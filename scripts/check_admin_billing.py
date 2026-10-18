"""Browser acceptance for paid/trial admin controls; no live service or keys."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ASSET=Path(__file__).resolve().parents[1]/'outputs/local_voice/admin.html'

def check(browser_path,output):
    output.mkdir(parents=True,exist_ok=True);errors=[];results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=browser_path,headless=True)
        for paid in (True,False):
            page=browser.new_page(viewport={'width':1100,'height':900});writes=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            user={'id':'fixture','name':'alice','enabled':True,'used_seconds':60,'reserved_seconds':0,'limit_seconds':120,'plan':'專業方案','entitlement_status':'verification_required'}
            def route_handler(route):
                request=route.request
                if '/v2/admin/' not in request.url:
                    route.fulfill(content_type='text/html',body=ASSET.read_text(encoding='utf-8'));return
                assert request.headers.get('authorization')=='Bearer isolated-admin-fixture'
                path=request.url.split('/v2/admin/')[1]
                if request.method!='GET':writes.append({'path':path,'body':request.post_data_json});data={'ok':True}
                elif path=='users':data={'users':[user],'billing_enabled':paid,'queue_size':0,'service_url':'https://dreamtype.dreamone.li','service_url_message':'固定網址'}
                elif path=='metrics':data={'worker_alive':True,'jobs_last_24h':{},'billing':{'state':'needs_attention' if paid else 'disabled','worker_alive':True,'counts':{'pending_ack':1,'stale':1},'alerts':[{'message':'<img src=x onerror=alert(1)>請重新查驗'}]}}
                else:raise AssertionError(path)
                route.fulfill(content_type='application/json',body=json.dumps(data))
            page.route('**/*',route_handler);page.goto('http://fixture.invalid/admin')
            page.locator('#key').fill('isolated-admin-fixture');page.locator('#connect').click()
            expect(page.locator('#panel')).to_be_visible()
            if paid:
                expect(page.locator('#minuteslabel')).to_be_hidden()
                expect(page.locator('#users')).to_contain_text('等待重新查驗')
                expect(page.locator('#users input[type=number]')).to_have_count(0)
                expect(page.locator('#health')).to_contain_text('請重新查驗')
                expect(page.locator('#health img')).to_have_count(0)
            else:
                expect(page.locator('#minuteslabel')).to_be_visible()
                page.locator('#users input[type=number]').fill('45')
            page.locator('#users input[type=checkbox]').uncheck()
            page.get_by_role('button',name='儲存',exact=True).click()
            expect(page.locator('#status')).to_have_text('已更新 alice')
            assert writes[-1]['body']==({'enabled':False} if paid else {'enabled':False,'minutes':45})
            page.locator('#name').fill('bobby');page.locator('#password').fill('synthetic-password')
            if not paid:page.locator('#minutes').fill('30')
            page.locator('#create button').click();expect(page.locator('#status')).to_contain_text('帳號已建立')
            assert writes[-1]['body']['minutes']==(0 if paid else 30)
            page.screenshot(path=str(output/('admin-paid.png' if paid else 'admin-trial.png')),full_page=True)
            page.locator('#logout').click();expect(page.locator('#panel')).to_be_hidden()
            assert page.evaluate('localStorage.length+sessionStorage.length')==0
            results.append({'mode':'paid' if paid else 'trial','writes':writes});page.close()
        browser.close()
    assert not errors,errors
    (output/'admin-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Paid/trial admin browser acceptance passed')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--browser');parser.add_argument('--output',type=Path,default=Path('work/admin-browser'))
    args=parser.parse_args();check(args.browser,args.output)
