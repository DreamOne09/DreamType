"""Use fixture instrumentation to inspect every interactive Android window, including IME."""
import json
from pathlib import Path
import subprocess
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

uploads=[]
class SyntheticResponse(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        if self.path!='/v1/audio/transcriptions' or self.headers.get('Authorization')!='Bearer synthetic-emulator-token':
            self.send_error(403);return
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
        body=json.dumps({'text':'明天下午四點半到板橋。','warning':None,'mode':'organize','target_language':'zh-TW'}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

server=ThreadingHTTPServer(('127.0.0.1',18765),SyntheticResponse)
Thread(target=server.serve_forever,daemon=True).start()

out=Path('work/emulator-probe/screenshots')
out.mkdir(parents=True,exist_ok=True)
def adb(*args):return subprocess.run(['adb',*args],check=True,capture_output=True,timeout=90).stdout
try:
    adb('install','-t','work/emulator-probe/fixture.apk')
    configured=adb('shell','am','instrument','-w','-e','configure_voice','true','tw.localvoice.keyboard/.SmokeInstrumentation').decode('utf-8')
    if 'INSTRUMENTATION_RESULT: dreamtype=passed' not in configured:
        raise AssertionError(configured)
    adb('shell','pm','grant','tw.localvoice.keyboard','android.permission.RECORD_AUDIO')
    adb('shell','ime','enable','tw.localvoice.keyboard/.VoiceIme')
    adb('shell','ime','set','tw.localvoice.keyboard/.VoiceIme')
    adb('shell','settings','put','secure','show_ime_with_hard_keyboard','1')
    result=adb('shell','am','instrument','-w','tw.dreamtype.fixture/.ImeInstrumentation').decode('utf-8')
    Path('work/emulator-probe/ime-instrumentation.txt').write_text(result,encoding='utf-8')
    adb('pull','/sdcard/Android/data/tw.dreamtype.fixture/files',str(out/'ime'))
    if 'INSTRUMENTATION_RESULT: ime=passed' not in result or 'INSTRUMENTATION_CODE: -1' not in result:
        raise AssertionError(result)
    if len(uploads)!=1:raise AssertionError('Expected exactly one valid audio upload')
    report={'external_editor':True,'ime_visible':True,'password_voice_disabled':True,
            'normal_field_reenabled':True,'microphone_recording_tested':True,
            'text_insertion_tested':True,'pixel9_tested':False,
            'response_source':'synthetic HTTP fixture; no speech recognition',
            'speech_recognition_tested':False,'uploaded_audio_bytes':uploads}
    Path('work/emulator-probe/ime-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
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
