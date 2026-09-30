import asyncio
import tempfile
import time
import unittest
from pathlib import Path
import httpx
from fastapi import FastAPI
from beta_api import install_beta


class AuthAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        app=FastAPI()
        self.beta=install_beta(app,Path(self.temp.name),object(),lambda _:1)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose();self.temp.cleanup()

    async def test_login_and_reset_share_slots_before_body_read(self):
        self.beta.auth_receive_limit=2
        release=asyncio.Event();entered=asyncio.Event();read=False;tasks=[]
        async def slow():
            entered.set();await release.wait();yield b'{}'
        try:
            for path in ('/v2/login','/v2/password-reset'):
                entered.clear()
                tasks.append(asyncio.create_task(self.client.post(path,headers={'Content-Length':'2'},content=slow())))
                await asyncio.wait_for(entered.wait(),1)
            async def extra():
                nonlocal read
                read=True;yield b'{}'
            response=await self.client.post('/v2/login',headers={'Content-Length':'2'},content=extra())
            self.assertEqual(response.status_code,429);self.assertFalse(read)
            self.assertEqual(response.headers['retry-after'],'2')
            self.assertEqual(response.json()['error_code'],'auth_rate_limit')
            self.assertEqual(self.beta.auth_receivers,2)
        finally:
            release.set();await asyncio.gather(*tasks)
        self.assertEqual(self.beta.auth_receivers,0)
        self.assertNotEqual((await self.client.post('/v2/login',json={})).status_code,429)

    async def test_rate_limit_rejects_both_routes_without_reading_body(self):
        self.beta.logins.extend([time.monotonic()]*20)
        read=False
        async def body():
            nonlocal read
            read=True;yield b'{}'
        for path in ('/v2/login','/v2/password-reset'):
            response=await self.client.post(path,headers={'Content-Length':'2'},content=body())
            self.assertEqual(response.status_code,429)
            self.assertEqual(response.headers['retry-after'],'60')
        self.assertFalse(read);self.assertEqual(self.beta.auth_receivers,0)

    async def test_timeout_releases_slot_but_attempt_still_counts(self):
        self.beta.body_timeout=.01
        async def slow():
            await asyncio.Event().wait();yield b'{}'
        response=await self.client.post('/v2/login',headers={'Content-Length':'2'},content=slow())
        self.assertEqual(response.status_code,408)
        self.assertEqual(self.beta.auth_receivers,0);self.assertEqual(len(self.beta.logins),1)

    async def test_cancelled_body_releases_slot_but_attempt_still_counts(self):
        entered=asyncio.Event()
        async def slow():
            entered.set();await asyncio.Event().wait();yield b'{}'
        task=asyncio.create_task(self.client.post('/v2/password-reset',headers={'Content-Length':'2'},content=slow()))
        await asyncio.wait_for(entered.wait(),1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(self.beta.auth_receivers,0);self.assertEqual(len(self.beta.logins),1)

    async def test_expired_attempts_allow_new_request(self):
        self.beta.logins.extend([time.monotonic()-61]*20)
        response=await self.client.post('/v2/login',json={})
        self.assertNotEqual(response.status_code,429)
        self.assertEqual(len(self.beta.logins),1);self.assertEqual(self.beta.auth_receivers,0)

    async def test_bad_json_releases_slot(self):
        response=await self.client.post('/v2/login',content=b'{')
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.beta.auth_receivers,0)


if __name__=='__main__':unittest.main()
