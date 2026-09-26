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
    async def test_short_dictation_priority_uses_decoded_duration_and_mode(self):
        self.beta.decoder=lambda audio:float(audio)
        self.provider.gate.clear()
        users=[await self.account('priority-'+str(i)) for i in range(5)]
        await self.upload(users[0][1],audio=b'60')
        async def started():
            while not self.provider.calls:await asyncio.sleep(.01)
        await asyncio.wait_for(started(),2)
        await self.upload(users[1][1],audio=b'30')
        await self.upload({**users[2][1],'X-DreamType-Mode':'translate','X-DreamType-Target':'en'},audio=b'5')
        await self.upload(users[3][1],audio=b'15')
        await self.upload(users[4][1],audio=b'15.1')
        self.provider.gate.set()
        await asyncio.wait_for(self.beta.queue.join(),3)
        self.assertEqual([call[0] for call in self.provider.calls],[b'60',b'15',b'30',b'5',b'15.1'])
        for (uid,_),seconds in zip(users,(60,30,5,15,16)):
            self.assertEqual(self.beta.store.me(uid)['used_seconds'],seconds)

    async def test_recovered_jobs_keep_snapshot_and_short_priority(self):
        self.beta.decoder=lambda audio:float(audio)
        users=[await self.account('recover-priority-'+str(i)) for i in range(3)]
        await self.beta.stop()
        await self.upload(users[0][1],audio=b'30')
        await self.upload({**users[1][1],'X-DreamType-Mode':'translate','X-DreamType-Target':'ja'},audio=b'5')
        await self.upload(users[2][1],audio=b'10')
        await self.beta.stop()
        await self.beta.start()
        await asyncio.wait_for(self.beta.queue.join(),3)
        self.assertEqual([call[0] for call in self.provider.calls],[b'10',b'30',b'5'])
        self.assertEqual(self.provider.calls[-1][1]['target_language'],'ja')
        self.assertTrue(self.beta.workers_ready())

    async def test_full_queue_rejects_without_reserving_and_accepts_later(self):
        first,a=await self.account();second,b=await self.account('bob');third,c=await self.account('charlie')
        # Keep the production worker, but use one waiting slot to reach capacity quickly.
        await self.beta.stop()
        self.beta.queue=asyncio.Queue(maxsize=1)
        self.provider.gate.clear()
        await self.beta.start()
        self.assertEqual((await self.upload(a)).status_code,202)
        async def wait_for_provider():
            while not self.provider.calls:await asyncio.sleep(0.01)
        await asyncio.wait_for(wait_for_provider(),2)
        self.assertEqual((await self.upload(b)).status_code,202)
        rejected=await self.upload(c)
        self.assertEqual(rejected.status_code,429)
        self.assertEqual(rejected.json()['error_code'],'queue_full')
        me=self.beta.store.me(third)
        self.assertEqual(me['used_seconds'],0)
        self.assertEqual(me['reserved_seconds'],0)
        self.provider.gate.set()
        await asyncio.wait_for(self.beta.queue.join(),2)
        self.assertEqual((await self.upload(c)).status_code,202)
        await asyncio.wait_for(self.beta.queue.join(),2)
        self.assertEqual(self.beta.progress(third,'request-1234567890')['state'],'done')
        self.assertEqual(self.beta.store.me(third)['used_seconds'],10)
        self.assertEqual(len(self.provider.calls),3)

    async def test_busy_and_unconfirmed_result_have_distinct_recovery_codes(self):
        _,auth=await self.account()
        self.provider.gate.clear()
        await self.upload({**auth,'X-DreamType-Receipt':'1'})
        busy=await self.upload(auth,jid='another-request-123456')
        self.assertEqual(busy.status_code,429)
        self.assertEqual(busy.json()['error_code'],'job_in_progress')
        self.provider.gate.set()
        await asyncio.wait_for(self.beta.queue.join(),2)
        unconfirmed=await self.upload(auth,jid='another-request-123456')
        self.assertEqual(unconfirmed.status_code,409)
        self.assertEqual(unconfirmed.json()['error_code'],'result_unconfirmed')

    async def test_worker_health_detects_either_background_task_stopping(self):
        self.assertTrue(self.beta.workers_ready())
        for index in (0,1):
            task=self.beta.tasks[index]
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
            self.assertFalse(self.beta.workers_ready())
            response=await self.client.get('/v2/admin/metrics',headers=self.admin)
            self.assertFalse(response.json()['worker_alive'])
            await self.beta.stop();await self.beta.start()
            self.assertTrue(self.beta.workers_ready())

    async def test_stalled_provider_releases_quota_and_next_user_runs(self):
        first,a=await self.account();second,b=await self.account('bob')
        cancelled=asyncio.Event();calls=[]
        async def stalled_then_ok(audio,prefs):
            calls.append(audio)
            if audio==b'stalled':
                try:await asyncio.Event().wait()
                finally:cancelled.set()
            return {'text':'第二位使用者的結果'}
        self.provider.transcribe=stalled_then_ok;self.beta.processing_timeout=0.05
        await self.upload(a,audio=b'stalled');await self.upload(b,audio=b'next')
        await asyncio.wait_for(self.beta.queue.join(),2)
        self.assertTrue(cancelled.is_set())
        self.assertEqual(calls,[b'stalled',b'next'])
        self.assertEqual(self.beta.store.me(first)['reserved_seconds'],0)
        self.assertEqual(self.beta.store.me(first)['used_seconds'],0)
        self.assertEqual(self.beta.progress(first,'request-1234567890')['state'],'failed')
        self.assertEqual(self.beta.progress(second,'request-1234567890')['text'],'第二位使用者的結果')
        self.assertTrue(all(not task.done() for task in self.beta.tasks))

    async def test_empty_provider_result_is_not_charged(self):
        uid,auth=await self.account()
        for index,text in enumerate(('', ' \n\t')):
            async def empty(audio,prefs):return {'text':text}
            self.provider.transcribe=empty
            jid='empty-result-request-'+str(index)
            await self.upload(auth,jid=jid)
            await asyncio.wait_for(self.beta.queue.join(),2)
            self.assertEqual(self.beta.progress(uid,jid)['state'],'failed')
        self.assertEqual(self.beta.store.me(uid)['used_seconds'],0)
        self.assertEqual(self.beta.store.me(uid)['reserved_seconds'],0)

    async def test_admin_metrics_report_missing_or_malformed_maintenance(self):
        self.assertEqual((await self.client.get('/v2/admin/metrics')).status_code,401)
        for data in ('[]', '{"checked_at": 1, "ready": true, "errors": []}'):
            (Path(self.temp.name)/'maintenance-status.json').write_text(data)
            response=await self.client.get('/v2/admin/metrics',headers=self.admin)
            self.assertEqual(response.status_code,200)
            checks={c['code']:c for c in response.json()['operations']['checks']}
            self.assertEqual(checks['engine']['state'],'attention')
            self.assertEqual(checks['offsite']['state'],'unverified')

    async def test_translation_choice_snapshot_and_retry(self):
        _,a=await self.account();self.provider.gate.clear()
        header={**a,'X-DreamType-Mode':'translate','X-DreamType-Target':'th','X-DreamType-Source':'zh-TW'}
        r=await self.upload(header);self.assertEqual(r.status_code,202)
        await self.client.post('/v2/me/preferences',headers=a,json={'mode':'translate','target_language':'ja'})
        self.provider.gate.set();await asyncio.wait_for(self.beta.queue.join(),2)
        self.assertEqual(self.provider.calls[0][1]['target_language'],'th')
        r=await self.upload({**header,'X-DreamType-Target':'ja'})
        self.assertEqual(r.status_code,202);self.assertEqual(len(self.provider.calls),1)
        r=await self.upload({**header,'X-DreamType-Target':'unsupported'},jid='new-request-12345678')
        self.assertEqual(r.status_code,400)
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
    async def test_receipt_is_account_scoped_and_idempotent(self):
        uid,a=await self.account();_,b=await self.account('bob')
        await self.upload({**a,'X-DreamType-Receipt':'1'});await asyncio.wait_for(self.beta.queue.join(),2)
        path='/v2/dictations/request-1234567890/receipt'
        self.assertTrue((await self.client.get('/v2/me/latest-dictation',headers=a)).json()['receipt_required'])
        self.assertEqual((await self.client.post(path,headers=b,json={})).status_code,409)
        for _ in range(2):self.assertEqual((await self.client.post(path,headers=a,json={})).status_code,200)
        self.assertFalse((await self.client.get('/v2/me/latest-dictation',headers=a)).json()['receipt_required'])
        self.assertEqual(self.beta.store.me(uid)['used_seconds'],10)
    async def test_worker_resumes_encrypted_pending_job_after_restart(self):
        uid,a=await self.account();self.provider.gate.clear()
        await self.upload({**a,'X-DreamType-Receipt':'1'})
        await self.beta.stop()
        self.assertEqual(self.beta.store.me(uid)['reserved_seconds'],10)
        self.provider.gate.set();await self.beta.start();await asyncio.wait_for(self.beta.queue.join(),2)
        result=(await self.client.get('/v2/me/latest-dictation',headers=a)).json()
        self.assertEqual(result['state'],'done');self.assertTrue(result['receipt_required'])
        self.assertEqual(self.beta.store.me(uid)['used_seconds'],10)
    async def test_admin_reset_revokes_old_session(self):
        uid,a=await self.account();path='/v2/admin/users/'+uid+'/password-reset'
        self.assertEqual((await self.client.post(path,headers=a,json={})).status_code,401)
        code=(await self.client.post(path,headers=self.admin,json={})).json()['code']
        r=await self.client.post('/v2/password-reset',json={'code':code,'new_password':'changed-password-12345'})
        self.assertEqual(r.status_code,200)
        self.assertEqual((await self.client.get('/v2/me',headers=a)).status_code,401)
        r=await self.client.get('/v2/admin/audit',headers=self.admin)
        self.assertIn('password_reset_completed',[e['action'] for e in r.json()['events']])
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
    async def test_latest_recovery_is_private_and_does_not_charge_twice(self):
        _,a=await self.account();_,b=await self.account('bob')
        self.assertEqual((await self.client.get('/v2/me/latest-dictation')).status_code,401)
        self.assertEqual((await self.client.get('/v2/me/latest-dictation',headers=a)).json()['state'],'none')
        await self.upload(a);await asyncio.wait_for(self.beta.queue.join(),2)
        for _ in range(2):
            r=await self.client.get('/v2/me/latest-dictation',headers=a)
            self.assertEqual(r.json()['text'],'整理完成')
        self.assertEqual((await self.client.get('/v2/me/latest-dictation',headers=b)).json()['state'],'none')
        self.assertEqual((await self.client.get('/v2/me',headers=a)).json()['used_seconds'],10)
        self.assertEqual(len(self.provider.calls),1)
        self.beta.results.clear()
        self.assertEqual((await self.client.get('/v2/me/latest-dictation',headers=a)).json()['state'],'done')
    async def test_latest_running_can_be_recovered_after_lost_response(self):
        _,a=await self.account();self.provider.gate.clear()
        await self.upload(a)
        r=await self.client.get('/v2/me/latest-dictation',headers=a)
        self.assertIn(r.json()['state'],('queued','running'))
        self.provider.gate.set();await asyncio.wait_for(self.beta.queue.join(),2)
        self.assertEqual((await self.client.get('/v2/me/latest-dictation',headers=a)).json()['state'],'done')
    async def test_retry_keeps_original_settings_and_success_charge(self):
        _,a=await self.account()
        await self.upload(a);await self.beta.queue.join()
        await self.client.post('/v2/me/preferences',headers=a,json={'personal_prompt':'之後的錄音才用條列'})
        r=await self.upload(a);self.assertEqual(r.status_code,202,r.text)
        self.assertEqual(r.json()['state'],'done');self.assertEqual(len(self.provider.calls),1)
        self.assertEqual((await self.client.get('/v2/me',headers=a)).json()['used_seconds'],10)
    async def test_explicit_retry_failed_job_charges_once(self):
        _,a=await self.account();original=self.provider.transcribe
        async def fail(audio,prefs):raise ValueError('temporary failure')
        self.provider.transcribe=fail
        await self.upload(a);await self.beta.queue.join()
        self.assertEqual((await self.upload(a)).json()['state'],'failed')
        self.provider.transcribe=original
        r=await self.upload({**a,'X-DreamType-Retry':'1'});self.assertEqual(r.status_code,202,r.text)
        await self.beta.queue.join()
        self.assertEqual((await self.client.get('/v2/me/latest-dictation',headers=a)).json()['state'],'done')
        self.assertEqual((await self.client.get('/v2/me',headers=a)).json()['used_seconds'],10)

if __name__=='__main__':unittest.main()
