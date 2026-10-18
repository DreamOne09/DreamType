import json
import tempfile
import unittest
from pathlib import Path
from service_address import admin_address, fixed_address

class ServiceAddressTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.work=Path(self.temp.name)
        (self.work/'logs').mkdir()
        (self.work/'logs/tunnel.err.log').write_text('https://obsolete.trycloudflare.com')
    def tearDown(self):self.temp.cleanup()
    def write(self,name,data):
        (self.work/name).write_text(json.dumps(data),encoding='utf-8')
    def test_fixed_config_wins_over_old_logs_and_published_temporary_address(self):
        self.write('endpoint-discovery.json',{'public_url':'https://dreamtype.dreamone.li'})
        self.write('endpoint-published.json',{'url':'https://old.trycloudflare.com','checked_at':100,'expires':1000})
        result=admin_address(self.work,now=200)
        self.assertEqual(result['service_url'],'https://dreamtype.dreamone.li')
        self.assertEqual(result['service_url_source'],'configured_fixed')
    def test_named_without_address_never_suggests_old_temporary_url(self):
        self.write('tunnel-config.json',{'mode':'named'})
        with self.assertRaises(ValueError):fixed_address(self.work)
        self.assertEqual(admin_address(self.work)['service_url'],'')
    def test_logs_alone_are_not_current_evidence(self):
        self.assertEqual(admin_address(self.work)['service_url'],'')
    def test_temporary_requires_unexpired_bounded_publication(self):
        self.write('endpoint-published.json',{'url':'https://recent.trycloudflare.com','checked_at':100,'expires':1000})
        self.assertEqual(admin_address(self.work,200)['service_url'],'https://recent.trycloudflare.com')
        self.assertEqual(admin_address(self.work,1000)['service_url'],'')
        self.assertEqual(admin_address(self.work,99)['service_url'],'')
        self.write('endpoint-published.json',{'url':'https://recent.trycloudflare.com','checked_at':100,'expires':999999})
        self.assertEqual(admin_address(self.work,200)['service_url'],'')
    def test_invalid_fixed_config_fails_closed(self):
        for data in ([],{'public_url':'https://evil.example'},{'public_url':'https://old.trycloudflare.com'},{'public_url':'https://dreamtype.dreamone.li/path'},{'public_url':None}):
            with self.subTest(data=data):
                self.write('endpoint-discovery.json',data)
                self.assertEqual(admin_address(self.work)['service_url'],'')
                with self.assertRaises(ValueError):fixed_address(self.work)
    def test_utf8_bom_configuration_is_supported(self):
        (self.work/'endpoint-discovery.json').write_text('{"public_url":"https://dreamtype.dreamone.li"}',encoding='utf-8-sig')
        self.assertEqual(fixed_address(self.work),'https://dreamtype.dreamone.li')

class AdminAddressApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_route_uses_trusted_config_not_request_host(self):
        import httpx
        from fastapi import FastAPI
        from beta_api import install_beta
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory)
            (work/'endpoint-discovery.json').write_text('{"public_url":"https://dreamtype.dreamone.li"}')
            app=FastAPI();beta=install_beta(app,work,None,lambda audio:1)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://untrusted.example') as client:
                self.assertEqual((await client.get('/v2/admin/users')).status_code,401)
                response=await client.get('/v2/admin/users',headers={'Authorization':'Bearer '+beta.admin,'X-Forwarded-Host':'wrong.example'})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['service_url'],'https://dreamtype.dreamone.li')
                self.assertEqual(response.json()['service_url_source'],'configured_fixed')

if __name__=='__main__':unittest.main()
