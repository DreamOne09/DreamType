import unittest
import httpx
from fastapi import FastAPI
from web_pages import install_web_pages

class WebPagesTests(unittest.IsolatedAsyncioTestCase):
    async def test_workspace_and_modules_are_public_but_never_cached_or_framed(self):
        app=FastAPI();install_web_pages(app)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://test') as client:
            for path in ('/','/dictate','/web/dictate.mjs','/web/web_dictation.mjs','/web/google_account.mjs'):
                result=await client.get(path)
                self.assertEqual(result.status_code,200)
                self.assertEqual(result.headers['cache-control'],'no-store')
                self.assertIn("frame-ancestors 'none'",result.headers['content-security-policy'])
                self.assertEqual(result.headers['content-security-policy'].split('script-src ')[1].split(';')[0], "'self' https://accounts.google.com/gsi/client")
                self.assertNotIn('unsafe-inline',result.headers['content-security-policy'].split('script-src')[1].split(';')[0])
                if path.endswith('.mjs'):self.assertIn('text/javascript',result.headers['content-type'])
            self.assertEqual((await client.get('/web/local-voice.key')).status_code,404)

if __name__=='__main__':unittest.main()
