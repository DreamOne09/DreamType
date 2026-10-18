"""Real Chromium with isolated Google SDK/API fixtures, never a live credential."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ASSETS=Path(__file__).resolve().parents[1]/'outputs/local_voice'
ORIGIN='https://dreamtype.dreamone.li'
SDK="""window.proofs=[];window.google={accounts:{id:{
initialize(options){window.proofs.push(options)},
renderButton(target){const b=document.createElement('button');b.textContent='Fixture Google';b.onclick=()=>window.proofs.at(-1).callback({credential:'synthetic-proof'});target.append(b)}
}}};"""

def check(executable, output):
    errors=[]; calls=[]; scripts=[]; signup=False; disabled=False
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=executable,headless=True)
        context=browser.new_context(viewport={'width':360,'height':800})
        def route(request_route):
            nonlocal calls
            request=request_route.request;url=request.url
            if url=='https://accounts.google.com/gsi/client':
                scripts.append(url);request_route.fulfill(content_type='text/javascript',body=SDK);return
            if not url.startswith(ORIGIN+'/'):raise AssertionError(url)
            path=url[len(ORIGIN):]
            if not path.startswith('/v2/'):
                filename={'/':'dictate.html','/account':'account.html'}.get(path,path.removeprefix('/web/'))
                assert filename in ('dictate.html','account.html','dictate.mjs','web_dictation.mjs','google_account.mjs')
                request_route.fulfill(content_type='text/javascript' if filename.endswith('.mjs') else 'text/html; charset=utf-8',body=(ASSETS/filename).read_text(encoding='utf-8'));return
            calls.append(path);status=200;headers={}
            if '/google/' in path:
                assert request.headers.get('x-dreamtype-client')=='web'
                if request.method=='POST':assert request.headers.get('origin')==ORIGIN
            if path.endswith('/config'):
                data={'client_id':'123-test.apps.googleusercontent.com','signup_enabled':signup}
                if disabled:status=404;data={'detail':'disabled'}
            elif path.endswith('/challenge'):data={'challenge':'a'*32,'secret':'b'*43,'nonce':'c'*43,'expires_at':4102444800}
            elif path.endswith('/complete'):
                assert request.post_data_json['id_token']=='synthetic-proof'
                assert request.post_data_json['secret']=='b'*43
                if '/delete/' in path:
                    assert request.headers['authorization']=='Bearer '+'t'*43
                    assert request.post_data_json['confirm'] is True
                    data={'deleted':True,'subscription_cancelled':False}
                else:data={'token':'t'*43}
            elif path=='/v2/me':data={'name':'Google 測試','login_methods':['google'],'used_seconds':0,'limit_seconds':0,'remaining_seconds':0,'month_utc':'2026-10','preferences':{}}
            elif path=='/v2/me/preferences':data={'vocabulary':'新竹市','personal_prompt':'','taiwan_places':True};headers={'ETag':'"v1"'}
            elif path=='/v2/logout':data={'ok':True}
            else:raise AssertionError(path)
            request_route.fulfill(status=status,headers=headers,content_type='application/json',body=json.dumps(data))
        context.route('**/*',route)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(ORIGIN+'/account');assert not scripts
        page.get_by_role('button',name='使用 Google 帳號',exact=True).click()
        expect(page.get_by_role('button',name='登入現有 Google 帳號')).to_be_visible()
        assert page.get_by_role('button',name='建立新的 Google 帳號連結').count()==0
        page.get_by_role('button',name='登入現有 Google 帳號').click()
        page.get_by_role('button',name='Fixture Google').wait_for()
        assert page.evaluate('proofs[0].nonce')=='c'*43
        page.get_by_role('button',name='取消驗證').click()
        expect(page.locator('#status')).to_have_text('已取消 Google 驗證。')
        page.evaluate("proofs[0].callback({credential:'synthetic-proof'})")
        assert '/v2/auth/google/complete' not in calls
        page.get_by_role('button',name='使用 Google 帳號',exact=True).click()
        page.get_by_role('button',name='登入現有 Google 帳號').click()
        page.get_by_role('button',name='Fixture Google').click()
        expect(page.locator('#panel')).to_be_visible()
        assert page.locator('#password-delete').is_hidden()
        page.get_by_text('刪除我的帳號',exact=True).click()
        page.once('dialog',lambda d:d.dismiss())
        page.get_by_role('button',name='用 Google 再次驗證並刪除').click()
        expect(page.get_by_role('button',name='用 Google 再次驗證並刪除')).to_be_enabled()
        assert '/v2/me/google/delete/challenge' not in calls
        page.once('dialog',lambda d:d.accept())
        page.get_by_role('button',name='用 Google 再次驗證並刪除').click()
        page.get_by_role('button',name='Fixture Google').click()
        expect(page.locator('#signin')).to_be_visible()
        expect(page.locator('#status')).to_contain_text('帳號已永久刪除')
        assert page.evaluate('localStorage.length + sessionStorage.length')==0
        # Dictation tab uses the same flow and retains explicit signup selection.
        signup=True;page.goto(ORIGIN+'/')
        page.get_by_role('button',name='使用 Google 帳號',exact=True).click()
        page.get_by_role('button',name='建立新的 Google 帳號連結').click()
        page.get_by_role('button',name='Fixture Google').click()
        expect(page.locator('#workspace')).to_be_visible()
        expect(page.locator('#record')).to_be_enabled()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        output.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(output/'google-workspace-mobile.png'),full_page=True)
        page.get_by_role('button',name='登出',exact=True).click()
        expect(page.locator('#signin')).to_be_visible()
        assert page.evaluate('localStorage.length + sessionStorage.length')==0
        disabled=True;page.get_by_role('button',name='使用 Google 帳號',exact=True).click()
        expect(page.locator('#status')).to_contain_text('尚未開放')
        expect(page.locator('#login button')).to_be_enabled()
        assert not errors,errors
        browser.close()
    report={'passed':True,'real_google_acceptance':False,'checks':['lazy SDK','explicit signup','challenge nonce','cancel rejects late callback','Google-only deletion','deletion cancellation','dictation login and logout','unavailable fallback','memory only','mobile width'],'browser_errors':errors}
    (output/'google-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--browser');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();check(args.browser,args.output)
