"""Google's verifier with a bounded, cached public-certificate transport."""
import threading
import time
from types import SimpleNamespace
import httpx

CERTS='https://www.googleapis.com/oauth2/v1/certs'


class Certificates:
    def __init__(self,transport=None):
        self.transport=transport;self.lock=threading.Lock();self.cached=None;self.until=0

    def __call__(self,url,method='GET',**kwargs):
        if url!=CERTS or method!='GET':raise ValueError('Unexpected certificate endpoint')
        if not self.lock.acquire(timeout=10):raise ValueError('Certificate verification busy')
        try:
            if self.cached is not None and time.monotonic()<self.until:return self.cached
            deadline=time.monotonic()+10
            with httpx.Client(timeout=10,trust_env=False,follow_redirects=False,transport=self.transport) as client:
                with client.stream('GET',CERTS) as response:
                    if response.status_code!=200:raise ValueError('Certificate service unavailable')
                    body=bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic()>deadline:raise ValueError('Certificate response deadline')
                        body.extend(chunk)
                        if len(body)>262144:raise ValueError('Certificate response too large')
            if time.monotonic()>deadline:raise ValueError('Certificate response deadline')
            self.cached=SimpleNamespace(status=200,data=bytes(body))
            self.until=time.monotonic()+300
            return self.cached
        finally:self.lock.release()


certificates=Certificates()


def google_identity(token,audience,request=certificates):
    from google.oauth2.id_token import verify_oauth2_token
    return verify_oauth2_token(token,request,audience=audience)
