"""Browser checks for personal settings; isolated API, no live accounts."""
import argparse
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright, expect
from check_web_workspace import Handler, ASSETS

class AccountHandler(Handler):
    def do_GET(self):
        if self.path!='/account':return super().do_GET()
        data=(ASSETS/'account.html').read_bytes()
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

def check(browser_path,output):
    server=ThreadingHTTPServer(('127.0.0.1',0),AccountHandler)
    Thread(target=server.serve_forever,daemon=True).start()
    prefs={'vocabulary':'原本詞庫','personal_prompt':'保留語氣','taiwan_places':True}
    version='"first"';saves=[];errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=browser_path,headless=True)
            page=browser.new_page(viewport={'width':1000,'height':900})
            page.on('pageerror',lambda e:errors.append(str(e)))
            def api(route):
                nonlocal version,prefs
                request=route.request;path=request.url.split('/v2/')[1];status=200;headers={}
                if path=='login':data={'token':'isolated-preferences-test'}
                elif path=='me':data={'name':'測試帳號','used_seconds':0,'limit_seconds':3600,'remaining_seconds':3600,'month_utc':'2026-10'}
                elif path=='me/preferences':
                    if request.method=='PATCH':
                        saves.append({'body':request.post_data_json,'version':request.headers.get('if-match')})
                        if len(saves)==1:
                            version='"phone-update"';prefs={**prefs,'vocabulary':'手機新增詞'}
                            status=412;data={'detail':'設定已在其他裝置更新。','error_code':'preferences_conflict'}
                        else:
                            assert request.headers['if-match']==version
                            prefs={**prefs,**request.post_data_json};version='"saved"';data=prefs
                    else:data=prefs
                    # A proxy may weaken ETag; the application version must be used intact.
                    headers={'ETag':'W/'+version,'X-DreamType-Preferences-Version':version}
                elif path=='logout':data={'ok':True}
                else:raise AssertionError(path)
                route.fulfill(status=status,content_type='application/json',headers=headers,body=json.dumps(data))
            page.route('**/v2/**',api)
            page.goto(f'http://127.0.0.1:{server.server_port}/account')
            page.locator('#username').fill('test');page.locator('#password').fill('synthetic-password')
            page.locator('#login button').click();page.locator('#panel').wait_for(state='visible')
            page.locator('#preferences summary').click()
            page.locator('#vocabulary').fill('李孟一、DreamType');page.locator('#personal_prompt').fill('重點條列，其餘按意思分段。')
            page.locator('#prefsform button[type=submit]').click()
            expect(page.locator('#prefsstatus')).to_contain_text('其他裝置已更新')
            assert page.locator('#vocabulary').input_value()=='李孟一、DreamType'
            page.locator('#refresh').click();expect(page.locator('#status')).to_have_text('用量已更新')
            assert page.locator('#vocabulary').input_value()=='李孟一、DreamType'
            page.once('dialog',lambda dialog:dialog.dismiss());page.locator('#reloadprefs').click()
            assert page.locator('#vocabulary').input_value()=='李孟一、DreamType'
            page.once('dialog',lambda dialog:dialog.accept());page.locator('#reloadprefs').click()
            expect(page.locator('#vocabulary')).to_have_value('手機新增詞')
            page.locator('#vocabulary').fill('手機新增詞、李孟一、DreamType')
            page.locator('#prefsform button[type=submit]').click()
            expect(page.locator('#prefsstatus')).to_have_text('已儲存，下一筆錄音生效。')
            assert set(saves[-1]['body'])=={'vocabulary','personal_prompt','taiwan_places'}
            assert saves[0]['version']=='"first"' and saves[-1]['version']=='"phone-update"'
            output.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(output/'preferences-desktop.png'),full_page=True)
            page.set_viewport_size({'width':360,'height':800})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(output/'preferences-mobile.png'),full_page=True)
            page.locator('#vocabulary').fill('尚未儲存')
            page.once('dialog',lambda dialog:dialog.dismiss());page.locator('#logout').click()
            assert page.locator('#panel').is_visible()
            page.once('dialog',lambda dialog:dialog.accept());page.locator('#logout').click()
            page.locator('#signin').wait_for(state='visible')
            assert page.locator('#vocabulary').input_value()==''
            assert page.evaluate('localStorage.length + sessionStorage.length')==0
            assert not errors,errors
            browser.close()
        report={'passed':True,'live_service_contacted':False,'checks':['conflict preserves draft','usage refresh preserves draft','reload confirmation','conditional partial save','proxy-safe revision','unsaved logout confirmation','logout erasure','mobile width'],'browser_errors':errors}
        (output/'preferences-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
    finally:server.shutdown();server.server_close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--browser');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    check(args.browser,args.output)
