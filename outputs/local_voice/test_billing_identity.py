import time
import unittest
from unittest.mock import patch
import httpx
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from google.auth import crypt,jwt
from billing_identity import Certificates,google_identity


class IdentityTests(unittest.TestCase):
    def test_slow_certificate_response_is_not_cached_and_lock_is_released(self):
        certs=Certificates(httpx.MockTransport(lambda request:httpx.Response(200,content=b'{}')))
        with patch('billing_identity.time.monotonic',side_effect=[0,11]),self.assertRaisesRegex(ValueError,'deadline'):
            certs('https://www.googleapis.com/oauth2/v1/certs')
        self.assertIsNone(certs.cached)
        self.assertTrue(certs.lock.acquire(blocking=False));certs.lock.release()

    def test_real_signature_expiry_issuer_audience_and_cache(self):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        pem=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        calls=[]
        def respond(request):
            calls.append(request.url)
            return httpx.Response(200,json={'fixture-key':public})
        certs=Certificates(httpx.MockTransport(respond));signer=crypt.RSASigner.from_string(pem,key_id='fixture-key')
        payload={'iss':'https://accounts.google.com','aud':'https://fixture.invalid/push','iat':int(time.time())-1,'exp':int(time.time())+3600,'email':'push@fixture.iam.gserviceaccount.com','email_verified':True}
        token=jwt.encode(signer,payload).decode()
        self.assertEqual(google_identity(token,payload['aud'],certs)['email'],payload['email'])
        for changes in ({'iss':'https://attacker.invalid'},{'aud':'wrong'},{'exp':int(time.time())-10},{'iat':int(time.time())+10000}):
            with self.assertRaises(Exception):google_identity(jwt.encode(signer,{**payload,**changes}).decode(),payload['aud'],certs)
        parts=token.split('.');parts[2]=('A' if parts[2][0]!='A' else 'B')+parts[2][1:]
        with self.assertRaises(Exception):google_identity('.'.join(parts),payload['aud'],certs)
        self.assertEqual(len(calls),1)

    def test_certificate_redirect_and_size_are_rejected(self):
        for response in (httpx.Response(302,headers={'Location':'https://attacker.invalid'}),httpx.Response(200,content=b'x'*262145)):
            certs=Certificates(httpx.MockTransport(lambda request:response))
            with self.assertRaises(ValueError):certs('https://www.googleapis.com/oauth2/v1/certs')
        with self.assertRaises(ValueError):Certificates()('https://attacker.invalid')


if __name__=='__main__':unittest.main()
