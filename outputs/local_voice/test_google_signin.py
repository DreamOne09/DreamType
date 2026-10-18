import time
import unittest
import httpx
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from google.auth import crypt,jwt
from billing_identity import Certificates
from google_signin import GoogleSignIn,GoogleSubject

class GoogleSignInTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        pem=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        cls.signer=crypt.RSASigner.from_string(pem,key_id='login-fixture')
        cls.public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()

    def setUp(self):
        self.calls=[]
        def response(request):
            self.calls.append(str(request.url))
            return httpx.Response(200,json={'login-fixture':self.public})
        self.client='web-fixture.apps.googleusercontent.com'
        self.android='android-fixture.apps.googleusercontent.com'
        self.nonce='n'*43
        self.verifier=GoogleSignIn(self.client,[self.android],Certificates(httpx.MockTransport(response)))
        self.claims={'iss':'https://accounts.google.com','aud':self.client,'sub':'google-stable-subject',
                     'iat':int(time.time())-1,'exp':int(time.time())+3600,'nonce':self.nonce}

    def token(self,changes=None):
        return jwt.encode(self.signer,{**self.claims,**(changes or {})}).decode()

    def test_identity_uses_subject_never_email_or_display_name(self):
        first=self.verifier.verify(self.token({'email':'old@example.invalid','name':'Old'}),self.nonce)
        second=self.verifier.verify(self.token({'email':'new@example.invalid','name':'New','email_verified':False}),self.nonce)
        self.assertEqual(first,GoogleSubject('google-stable-subject'))
        self.assertEqual(first,second)
        self.assertFalse(hasattr(first,'email'))
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.verifier.verify(self.token({'azp':self.android}),self.nonce),first)

    def test_wrong_app_nonce_issuer_time_and_subject_are_rejected(self):
        for changes in ({'aud':'other.apps.googleusercontent.com'},{'iss':'https://attacker.invalid'},
                        {'azp':'other.apps.googleusercontent.com'},{'nonce':'x'*43},{'nonce':None},
                        {'iat':int(time.time())-301},{'iat':int(time.time())+10},
                        {'exp':int(time.time())-1},{'sub':''},{'sub':'x'*256},{'sub':'bad\nsubject'},
                        {'iat':True},{'exp':float(time.time()+60)}):
            with self.subTest(changes=changes),self.assertRaisesRegex(ValueError,'proof invalid or unavailable'):
                self.verifier.verify(self.token(changes),self.nonce)

    def test_untrusted_input_is_bounded_before_certificate_fetch(self):
        for token,nonce in [('x'*16385,self.nonce),('非英文',self.nonce),(None,self.nonce),
                            (self.token(),'short'),(self.token(),None)]:
            with self.assertRaises(ValueError):self.verifier.verify(token,nonce)
        self.assertEqual(self.calls,[])
        parts=self.token().split('.');parts[2]=('A' if parts[2][0]!='A' else 'B')+parts[2][1:]
        with self.assertRaises(ValueError):self.verifier.verify('.'.join(parts),self.nonce)

    def test_configuration_does_not_accept_arbitrary_audience_or_presenter(self):
        for client,presenters in [('https://fixture.invalid',()),(self.client,['https://attacker.invalid']),
                                  (self.client,self.android),(None,()),(self.client,[self.android]*11)]:
            with self.assertRaises(ValueError):GoogleSignIn(client,presenters)

if __name__=='__main__':unittest.main()
