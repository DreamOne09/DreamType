"""Bound upload memory and decoder work before inference queue admission."""
import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
import httpx
from fastapi import FastAPI
from beta_api import install_beta
from beta_store import StoreError
from request_limits import DecoderBudget


class Provider:
    async def transcribe(self,audio,prefs):return {'text':'測試文字'}


class UploadAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.release=threading.Event();self.started=threading.Event();self.calls=0
        def decoder(audio):
            self.calls+=1;self.started.set()
            if not self.release.wait(5):raise RuntimeError('test decoder timed out')
            return 1
        self.app=FastAPI();self.beta=install_beta(self.app,Path(self.temp.name),Provider(),decoder)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='http://test')
        self.headers=[]
        for name in ('first','second','third'):
            self.beta.store.create(name,'synthetic-password')
            token=self.beta.store.login(name,'synthetic-password')['token']
            self.headers.append({'Authorization':'Bearer '+token})
        await self.beta.start()

    async def asyncTearDown(self):
        self.release.set();await self.client.aclose();await self.beta.stop();self.temp.cleanup()

    async def upload(self,user=0,jid='test-request-00000001'):
        return await self.client.post('/v2/dictations',headers={**self.headers[user],'Idempotency-Key':jid},files={'file':('voice.wav',b'synthetic')})

    async def wait_started(self,count=1):
        async def poll():
            while self.calls<count:await asyncio.sleep(.005)
        await asyncio.wait_for(poll(),2)

    async def test_same_account_parallel_upload_rejected_before_decode(self):
        first=asyncio.create_task(self.upload())
        try:
            await self.wait_started()
            second=await asyncio.wait_for(self.upload(jid='test-request-00000002'),1)
            self.assertEqual(second.status_code,429)
            self.assertEqual(second.json()['error_code'],'upload_busy')
            self.assertEqual(self.calls,1)
            usage=(await self.client.get('/v2/me',headers=self.headers[0])).json()
            self.assertEqual(usage['used_seconds'],0);self.assertEqual(usage['reserved_seconds'],0)
        finally:
            self.release.set();await first
        await asyncio.wait_for(self.beta.queue.join(),2)
        self.assertEqual((await self.client.get('/v2/me',headers=self.headers[0])).json()['used_seconds'],1)

    async def test_upload_slots_reject_slow_bodies_before_reading_and_release(self):
        self.beta.upload_limit=2
        blocked=asyncio.Event();entered=asyncio.Event();third_read=False
        async def slow_body():
            entered.set();await blocked.wait();yield b'{}'
        first=asyncio.create_task(self.client.post('/v2/dictations',headers={**self.headers[0],'Content-Length':'2'},content=slow_body()))
        second=None
        try:
            await asyncio.wait_for(entered.wait(),1);entered.clear()
            second=asyncio.create_task(self.client.post('/v2/dictations',headers={**self.headers[1],'Content-Length':'2'},content=slow_body()))
            await asyncio.wait_for(entered.wait(),1)
            async def probe_body():
                nonlocal third_read
                third_read=True;yield b'{}'
            response=await asyncio.wait_for(self.client.post('/v2/dictations',headers={**self.headers[2],'Content-Length':'2'},content=probe_body()),1)
            self.assertEqual(response.status_code,429)
            self.assertFalse(third_read)
        finally:
            blocked.set();await first
            if second:await second
        self.assertFalse(self.beta.uploads)

    async def test_body_timeout_releases_slot_and_does_not_decode(self):
        self.beta.body_timeout=.03
        async def slow():
            await asyncio.sleep(1);yield b'{}'
        response=await self.client.post('/v2/dictations',headers={**self.headers[0],'Content-Length':'2'},content=slow())
        self.assertEqual(response.status_code,408)
        self.assertEqual(self.calls,0);self.assertFalse(self.beta.uploads)
        self.release.set();self.assertEqual((await self.upload()).status_code,202)

    async def test_unauthorized_or_oversized_bodies_are_not_read(self):
        read=False
        async def body():
            nonlocal read
            read=True;yield b'{}'
        response=await self.client.post('/v2/dictations',headers={'Content-Length':'2'},content=body())
        self.assertEqual(response.status_code,401);self.assertFalse(read)
        response=await self.client.post('/v2/dictations',headers={**self.headers[0],'Content-Length':str(3*1024*1024)},content=body())
        self.assertEqual(response.status_code,413);self.assertFalse(read);self.assertFalse(self.beta.uploads)

    async def test_request_cancellation_does_not_free_running_decoder(self):
        self.beta.decoders.wait_timeout=.05
        first=asyncio.create_task(self.upload());second=None
        try:
            await self.wait_started();first.cancel()
            with self.assertRaises(asyncio.CancelledError):await first
            self.assertFalse(self.beta.uploads)
            self.assertEqual(len(self.beta.decoders.tasks),1)
            second=asyncio.create_task(self.upload(user=1));await self.wait_started(2)
            response=await self.upload(user=2)
            self.assertEqual(response.status_code,429);self.assertEqual(self.calls,2)
        finally:
            self.release.set()
            if second:await second
            await asyncio.gather(*list(self.beta.decoders.tasks),return_exceptions=True)
        self.assertFalse(self.beta.uploads);self.assertFalse(self.beta.decoders.tasks)

    async def test_three_normal_uploads_wait_without_spawning_extra_decoders(self):
        pending=[asyncio.create_task(self.upload(user=i)) for i in range(3)]
        try:
            await self.wait_started(2)
            async def queued():
                while self.beta.decoders.waiting!=1:await asyncio.sleep(.005)
            await asyncio.wait_for(queued(),1)
            self.assertEqual(self.calls,2)
        finally:self.release.set()
        responses=await asyncio.gather(*pending)
        self.assertEqual([r.status_code for r in responses],[202]*3)
        self.assertEqual(self.calls,3)

    async def test_active_job_and_exhausted_quota_rejected_without_decoding(self):
        token=self.headers[0]['Authorization'].removeprefix('Bearer ')
        uid=self.beta.store.authenticate(token)['id']
        self.beta.store.reserve(uid,'existing-job-000001','synthetic-digest',1)
        response=await self.upload()
        self.assertEqual(response.status_code,429)
        self.assertEqual(response.json()['error_code'],'job_in_progress')
        self.beta.store.state(uid,'existing-job-000001','failed')
        self.beta.store.update(uid,enabled=True,minutes=0)
        response=await self.upload()
        self.assertEqual(response.status_code,402);self.assertEqual(self.calls,0)


class DecoderBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_retains_actual_running_slot_then_recovers(self):
        release=threading.Event();budget=DecoderBudget(limit=1,timeout=.02,wait_timeout=.02)
        def slow(audio):release.wait(3);return 1
        try:
            with self.assertRaises(StoreError) as caught:await budget.run(slow,b'')
            self.assertEqual(caught.exception.code,'decode_timeout')
            self.assertEqual(len(budget.tasks),1)
            with self.assertRaises(StoreError) as busy:await budget.run(slow,b'')
            self.assertEqual(busy.exception.code,'upload_busy')
        finally:
            release.set();await asyncio.gather(*list(budget.tasks),return_exceptions=True)
        budget.timeout=1  # Recovery correctness, not a 20 ms Windows scheduling assertion.
        self.assertEqual(await budget.run(lambda audio:5,b''),5)

    async def test_decoder_failure_releases_slot(self):
        budget=DecoderBudget(limit=1)
        def invalid(audio):raise ValueError('invalid recording')
        with self.assertRaises(ValueError):await budget.run(invalid,b'')
        self.assertFalse(budget.tasks)
        self.assertEqual(await budget.run(lambda audio:5,b''),5)


if __name__=='__main__':unittest.main()
