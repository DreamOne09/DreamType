"""Disposable real beta API/SQLite for native CI. Only the AI provider is synthetic."""
import asyncio
import math
from pathlib import Path
import secrets
import ssl
import socket
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'outputs/local_voice'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from beta_api import install_beta, audio_duration


class BackendFixture:
    def __init__(self,interruptions=False):
        self.temporary=tempfile.TemporaryDirectory(prefix='dreamtype-native-')
        self.calls=[]
        self.interruptions=interruptions
        self.dropped=set()
        owner=self
        class Provider:
            async def transcribe(self,audio,prefs):
                owner.calls.append({'bytes':len(audio),'seconds':audio_duration(audio),'source':prefs['source_language']})
                await asyncio.sleep(1.5)
                return {'text':'明天下午四點半到板橋。','mode':'organize','target_language':'zh-TW'}
        app=FastAPI()
        self.beta=install_beta(app,Path(self.temporary.name),Provider(),audio_duration)
        self.client=TestClient(app)
        self.client.__enter__()
        self.password=password=secrets.token_urlsafe(24)
        created=self.client.post('/v2/admin/users',headers={'Authorization':'Bearer '+self.beta.admin},json={'username':'native-fixture','password':password,'minutes':10})
        created.raise_for_status();self.uid=created.json()['id']
        self.requests=[]
        class Bridge(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def forward(self):
                length=int(self.headers.get('Content-Length','0'))
                if not 0<=length<=2*1024*1024+65536:self.send_error(413);return
                # Preserve Android authorization, receipt, language and request ID headers.
                headers={key:value for key,value in self.headers.items() if key.lower() not in ('host','connection')}
                response=owner.client.request(self.command,self.path,headers=headers,content=self.rfile.read(length))
                owner.requests.append((self.command,self.path,response.status_code))
                phase='poll' if self.command=='GET' and self.path.startswith('/v2/dictations/') else 'receipt' if self.command=='POST' and self.path.endswith('/receipt') else None
                # Process the request first, then lose its HTTP response over TLS.
                # In the receipt case this deliberately loses a committed acknowledgement.
                if owner.interruptions and phase and phase not in owner.dropped and response.status_code==200:
                    owner.dropped.add(phase);self.close_connection=True
                    try:self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:pass
                    self.connection.close();return
                self.send_response(response.status_code)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(response.content)))
                self.end_headers();self.wfile.write(response.content)
            do_GET=forward
            do_POST=forward
        self.server=ThreadingHTTPServer(('127.0.0.1',18765),Bridge)
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain('work/emulator-probe/tls-cert.pem','work/emulator-probe/tls-key.pem')
        self.server.socket=tls.wrap_socket(self.server.socket,server_side=True)

    def verify(self):
        if len(self.calls)!=1 or self.calls[0]['source']!='zh-TW':raise AssertionError('Expected one Taiwan-Chinese provider call')
        with self.beta.store.db() as db:
            jobs=db.execute('SELECT * FROM jobs WHERE uid=?',(self.uid,)).fetchall()
            receipts=db.execute('SELECT confirmed FROM receipts WHERE uid=?',(self.uid,)).fetchall()
        if len(jobs)!=1 or jobs[0]['state']!='done':raise AssertionError('Expected one completed job')
        if len(receipts)!=1 or receipts[0]['confirmed']!=1:raise AssertionError('Missing confirmed receipt')
        expected=math.ceil(self.calls[0]['seconds'])
        me=self.beta.store.me(self.uid)
        if me['used_seconds']!=expected or me['reserved_seconds']!=0:raise AssertionError('Quota differs from decoded recording')
        uploads=[r for r in self.requests if r[:2]==('POST','/v2/dictations')]
        acknowledgements=[r for r in self.requests if r[0]=='POST' and r[1].endswith('/receipt')]
        if len(uploads)!=1 or len(acknowledgements)!=(2 if self.interruptions else 1):raise AssertionError('Unexpected duplicate upload or receipt')
        if self.interruptions and self.dropped!={'poll','receipt'}:raise AssertionError('Both response losses must occur')
        logins=[r[2] for r in self.requests if r[:2]==('POST','/v2/login')]
        if logins!=[401,200]:raise AssertionError('Expected rejected password then successful UI login')
        if any(r[2]>=400 and r!=('POST','/v2/login',401) for r in self.requests):raise AssertionError('Backend request failed')
        return {'provider_calls':1,'decoded_seconds':self.calls[0]['seconds'],'charged_seconds':expected,
                'uploaded_audio_bytes':[self.calls[0]['bytes']],'receipts':1,'sqlite_job_done':True,
                'quota_matches_decoded_audio':True,'login_api_tested':True,'login_ui_tested':True,'login_rejection_tested':True,'https_tested':True,
                'response_losses':sorted(self.dropped),'receipt_requests':len(acknowledgements),'audio_upload_requests':len(uploads)}

    def close(self):
        self.client.__exit__(None,None,None)
        self.temporary.cleanup()
