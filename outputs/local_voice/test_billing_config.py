import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from urllib.parse import parse_qs
import httpx
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from google.auth import jwt
from billing_config import load_billing,PlayCredentials,TOKEN_URI,SCOPE


def credential_fixture():
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    return {'type':'service_account','client_email':'play@fixture.iam.gserviceaccount.com','token_uri':TOKEN_URI,'private_key_id':'fixture',
            'private_key':key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode()}


class ConfigTests(unittest.TestCase):
    def test_malformed_disable_and_oversized_configuration_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            work=Path(d);path=work/'billing-config.json'
            for content in ('{"enabled":0}','{"enabled":null}','{"enabled":"false"}','x'*32769):
                path.write_text(content)
                with self.assertRaises(RuntimeError):load_billing(work)

    def test_slow_oauth_response_never_caches_access_token(self):
        creds=PlayCredentials(credential_fixture(),httpx.MockTransport(lambda r:httpx.Response(200,json={'access_token':'secret-fixture','expires_in':3600})))
        with patch('billing_config.time.monotonic',side_effect=[0,11]),self.assertRaisesRegex(ValueError,'^Play credentials unavailable$'):
            creds()
        self.assertIsNone(creds.credentials.token)
        self.assertTrue(creds.lock.acquire(blocking=False));creds.lock.release()

    def test_off_invalid_and_explicit_paid_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            work=Path(d);path=work/'billing-config.json'
            self.assertIsNone(load_billing(work))
            path.write_text('{"enabled":false}');self.assertIsNone(load_billing(work))
            config={'enabled':True,'products':[{'product_id':'fixture','base_plan_id':'monthly','plan':'pro','monthly_seconds':120}],
                    'push':{'audience':'https://dreamtype.dreamone.li/billing/google/play/notifications','email':'push@fixture.iam.gserviceaccount.com','subscription':'projects/fixture/subscriptions/play'},'credentials_file':'play.json'}
            (work/'play.json').write_text(json.dumps(credential_fixture()))
            path.write_text(json.dumps(config));runtime=load_billing(work)
            self.assertEqual(runtime.policy.catalog,{('fixture','monthly'):('pro',120)})
            for change in ({'credentials_file':'../private.json'},{'products':config['products']*2},{'enabled':'true'},{'unknown':True}):
                path.write_text(json.dumps({**config,**change}))
                with self.assertRaises(RuntimeError):load_billing(work)

    def test_google_oauth_scope_cache_and_fail_closed(self):
        calls=[]
        def respond(request):
            calls.append(request)
            assertion=parse_qs(request.content.decode())['assertion'][0]
            payload=jwt.decode(assertion,verify=False)
            self.assertEqual(payload['scope'],SCOPE)
            self.assertEqual(str(request.url),TOKEN_URI)
            return httpx.Response(200,json={'access_token':'synthetic-access','expires_in':3600,'token_type':'Bearer'})
        creds=PlayCredentials(credential_fixture(),httpx.MockTransport(respond))
        self.assertEqual(creds(),'synthetic-access');self.assertEqual(creds(),'synthetic-access')
        self.assertEqual(len(calls),1)
        bad=PlayCredentials(credential_fixture(),httpx.MockTransport(lambda r:httpx.Response(302,headers={'Location':'https://attacker.invalid'})))
        with self.assertRaisesRegex(ValueError,'^Play credentials unavailable$'):bad()


if __name__=='__main__':unittest.main()
