import asyncio,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from fastapi import FastAPI
from beta_api import install_beta,LocalProvider
from beta_store import StoreError,Store

class NoSpeechTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_accepts_only_typed_422(self):
        client_type=httpx.AsyncClient
        for status,body,expected in ((422,{'error_code':'no_speech'},StoreError),(503,{'error_code':'no_speech'},httpx.HTTPStatusError),(422,{'error_code':'unknown'},httpx.HTTPStatusError),(422,[],httpx.HTTPStatusError)):
            def reply(request):return httpx.Response(status,json=body)
            with self.subTest(status=status,body=body),patch('beta_api.httpx.AsyncClient',lambda **kw:client_type(transport=httpx.MockTransport(reply))):
                with self.assertRaises(expected):await LocalProvider('http://example.invalid','synthetic').transcribe(b'audio',{})

    async def test_failure_survives_restart_without_charge_and_retry_clears_reason(self):
        class Provider:
            async def transcribe(self,audio,prefs):raise StoreError(422,'untrusted details','no_speech')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);app=FastAPI();beta=install_beta(app,root,Provider(),lambda audio:3)
            uid=beta.store.create('silence','synthetic-password')
            jid='silence-request-123456';beta.store.reserve(uid,jid,'digest',3)
            beta.store.save_pending(uid,jid,b'fixture audio',{},True)
            await beta.start()
            try:
                await asyncio.wait_for(beta.queue.join(),3)
                result=beta.progress(uid,jid)
                self.assertEqual(result['state'],'failed');self.assertEqual(result['error_code'],'no_speech')
                self.assertIn('未偵測到語音',result['message']);self.assertNotIn('untrusted',result['message'])
                self.assertEqual(beta.store.me(uid)['used_seconds'],0);self.assertEqual(beta.store.me(uid)['reserved_seconds'],0)
                with beta.store.db() as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM pending_audio').fetchone()[0],0)
                    self.assertNotIn(b'no_speech',db.execute('SELECT payload FROM results').fetchone()[0])
                other=beta.store.create('other','synthetic-password')
                with self.assertRaises(StoreError):beta.progress(other,jid)
                restarted=Store(root/'beta/accounts.sqlite3');restarted.recover()
                self.assertEqual(restarted.result(uid,jid),{'error_code':'no_speech'})
                restarted.reserve(uid,jid,'digest',3,retry_failed=True)
                self.assertIsNone(restarted.result(uid,jid))
                self.assertEqual(restarted.job(uid,jid)['state'],'queued')
            finally:await beta.stop()

if __name__=='__main__':unittest.main()
