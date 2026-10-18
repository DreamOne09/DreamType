"""Real Chromium UI checks with synthetic microphone and isolated fake API.

Requires playwright and a Chromium executable; never contacts the live service.
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'outputs/local_voice'

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        name={'/':'dictate.html','/web/dictate.mjs':'dictate.mjs','/web/web_dictation.mjs':'web_dictation.mjs'}.get(self.path)
        if not name:self.send_error(404);return
        content=(ASSETS/name).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type','text/javascript' if name.endswith('mjs') else 'text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(content)))
        self.end_headers();self.wfile.write(content)

def check(executable,output):
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    Thread(target=server.serve_forever,daemon=True).start()
    uploads=[];receipts=[];errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=executable,headless=True,args=['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
            page=browser.new_page(viewport={'width':1000,'height':900})
            page.on('pageerror',lambda error:errors.append(str(error)))
            def api(route):
                request=route.request;path=request.url.split('/v2/')[1];status=200
                if path=='login':data={'token':'isolated-browser-test-token'}
                elif path=='me':data={'name':'測試帳號','remaining_seconds':1800,'preferences':{}}
                elif path=='dictations':
                    uploads.append({'id':request.headers['idempotency-key'],'body':request.post_data_buffer,'target':request.headers['x-dreamtype-target']})
                    if len(uploads)==1:status=503;data={'detail':'模擬上傳回應中斷，請重試同一筆。'}
                    else:data={'id':uploads[-1]['id'],'state':'queued'}
                elif path.endswith('/receipt'):
                    receipts.append(path)
                    if len(receipts)==1:status=503;data={'detail':'模擬收件確認失敗'}
                    else:data={'ok':True}
                elif path.startswith('dictations/'):
                    data={'id':uploads[-1]['id'],'state':'done','mode':'translate','target_language':'ja','text':'明日、計画を確認します。','raw_text':'明天確認計畫。','receipt_required':True}
                elif path=='logout':data={'ok':True}
                else:raise AssertionError('Unexpected API '+path)
                route.fulfill(status=status,content_type='application/json',body=json.dumps(data))
            page.route('**/v2/**',api)
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            page.locator('#username').fill('test');page.locator('#password').fill('test-password')
            page.get_by_role('button',name='登入開始').click()
            try:page.locator('#workspace').wait_for(state='visible',timeout=10000)
            except Exception:
                print(json.dumps({'status':page.locator('#status').inner_text(),'errors':errors},ensure_ascii=True));raise
            page.locator('#mode').select_option('translate');page.locator('#target').select_option('ja')
            page.locator('#record').click();page.get_by_text('正在錄音，再按一次就會停止。',exact=True).wait_for()
            page.wait_for_timeout(1200);page.locator('#record').click()
            page.get_by_text('模擬上傳回應中斷，請重試同一筆。',exact=True).wait_for()
            page.locator('#retry').click();page.locator('#result').wait_for(state='visible')
            page.locator('#receipt').wait_for(state='visible')
            assert page.locator('#text').input_value()=='明日、計画を確認します。'
            assert page.locator('#record').is_disabled()
            assert len(uploads)==2 and uploads[0]['id']==uploads[1]['id']
            # Multipart boundaries differ; the audio payload and settings do not.
            audio=lambda body:body.split(b'\r\n\r\n',1)[1].rsplit(b'\r\n--',1)[0]
            assert audio(uploads[0]['body'])==audio(uploads[1]['body']) and len(audio(uploads[0]['body']))>100
            assert uploads[0]['target']==uploads[1]['target']=='ja'
            page.locator('#receipt').click();page.locator('#receipt').wait_for(state='hidden')
            assert page.locator('#record').is_enabled()
            page.locator('#erase').click();assert page.locator('#text').input_value()==''
            page.locator('#undo').click();assert page.locator('#text').input_value()=='明日、計画を確認します。'
            page.get_by_text('辨識原文',exact=True).click();page.locator('#restore').click()
            assert page.locator('#text').input_value()=='明天確認計畫。'
            output.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(output/'desktop.png'),full_page=True)
            page.set_viewport_size({'width':360,'height':800})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(output/'mobile.png'),full_page=True)
            page.locator('#record').click();page.get_by_text('正在錄音，再按一次就會停止。',exact=True).wait_for()
            page.locator('#cancel').click();page.get_by_text('已取消，沒有上傳這次錄音。',exact=True).wait_for()
            assert len(uploads)==2
            page.locator('#logout').click();page.locator('#signin').wait_for(state='visible')
            assert page.locator('#text').input_value()==''
            assert page.evaluate('localStorage.length + sessionStorage.length')==0
            assert not errors,errors
            browser.close()
        report={'passed':True,'synthetic_microphone':True,'live_service_contacted':False,'upload_attempts':len(uploads),'receipt_attempts':len(receipts),'browser_errors':errors,'checks':['login','record-stop','idempotent retry','translation snapshot','receipt retry','erase-undo','raw restore','mobile overflow','cancel without upload','logout erasure','no browser storage']}
        (output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
    finally:server.shutdown();server.server_close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--browser');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    check(args.browser,args.output)
