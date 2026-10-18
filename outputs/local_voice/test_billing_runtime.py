import asyncio
import json
import tempfile
import unittest
import threading
from unittest.mock import patch
from pathlib import Path
import httpx
from fastapi import FastAPI
from beta_api import install_beta
from billing_test_fixture import prepared_store
from billing_runtime import BillingRuntime
from entitlements import SubscriptionPolicy
from play_billing import PlayVerifier
from billing_service import play_account_id


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_shutdown_waits_for_running_pass_before_releasing_runtime(self):
        with tempfile.TemporaryDirectory() as d:
            policy=SubscriptionPolicy({('fixture','monthly'):('pro',120)})
            runtime=BillingRuntime(policy,PlayVerifier(lambda:'fixture',{('fixture','monthly')}),audience='https://fixture.invalid/push',email='push@fixture.iam.gserviceaccount.com',subscription='projects/fixture/subscriptions/play')
            store=prepared_store(Path(d)/'accounts.sqlite3',policy)
            runtime.bind(FastAPI(),store)
            started=threading.Event();release=threading.Event()
            def blocked(*args):
                started.set();release.wait(5);return {'checked':0}
            with patch('billing_runtime.run',blocked):
                await runtime.start()
                try:
                    async with asyncio.timeout(2):
                        while not started.is_set():await asyncio.sleep(.01)
                    stopping=asyncio.create_task(runtime.stop())
                    await asyncio.sleep(.02)
                    self.assertFalse(stopping.done())
                finally:release.set()
                await asyncio.wait_for(stopping,2)
                self.assertIsNone(runtime.task)

    async def test_shared_app_purchase_policy_and_background_lifecycle(self):
        with tempfile.TemporaryDirectory() as d:
            identity=[''];methods=[]
            def google(request):
                methods.append(request.method)
                return httpx.Response(200,json={'externalAccountIdentifiers':{'obfuscatedExternalAccountId':identity[0]},'subscriptionState':'SUBSCRIPTION_STATE_ACTIVE','acknowledgementState':'ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED','lineItems':[{'productId':'fixture','offerDetails':{'basePlanId':'monthly'},'expiryTime':'2027-01-01T00:00:00Z'}]})
            policy=SubscriptionPolicy({('fixture','monthly'):('pro',120)})
            runtime=BillingRuntime(policy,PlayVerifier(lambda:'fixture',{('fixture','monthly')},transport=httpx.MockTransport(google)),audience='https://fixture.invalid/push',email='push@fixture.iam.gserviceaccount.com',subscription='projects/fixture/subscriptions/play')
            prepared_store(Path(d)/'beta/accounts.sqlite3')
            app=FastAPI();beta=install_beta(app,Path(d),object(),lambda _:1,billing=runtime)
            uid=beta.store.create('alice','fixture-password');identity[0]=play_account_id(uid)
            session=beta.store.login('alice','fixture-password')['token'];headers={'Authorization':'Bearer '+session}
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://fixture.invalid') as client:
                    before=await client.get('/v2/me',headers=headers)
                    self.assertEqual(before.json()['entitlement_status'],'subscription_required')
                    purchase=await client.post('/v2/billing/google/verify',headers=headers,json={'purchase_token':'fixture'})
                    self.assertEqual(purchase.status_code,200)
                    me=await client.get('/v2/me',headers=headers)
                    self.assertEqual(me.json()['limit_seconds'],120)
                    admin={'Authorization':'Bearer '+beta.admin}
                    health=await client.get('/v2/admin/metrics',headers=admin)
                    self.assertEqual(health.status_code,200)
                    self.assertEqual(health.json()['billing']['counts']['subscriptions'],1)
                    self.assertNotIn('purchase_token',health.text)
                    (Path(d)/'endpoint-discovery.json').write_text(json.dumps({'public_url':'https://dreamtype.dreamone.li'}))
                    users=await client.get('/v2/admin/users',headers=admin)
                    self.assertTrue(users.json()['billing_enabled'])
                    self.assertEqual(users.json()['service_url'],'https://dreamtype.dreamone.li')
                    rejected=await client.patch('/v2/admin/users/'+uid,headers=admin,json={'minutes':9999})
                    self.assertEqual(rejected.status_code,400)
                    self.assertEqual((await client.patch('/v2/admin/users/'+uid,headers=admin,json={'enabled':True})).status_code,200)
                    self.assertEqual((await client.post('/v2/admin/users',headers=admin,json={'username':'bobby','password':'fixture-password','minutes':100})).status_code,400)
                    self.assertEqual((await client.post('/v2/admin/users',headers=admin,json={'username':'bobby','password':'fixture-password','minutes':0})).status_code,201)
                    self.assertIs(runtime.store,beta.store)
                    async with asyncio.timeout(3):
                        while 'checked_at' not in runtime.status:await asyncio.sleep(.01)
                    self.assertFalse(runtime.task.done())
            self.assertIsNone(runtime.task)
            self.assertEqual(runtime.status['state'],'stopped')
            self.assertTrue(methods);self.assertTrue(all(method=='GET' for method in methods))

    async def test_default_app_has_no_billing_routes_or_policy(self):
        with tempfile.TemporaryDirectory() as d:
            app=FastAPI();beta=install_beta(app,Path(d),object(),lambda _:1)
            self.assertIsNone(beta.store.entitlement_policy)
            self.assertFalse(any('/billing/' in r.path for r in app.routes))


if __name__=='__main__':unittest.main()
