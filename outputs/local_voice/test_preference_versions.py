import tempfile
import unittest
from pathlib import Path
import httpx
from fastapi import FastAPI
from beta_api import install_beta
from beta_store import StoreError, preferences_etag

class PreferenceVersionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=FastAPI();self.beta=install_beta(self.app,Path(self.temp.name),None,lambda audio:1)
        self.beta.store.create('alice','synthetic-password')
        token=self.beta.store.login('alice','synthetic-password')['token']
        self.auth={'Authorization':'Bearer '+token}
        self.uid=self.beta.store.authenticate(token)['id']
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(self.app),base_url='http://test')
    async def asyncTearDown(self):
        await self.client.aclose();self.temp.cleanup()
    async def test_partial_conditional_save_preserves_language_and_client_mappings(self):
        old={'mode':'translate','target_language':'th','source_language':'en','word_replacements':'長灰 → 長輝','personal_prompt':'保留語氣','vocabulary':'舊詞','taiwan_places':False}
        await self.client.post('/v2/me/preferences',headers=self.auth,json=old)
        read=await self.client.get('/v2/me/preferences',headers=self.auth)
        saved=await self.client.patch('/v2/me/preferences',headers={**self.auth,'If-Match':read.headers['etag']},json={'vocabulary':'李孟一、DreamType'})
        self.assertEqual(saved.status_code,200)
        self.assertEqual(saved.json(),{**old,'vocabulary':'李孟一、DreamType'})
        self.assertNotEqual(saved.headers['etag'],read.headers['etag'])
    async def test_old_web_snapshot_cannot_overwrite_new_phone_preferences(self):
        read=await self.client.get('/v2/me/preferences',headers=self.auth)
        phone=await self.client.post('/v2/me/preferences',headers=self.auth,json={'vocabulary':'手機新增詞'})
        failed=await self.client.patch('/v2/me/preferences',headers={**self.auth,'If-Match':read.headers['etag']},json={'vocabulary':'舊網頁內容'})
        self.assertEqual(failed.status_code,412)
        self.assertEqual(failed.json()['error_code'],'preferences_conflict')
        self.assertEqual((await self.client.get('/v2/me/preferences',headers=self.auth)).json(),phone.json())
    async def test_atomic_store_rechecks_revision_after_api_read(self):
        snapshot=self.beta.store.me(self.uid)['preferences']
        self.beta.store.preferences(self.uid,{'vocabulary':'concurrent update'})
        with self.assertRaises(StoreError) as caught:
            self.beta.store.preferences(self.uid,{'vocabulary':'stale'},expected=preferences_etag(snapshot))
        self.assertEqual(caught.exception.status,412)
        self.assertEqual(self.beta.store.me(self.uid)['preferences']['vocabulary'],'concurrent update')
    async def test_invalid_update_is_atomic_and_unknown_fields_rejected(self):
        read=await self.client.get('/v2/me/preferences',headers=self.auth)
        for changes in ({'vocabulary':'a'*1001},{'uid':'another-user'},{'taiwan_places':'true'}):
            response=await self.client.patch('/v2/me/preferences',headers={**self.auth,'If-Match':read.headers['etag']},json=changes)
            self.assertEqual(response.status_code,400)
        current=await self.client.get('/v2/me/preferences',headers=self.auth)
        self.assertEqual(current.headers['etag'],read.headers['etag'])
    async def test_get_requires_account_authentication(self):
        self.assertEqual((await self.client.get('/v2/me/preferences')).status_code,401)
    async def test_partial_save_keeps_future_fields_it_does_not_edit(self):
        self.beta.store.preferences(self.uid,{'future_setting':{'enabled':True}})
        read=await self.client.get('/v2/me/preferences',headers=self.auth)
        self.assertEqual(read.headers['x-dreamtype-preferences-version'],read.headers['etag'])
        saved=await self.client.patch('/v2/me/preferences',headers={**self.auth,'If-Match':read.headers['etag']},json={'vocabulary':'新詞'})
        self.assertEqual(saved.status_code,200)
        self.assertEqual(saved.json()['future_setting'],{'enabled':True})

if __name__=='__main__':unittest.main()
