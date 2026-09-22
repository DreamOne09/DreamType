"""Use fixture instrumentation to inspect every interactive Android window, including IME."""
import json
from pathlib import Path
import subprocess
import sys
import uuid
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

account='--account' in sys.argv
prefix='account-' if account else ''
uploads=[]
job={'id':None,'polls':0,'receipts':0}
class SyntheticResponse(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,body):
        payload=json.dumps(body).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    def authorized(self):return self.headers.get('Authorization')=='Bearer synthetic-emulator-token'
    def do_GET(self):
        if not account or not self.authorized() or self.path!='/v2/dictations/'+str(job['id']):
            self.send_error(404);return
        job['polls']+=1
        if job['polls']==1:self.reply({'id':job['id'],'state':'running'})
        else:self.reply({'id':job['id'],'state':'done','receipt_required':True,'text':'明天下午四點半到板橋。','mode':'organize','target_language':'zh-TW'})
    def do_POST(self):
        if not self.authorized():
            self.send_error(403);return
        if account and job['id'] and self.path=='/v2/dictations/'+job['id']+'/receipt':
            if job['polls']<2:self.send_error(409);return
            job['receipts']+=1;self.reply({'ok':True});return
        if self.path!=('/v2/dictations' if account else '/v1/audio/transcriptions'):
            self.send_error(404);return
        if account:
            expected={'X-DreamType-Receipt':'1','X-DreamType-Mode':'organize','X-DreamType-Source':'zh-TW','X-DreamType-Target':'en'}
            if any(self.headers.get(key)!=value for key,value in expected.items()):
                self.send_error(400);return
            try:job['id']=str(uuid.UUID(self.headers.get('Idempotency-Key','')))
            except ValueError:self.send_error(400);return
        size=int(self.headers.get('Content-Length','0'))
        if not 0<size<2*1024*1024:
            self.send_error(400);return
        content_type=self.headers.get('Content-Type','')
        message=BytesParser(policy=default).parsebytes(
            ('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+self.rfile.read(size))
        audio=[part.get_payload(decode=True) for part in message.iter_parts()
               if part.get_param('name',header='content-disposition')=='file']
        if len(audio)!=1 or len(audio[0])<100 or audio[0][4:8]!=b'ftyp':
            self.send_error(400);return
        uploads.append(len(audio[0]))
        if account:self.reply({'id':job['id'],'state':'queued','queue_size':1})
        else:self.reply({'text':'明天下午四點半到板橋。','warning':None,'mode':'organize','target_language':'zh-TW'})

server=ThreadingHTTPServer(('127.0.0.1',18765),SyntheticResponse)
Thread(target=server.serve_forever,daemon=True).start()

out=Path('work/emulator-probe/screenshots')/('account' if account else 'private')
out.mkdir(parents=True,exist_ok=True)
def adb(*args):return subprocess.run(['adb',*args],check=True,capture_output=True,timeout=90).stdout
try:
    adb('install','-t','work/emulator-probe/fixture.apk')
    # Self-instrumentation restarts the target process. Detach the previous IME
    # before reconfiguring, so the next case binds a fresh service instance.
    adb('shell','ime','reset')
    configured=adb('shell','am','instrument','-w','-e','configure_voice','true','-e','account_voice',str(account).lower(),'tw.localvoice.keyboard/.SmokeInstrumentation').decode('utf-8')
    if 'INSTRUMENTATION_RESULT: dreamtype=passed' not in configured:
        raise AssertionError(configured)
    adb('shell','pm','grant','tw.localvoice.keyboard','android.permission.RECORD_AUDIO')
    adb('shell','ime','enable','tw.localvoice.keyboard/.VoiceIme')
    adb('shell','ime','set','tw.localvoice.keyboard/.VoiceIme')
    adb('shell','settings','put','secure','show_ime_with_hard_keyboard','1')
    result=adb('shell','am','instrument','-w','tw.dreamtype.fixture/.ImeInstrumentation').decode('utf-8')
    Path('work/emulator-probe/'+prefix+'ime-instrumentation.txt').write_text(result,encoding='utf-8')
    adb('pull','/sdcard/Android/data/tw.dreamtype.fixture/files',str(out/'ime'))
    if 'INSTRUMENTATION_RESULT: ime=passed' not in result or 'INSTRUMENTATION_CODE: -1' not in result:
        raise AssertionError(result)
    if len(uploads)!=1:raise AssertionError('Expected exactly one valid audio upload')
    if account:
        if job['polls']!=2 or job['receipts']!=1:raise AssertionError('Expected running/done polling and exactly one receipt')
        delivered=adb('shell','am','instrument','-w','-e','verify_delivered','true','tw.localvoice.keyboard/.SmokeInstrumentation').decode('utf-8')
        Path('work/emulator-probe/'+prefix+'delivered.txt').write_text(delivered,encoding='utf-8')
        if 'INSTRUMENTATION_RESULT: delivered=passed' not in delivered or 'INSTRUMENTATION_CODE: -1' not in delivered:
            raise AssertionError(delivered)
    report={'external_editor':True,'ime_visible':True,'password_voice_disabled':True,
            'normal_field_reenabled':True,'microphone_recording_tested':True,
            'text_insertion_tested':True,'pixel9_tested':False,
            'response_source':'synthetic HTTP fixture; no speech recognition',
            'speech_recognition_tested':False,'uploaded_audio_bytes':uploads,
            'mode':'account' if account else 'private','queue_polling_tested':account,
            'receipts':job['receipts'],'delivered_recording_cleanup_tested':account,
            'login_ui_tested':False,'real_backend_tested':False}
    Path('work/emulator-probe/'+prefix+'ime-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
except Exception:
    for name,command in (
        ('ime-failure.png',('exec-out','screencap','-p')),
        ('ime-state.txt',('shell','dumpsys','input_method')),
        ('ime-log.txt',('shell','logcat','-d','-t','300'))):
        try:(out/name).write_bytes(adb(*command))
        except Exception:pass
    raise
finally:
    server.shutdown();server.server_close()
