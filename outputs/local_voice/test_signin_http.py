import asyncio
import json
import tempfile
import threading
import unittest
from pathlib import Path
from fastapi import FastAPI
import httpx
import test_signin_storage as storage
import test_google_signin as identity
from reauth_migration import prepare_reauth
from signin_config import SignInRuntime,load_signin
from signin_http import signin_router,BASE,DELETE,ORIGIN,LIMIT
from signin_store import SignInStore
from account_reauth import GoogleAccountDeletion
from beta_api import install_beta
from web_pages import install_web_pages

class SignInHttpTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):identity.GoogleSignInTests.setUpClass()

    async def test_google_assets_and_policy_are_scoped_to_user_pages(self):
        with tempfile.TemporaryDirectory() as d:
            app,store,proof=self.fixture(d);install_web_pages(app)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN) as client:
                for path in ('/','/dictate','/account'):
                    response=await client.get(path)
                    self.assertEqual(response.status_code,200)
                    csp=response.headers['content-security-policy']
                    self.assertIn('https://accounts.google.com/gsi/client',csp)
                    self.assertIn("frame-ancestors 'none'",csp)
                    self.assertIn("base-uri 'none'",csp)
                    self.assertEqual(response.headers['cross-origin-opener-policy'],'same-origin-allow-popups')
                self.assertNotIn('accounts.google.com',(await client.get('/admin')).headers['content-security-policy'])
                response=await client.get('/web/google_account.mjs')
                self.assertEqual(response.status_code,200)
                self.assertIn('javascript',response.headers['content-type'])
                self.assertEqual(response.headers['cache-control'],'no-store')

    def fixture(self,d,signup=True,full=True,**limits):
        root,store=storage.SignInStorageTests().fixture(d);prepare_reauth(root)
        proof=identity.GoogleSignInTests();proof.setUp()
        runtime=SignInRuntime(proof.client,[proof.android],signup);runtime.verifier=proof.verifier
        app=FastAPI()
        if full:beta=install_beta(app,root/'work',None,None,signin=runtime);store=beta.store
        else:app.include_router(signin_router(SignInStore(store,proof.verifier),GoogleAccountDeletion(store,proof.verifier),proof.client,allow_signup=signup,**limits))
        return app,store,proof

    async def test_full_app_signed_signup_login_delete_and_old_route_guards(self):
        with tempfile.TemporaryDirectory() as d:
            app,store,proof=self.fixture(d)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN,headers={'X-DreamType-Client':'android'}) as client:
                self.assertEqual((await client.get('/v2/me')).status_code,401)
                self.assertEqual((await client.get(BASE+'/unexpected')).status_code,401)
                config=await client.get(BASE+'/config');self.assertEqual(config.json()['client_id'],proof.client)
                c=(await client.post(BASE+'/challenge',json={'purpose':'signup'})).json()
                payload={'challenge':c['challenge'],'secret':c['secret'],'id_token':proof.token({'nonce':c['nonce']})}
                result=await client.post(BASE+'/complete',json=payload);self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(result.headers['cache-control'],'no-store')
                session=result.json()['token'];headers={'Authorization':'Bearer '+session}
                me=await client.get('/v2/me',headers=headers);self.assertEqual(me.json()['remaining_seconds'],0);self.assertEqual(me.json()['login_methods'],['google']);self.assertNotIn('password',me.json())
                self.assertEqual((await client.post(BASE+'/complete',json=payload)).status_code,401)
                deletion=(await client.post(DELETE+'/challenge',json={},headers=headers)).json()
                payload={'challenge':deletion['challenge'],'secret':deletion['secret'],'id_token':proof.token({'nonce':deletion['nonce']}),'confirm':False}
                self.assertEqual((await client.post(DELETE+'/complete',json=payload,headers=headers)).status_code,400)
                payload['confirm']=True
                result=await client.post(DELETE+'/complete',json=payload,headers=headers)
                self.assertEqual(result.json(),{'deleted':True,'subscription_cancelled':False})
                self.assertEqual((await client.get('/v2/me',headers=headers)).status_code,401)

    async def test_origin_signup_switch_body_and_auth_rejected_before_proof(self):
        with tempfile.TemporaryDirectory() as d:
            app,store,proof=self.fixture(d,signup=False)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN) as client:
                for headers in ({},{'X-DreamType-Client':'web'}, {'X-DreamType-Client':'android','Origin':'https://evil.invalid'},
                                {'X-DreamType-Client':'web','Origin':ORIGIN,'Sec-Fetch-Site':'cross-site'}):
                    self.assertEqual((await client.post(BASE+'/challenge',headers=headers,json={'purpose':'signup'})).status_code,403)
                headers={'X-DreamType-Client':'web','Origin':ORIGIN,'Sec-Fetch-Site':'same-origin'}
                self.assertEqual((await client.get(BASE+'/config',headers=headers)).status_code,200)
                get_headers={'X-DreamType-Client':'web','Sec-Fetch-Site':'same-origin'}
                self.assertEqual((await client.get(BASE+'/config',headers=get_headers)).status_code,200)
                self.assertEqual((await client.post(BASE+'/challenge',headers=get_headers,json={'purpose':'signin'})).status_code,403)
                self.assertEqual((await client.get(BASE+'/config',headers={'X-DreamType-Client':'web'})).status_code,403)
                self.assertEqual((await client.get(BASE+'/config',headers={**get_headers,'Origin':'https://evil.invalid'})).status_code,403)
                self.assertEqual((await client.post(BASE+'/challenge',headers=headers,json={'purpose':'signup'})).status_code,403)
                self.assertEqual((await client.post(BASE+'/complete',headers=headers,json={'paid':True})).status_code,400)
                self.assertEqual((await client.post(DELETE+'/challenge',headers=headers,json={})).status_code,401)
                self.assertEqual((await client.post(BASE+'/complete',headers={**headers,'Content-Type':'application/json'},content=b'x'*(LIMIT+1))).status_code,413)
                self.assertEqual(proof.calls,[])

    async def test_slow_body_and_cancelled_verifier_keep_admission_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            app,store,proof=self.fixture(d,full=False,read_timeout=.05,concurrency=1)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN,headers={'X-DreamType-Client':'android'}) as client:
                async def slow():await asyncio.sleep(.2);yield b'{}'
                self.assertEqual((await client.post(BASE+'/complete',headers={'Content-Type':'application/json'},content=slow())).status_code,408)
                c=(await client.post(BASE+'/challenge',json={'purpose':'signup'})).json()
                started=threading.Event();release=threading.Event();original=proof.verifier.verify
                def block(token,nonce):started.set();release.wait(5);return original(token,nonce)
                proof.verifier.verify=block
                payload={'challenge':c['challenge'],'secret':c['secret'],'id_token':proof.token({'nonce':c['nonce']})}
                task=asyncio.create_task(client.post(BASE+'/complete',json=payload))
                try:
                    async with asyncio.timeout(2):
                        while not started.is_set():await asyncio.sleep(.005)
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):await task
                    self.assertEqual((await client.get(BASE+'/config')).status_code,429)
                finally:release.set()
                async with asyncio.timeout(2):
                    while (await client.get(BASE+'/config')).status_code!=200:await asyncio.sleep(.03)
                with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],1)

    async def test_disabled_default_and_private_configuration_validation(self):
        with tempfile.TemporaryDirectory() as d:
            work=Path(d);self.assertIsNone(load_signin(work))
            path=work/'signin-config.json';path.write_text('{"enabled":false}')
            self.assertIsNone(load_signin(work))
            for value in ({'enabled':0},{'enabled':True},{'enabled':False,'client_id':'anything'}):
                path.write_text(json.dumps(value))
                with self.assertRaises(RuntimeError):load_signin(work)
            path.write_text(json.dumps({'enabled':True,'client_id':'web-fixture.apps.googleusercontent.com','presenters':[],'allow_signup':False}))
            self.assertIsInstance(load_signin(work),SignInRuntime)
            path.write_text(' '*16385)
            with self.assertRaises(RuntimeError):load_signin(work)
            app=FastAPI();beta=install_beta(app,work,None,None)
            self.assertFalse(any(r.path in (BASE+'/config',BASE+'/challenge') for r in app.routes))
            runtime=SignInRuntime('web-fixture.apps.googleusercontent.com',[])
            with self.assertRaises(ValueError):runtime.validate_storage(beta.store.path)

if __name__=='__main__':unittest.main()
