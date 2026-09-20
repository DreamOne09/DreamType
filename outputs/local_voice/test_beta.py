import asyncio
import tempfile
import unittest
from pathlib import Path
import httpx
from fastapi import FastAPI
from beta_api import install_beta

PASSWORD='test-password-12345'

class Provider:
    def __init__(self):self.calls=[];self.gate=asyncio.Event();self.gate.set()
    async def transcribe(self,audio,prefs):
        self.calls.append((audio,prefs));await self.gate.wait()
        return {'text':'整理完成','timings':{'total_seconds':0.1}}

class BetaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.provider=Provider();self.app=FastAPI()
        self.beta=install_beta(self.app,Path(self.temp.name),self.provider,lambda audio:10)
        await self.beta.start()
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='http://test')
        self.admin={'Authorization':'Bearer '+self.beta.admin}
    async def asyncTearDown(self):
        await self.client.aclose();await self.beta.stop();self.temp.cleanup()
    async def account(self,name='alice',minutes=1200):
        r=await self.client.post('/v2/admin/users',headers=self.admin,json={'username':name,'password':PASSWORD,'minutes':minutes})
        self.assertEqual(r.status_code,201,r.text);uid=r.json()['id']
        r=await self.client.post('/v2/login',json={'username':name,'password':PASSWORD})
        self.assertEqual(r.status_code,200,r.text)
        return uid,{'Authorization':'Bearer '+r.json()['token']}
    async def upload(self,headers,jid='request-1234567890',audio=b'voice'):
        return await self.client.post('/v2/dictations',headers={**headers,'Idempotency-Key':jid},files={'file':('voice.m4a',audio)})
    async def test_auth_preferences_and_admin_isolation(self):
        self.assertEqual((await self.client.get('/v2/admin/users')).status_code,401)
        _,a=await self.account();_,b=await self.account('bob')
        self.assertEqual((await self.client.get('/v2/admin/users',headers=a)).status_code,401)
        r=await self.client.patch('/v2/me/preferences',headers=a,json={'personal_prompt':'請用條列','vocabulary':'汐止','taiwan_places':True})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual((await self.client.get('/v2/me',headers=b)).json()['preferences'],{})
        self.assertEqual((await self.client.get('/v2/me',headers=a)).json()['preferences']['vocabulary'],'汐止')
        r=await self.client.patch('/v2/me/preferences',headers=a,json={'personal_prompt':'x'*2001})
        self.assertEqual(r.status_code,400)
        r=await self.client.post('/v2/login',json=[]);self.assertEqual(r.status_code,400)
    async def test_queue_idempotency_and_quota(self):
        _,a=await self.account(minutes=1);_,b=await self.account('bob')
        self.provider.gate.clear()
        r=await self.upload(a);self.assertEqual(r.status_code,202,r.text)
        r=await self.upload(a);self.assertEqual(r.status_code,202,r.text)
        self.assertEqual((await self.upload(a,'different-12345678')).status_code,429)
        self.assertEqual((await self.upload(a,audio=b'different')).status_code,409)
        self.assertEqual((await self.client.get('/v2/dictations/request-1234567890',headers=b)).status_code,404)
        self.assertEqual((await self.client.get('/v2/me',headers=a)).json()['reserved_seconds'],10)
        self.provider.gate.set();await asyncio.wait_for(self.beta.queue.join(),2)
        r=await self.client.get('/v2/dictations/request-1234567890',headers=a)
        self.assertEqual(r.json()['text'],'整理完成');self.assertEqual(len(self.provider.calls),1)
        self.assertEqual((await self.client.get('/v2/me',headers=a)).json()['used_seconds'],10)
        _,c=await self.account('charlie',minutes=0)
        self.assertEqual((await self.upload(c)).status_code,402)
    async def test_disable_logout_and_delete(self):
        uid,a=await self.account()
        r=await self.client.patch('/v2/admin/users/'+uid,headers=self.admin,json={'enabled':False,'minutes':10})
        self.assertEqual(r.status_code,200)
        self.assertEqual((await self.client.get('/v2/me',headers=a)).status_code,401)
        self.assertEqual((await self.client.post('/v2/login',json={'username':'alice','password':PASSWORD})).status_code,401)
        uid,b=await self.account('bob')
        r=await self.client.request('DELETE','/v2/me',headers=b,json={'password':'wrong'});self.assertEqual(r.status_code,403)
        r=await self.client.request('DELETE','/v2/me',headers=b,json={'password':PASSWORD});self.assertEqual(r.status_code,200)
        self.assertEqual((await self.client.get('/v2/me',headers=b)).status_code,401)
        _,c=await self.account('charlie')
        self.assertEqual((await self.client.post('/v2/logout',headers=c,content=b'')).status_code,200)
        self.assertEqual((await self.client.get('/v2/me',headers=c)).status_code,401)
    async def test_failure_and_restart_release_reservation(self):
        uid,a=await self.account()
        async def fail(audio,prefs):raise RuntimeError('private-provider-error')
        self.provider.transcribe=fail
        self.assertEqual((await self.upload(a)).status_code,202)
        await asyncio.wait_for(self.beta.queue.join(),2)
        self.assertEqual(self.beta.store.me(uid)['used_seconds'],0)
        self.assertEqual(self.beta.progress(uid,'request-1234567890')['state'],'failed')
        self.beta.store.reserve(uid,'restart-123456789','digest',10)
        self.beta.store.recover()
        self.assertEqual(self.beta.store.me(uid)['reserved_seconds'],0)
    async def test_fifo_and_preferences_snapshot(self):
        _,a=await self.account();_,b=await self.account('bob')
        self.provider.gate.clear()
        await self.client.patch('/v2/me/preferences',headers=a,json={'personal_prompt':'甲'})
        await self.upload(a,audio=b'a');await self.upload(b,audio=b'b')
        self.assertEqual(len(self.provider.calls),1)
        await self.client.patch('/v2/me/preferences',headers=a,json={'personal_prompt':'新設定'})
        self.provider.gate.set();await asyncio.wait_for(self.beta.queue.join(),2)
        self.assertEqual([c[0] for c in self.provider.calls],[b'a',b'b'])
        self.assertEqual(self.provider.calls[0][1]['personal_prompt'],'甲')
    async def test_password_change_revokes_all_sessions(self):
        _,a=await self.account()
        second=await self.client.post('/v2/login',json={'username':'alice','password':PASSWORD})
        b={'Authorization':'Bearer '+second.json()['token']}
        r=await self.client.post('/v2/me/password',headers=a,json={'current_password':'wrong','new_password':'replacement-12345'})
        self.assertEqual(r.status_code,403)
        r=await self.client.post('/v2/me/password',headers=a,json={'current_password':PASSWORD,'new_password':'replacement-12345'})
        self.assertEqual(r.status_code,200,r.text)
        for headers in (a,b):self.assertEqual((await self.client.get('/v2/me',headers=headers)).status_code,401)
        r=await self.client.post('/v2/login',json={'username':'alice','password':'replacement-12345'})
        self.assertEqual(r.status_code,200)
    async def test_body_and_audio_limits(self):
        _,a=await self.account()
        self.assertEqual((await self.client.post('/v2/login',content=b'{' )).status_code,400)
        r=await self.client.post('/v2/login',content=b'x'*20000);self.assertEqual(r.status_code,413)
        self.assertEqual((await self.upload(a,audio=b'x'*(2*1024*1024+1))).status_code,413)
        self.beta.decoder=lambda audio:121
        self.assertEqual((await self.upload(a)).status_code,413)

if __name__=='__main__':unittest.main()
