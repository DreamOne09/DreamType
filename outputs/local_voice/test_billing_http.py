import asyncio
import tempfile
import threading
import unittest
import httpx
from fastapi import FastAPI
from billing_http import notification_router,PATH
import test_billing_notifications as notice_fixture
import test_billing_worker as worker_fixture


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_busy_requests_retry_and_capacity_recovers(self):
        started=threading.Event();release=threading.Event()
        class Receiver:
            def receive(self,*args):
                started.set()
                if not release.wait(5):raise RuntimeError('fixture timed out')
        app=FastAPI();app.include_router(notification_router(Receiver(),concurrency=1))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://fixture.invalid') as client:
            headers={'Authorization':'Bearer fixture','Content-Type':'application/json'}
            first=asyncio.create_task(client.post(PATH,headers=headers,content=b'{}'))
            try:
                async with asyncio.timeout(3):
                    while not started.is_set():await asyncio.sleep(.01)
                self.assertEqual((await client.post(PATH,headers=headers,content=b'{}')).status_code,503)
                first.cancel()
                with self.assertRaises(asyncio.CancelledError):await first
                self.assertEqual((await client.post(PATH,headers=headers,content=b'{}')).status_code,503)
            finally:release.set()
            async with asyncio.timeout(2):
                while True:
                    response=await client.post(PATH,headers=headers,content=b'{}')
                    if response.status_code==204:break
                    await asyncio.sleep(.02)

    async def test_http_to_durable_refresh_and_errors(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=worker_fixture.WorkerTests().setup_store(d)
            fixture=notice_fixture.NotificationTests();receiver=fixture.receiver(store)
            app=FastAPI();app.include_router(notification_router(receiver))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://fixture.invalid') as client:
                headers={'Authorization':'Bearer fixture','Content-Type':'application/json'}
                self.assertEqual((await client.post(PATH,content=fixture.body())).status_code,401)
                self.assertEqual((await client.post(PATH,headers=headers,content=fixture.body('unknown'))).status_code,503)
                response=await client.post(PATH,headers=headers,content=fixture.body())
                self.assertEqual(response.status_code,204)
                self.assertEqual(store.me(uid)['entitlement_status'],'verification_required')
                self.assertEqual((await client.post(PATH,headers=headers,content=b'bad-json')).status_code,400)
                async def chunks():
                    yield b'x'*20000
                    yield b'x'*20000
                self.assertEqual((await client.post(PATH,headers=headers,content=chunks())).status_code,413)
                self.assertEqual((await client.post(PATH,headers={**headers,'Content-Encoding':'gzip'},content=b'x')).status_code,415)

    async def test_limits_and_timeout_without_provider_call(self):
        class Receiver:
            def receive(self,*args):raise AssertionError('must not call provider')
        app=FastAPI();app.include_router(notification_router(Receiver(),per_minute=2,read_timeout=.01))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://fixture.invalid') as client:
            async def slow():
                await asyncio.sleep(.1)
                yield b'{}'
            headers={'Authorization':'Bearer fixture','Content-Type':'application/json'}
            self.assertEqual((await client.post(PATH,headers=headers,content=slow())).status_code,408)
            self.assertEqual((await client.post(PATH,headers={**headers,'Content-Length':'999999'},content=b'{}')).status_code,413)
            response=await client.post(PATH,headers=headers,content=b'{}')
            self.assertEqual(response.status_code,429)
            self.assertEqual(response.headers['Retry-After'],'30')


if __name__=='__main__':unittest.main()
