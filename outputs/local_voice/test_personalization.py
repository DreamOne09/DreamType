import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import unittest
from unittest.mock import patch
import httpx
import server
from personalization import formatting_prompt, speech_hint

class RequestIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://local')
        self.auth={'Authorization':'Bearer '+server.API_KEY}
    async def asyncTearDown(self):
        await self.client.aclose()
    async def test_two_users_do_not_share_preferences(self):
        calls=[]
        async def formatter(text, *prefs):
            calls.append((text,prefs));return text
        with patch.object(server,'format_text',formatter):
            for style,words in [('用條列','汐止'),('用完整段落','鹽埕')]:
                r=await self.client.post('/v1/chat/completions',headers=self.auth,json={'messages':[{'role':'user','content':'明天下午四點開會。'}],'personal_prompt':style,'vocabulary':words})
                self.assertEqual(r.status_code,200)
            await self.client.post('/v1/chat/completions',headers=self.auth,json={'messages':[{'role':'user','content':'不要取消。'}]})
        self.assertEqual(calls[0][1],('用條列','汐止',True))
        self.assertEqual(calls[1][1],('用完整段落','鹽埕',True))
        self.assertEqual(calls[2][1],('','',True))
    async def test_limits_and_auth(self):
        for body in [{'personal_prompt':'字'*2001},{'vocabulary':'字'*1001},{'taiwan_places':'false'}]:
            r=await self.client.post('/v1/chat/completions',headers=self.auth,json=body)
            self.assertEqual(r.status_code,400)
        r=await self.client.post('/v1/chat/completions',json={'personal_prompt':'private'})
        self.assertEqual(r.status_code,401)
    async def test_audio_preferences_and_fallback(self):
        seen=[]
        def recognize(audio,language,prompt):
            seen.append(prompt);return '明天去汐止。','zh'
        async def fail(*args):raise ValueError('offline')
        with patch.object(server,'decode_audio',lambda *a,**k: [0]*16000),patch.object(server,'recognize',recognize),patch.object(server,'format_text',fail):
            r=await self.client.post('/v1/audio/transcriptions',headers=self.auth,files={'file':('test.wav',b'fake')},data={'vocabulary':'汐止','personal_prompt':'條列','taiwan_places':'false'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['text'],'明天去汐止。')
        self.assertTrue(r.json()['warning'])
        self.assertIn('汐止',seen[0]);self.assertNotIn('臺北市',seen[0])

class PromptTests(unittest.TestCase):
    def test_place_switch_and_preserve_rules(self):
        self.assertIn('臺北市',formatting_prompt('base'))
        self.assertNotIn('臺北市',formatting_prompt('base',taiwan_places=False))
        self.assertIn('never force an ambiguous word',formatting_prompt('base'))
        self.assertIn('汐止',speech_hint('', '汐止'))
    def test_one_person_does_not_mutate_base(self):
        formatting_prompt('base','only-user-a','user-a-place')
        result=formatting_prompt('base')
        self.assertNotIn('user-a',result)

if __name__=='__main__':unittest.main()
