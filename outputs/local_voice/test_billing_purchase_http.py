import tempfile
import asyncio
import threading
from types import SimpleNamespace
import unittest
from pathlib import Path
import httpx
from fastapi import FastAPI
from billing_test_fixture import prepared_store
from billing_purchase_http import purchase_router
from billing_service import PlayPurchaseService,play_account_id
from entitlements import SubscriptionPolicy
from play_billing import PlayVerifier


class PurchaseHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_request_keeps_provider_slot_until_thread_finishes(self):
        release=threading.Event();started=threading.Event();calls=[]
        policy=SubscriptionPolicy({('fixture','monthly'):('pro',120)})
        store=SimpleNamespace(entitlement_policy=policy,authenticate=lambda _: {'id':'fixture'},
            me=lambda _:dict(plan='pro',entitlement_status='active',limit_seconds=120,remaining_seconds=120))
        def verify(*args):
            calls.append(1);started.set();release.wait(5)
        service=SimpleNamespace(store=store,account_identifier=lambda _: 'account',verify_and_claim=verify)
        app=FastAPI();app.include_router(purchase_router(service,concurrency=1))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://fixture.invalid') as client:
            headers={'Authorization':'Bearer fixture'};path='/v2/billing/google/verify'
            task=asyncio.create_task(client.post(path,headers=headers,json={'purchase_token':'fixture'}))
            try:
                async with asyncio.timeout(2):
                    while not started.is_set():await asyncio.sleep(.005)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):await task
                result=await client.post(path,headers=headers,json={'purchase_token':'fixture'})
                self.assertEqual(result.status_code,429);self.assertEqual(len(calls),1)
            finally:release.set()
            async with asyncio.timeout(2):
                while True:
                    result=await client.get('/v2/billing/google/account',headers=headers)
                    if result.status_code==200:break
                    await asyncio.sleep(.02)

    async def test_body_limit_and_slow_upload_never_call_provider(self):
        policy=SubscriptionPolicy({('fixture','monthly'):('pro',120)});calls=[]
        service=SimpleNamespace(store=SimpleNamespace(entitlement_policy=policy),
            account_identifier=lambda _: 'account',verify_and_claim=lambda *args:calls.append(1))
        app=FastAPI();app.include_router(purchase_router(service,read_timeout=.05))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://fixture.invalid') as client:
            headers={'Authorization':'Bearer fixture','Content-Type':'application/json'}
            path='/v2/billing/google/verify'
            result=await client.post(path,headers=headers,content=b'x'*8193)
            self.assertEqual(result.status_code,413)
            async def slow():
                await asyncio.sleep(.2);yield b'{}'
            result=await client.post(path,headers=headers,content=slow())
            self.assertEqual(result.status_code,408)
            self.assertEqual(calls,[])

    async def test_phone_to_google_to_policy_never_trusts_phone_flags(self):
        with tempfile.TemporaryDirectory() as d:
            store=prepared_store(Path(d)/'accounts.sqlite3',SubscriptionPolicy({('fixture','monthly'):('pro',120)}))
            uid=store.create('alice','fixture-password');session=store.login('alice','fixture-password')['token']
            calls=[];owner=[play_account_id(uid)]
            def google(request):
                calls.append(request.method)
                return httpx.Response(200,json={'externalAccountIdentifiers':{'obfuscatedExternalAccountId':owner[0]},'subscriptionState':'SUBSCRIPTION_STATE_ACTIVE','acknowledgementState':'ACKNOWLEDGEMENT_STATE_PENDING','lineItems':[{'productId':'fixture','offerDetails':{'basePlanId':'monthly'},'expiryTime':'2027-01-01T00:00:00Z'}]})
            service=PlayPurchaseService(store,PlayVerifier(lambda:'fixture-oauth',{('fixture','monthly')},transport=httpx.MockTransport(google)))
            app=FastAPI();app.include_router(purchase_router(service))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://fixture.invalid') as client:
                path='/v2/billing/google/verify';headers={'Authorization':'Bearer '+session}
                self.assertEqual((await client.post(path,json={'purchase_token':'fixture'})).status_code,401)
                identity=await client.get('/v2/billing/google/account',headers=headers)
                self.assertEqual(identity.json()['obfuscated_account_id'],play_account_id(uid))
                self.assertEqual(identity.json()['products'],[{'product_id':'fixture','base_plan_id':'monthly','monthly_seconds':120,'quota_reset':'utc_calendar_month'}])
                self.assertEqual((await client.post(path,headers=headers,json={'purchase_token':'fixture','paid':True})).status_code,400)
                self.assertEqual(calls,[])
                result=await client.post(path,headers=headers,json={'purchase_token':'fixture'})
                self.assertEqual(result.status_code,200);self.assertEqual(result.json()['limit_seconds'],120)
                self.assertEqual(result.json()['entitlement_status'],'active')
                self.assertNotIn('fixture',result.text)
                owner[0]='wrong-account'
                rejected=await client.post(path,headers=headers,json={'purchase_token':'another'})
                self.assertEqual(rejected.status_code,503)
                self.assertEqual(calls,['GET','GET'])
                store.logout(session)
                self.assertEqual((await client.post(path,headers=headers,json={'purchase_token':'fixture'})).status_code,401)


if __name__=='__main__':unittest.main()
