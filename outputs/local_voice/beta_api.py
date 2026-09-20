"""Invitation-only multi-user API. One process owns a bounded FIFO inference queue."""
import asyncio
import hashlib
import json
import math
import re
import secrets
import time
import io
from contextlib import asynccontextmanager
from collections import deque
from pathlib import Path
import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from beta_store import Store, StoreError
from personalization import validate_preferences

def audio_duration(data):
    """Decode frames incrementally; stop long/compressed recordings before allocating PCM."""
    import av
    seconds=0
    with av.open(io.BytesIO(data)) as container:
        for frame in container.decode(audio=0):
            seconds+=frame.samples/frame.sample_rate
            if seconds>120:return seconds
    return seconds

async def object_body(request):
    try:body=await request.json()
    except (ValueError,UnicodeDecodeError):raise StoreError(400,'無效的 JSON 格式')
    if not isinstance(body,dict):raise StoreError(400,'請使用 JSON 物件')
    return body

class LocalProvider:
    """Replace this adapter to migrate inference without changing the phone API."""
    def __init__(self,url,key):self.url,self.key=url,key
    async def transcribe(self,audio,prefs):
        async with httpx.AsyncClient(timeout=100) as client:
            r=await client.post(self.url+'/v1/audio/transcriptions',headers={'Authorization':'Bearer '+self.key},
                files={'file':('voice.m4a',audio,'application/octet-stream')},data={'model':'local-dictation',**prefs})
            r.raise_for_status();return r.json()

class Beta:
    def __init__(self,work,provider,decoder):
        self.store=Store(work/'beta/accounts.sqlite3');self.provider,self.decoder=provider,decoder
        path=work/'beta/admin.key'
        if not path.exists():path.write_text(secrets.token_urlsafe(32),encoding='ascii')
        self.admin=path.read_text().strip()
        self.queue=asyncio.Queue(maxsize=8);self.results={};self.tasks=[];self.logins=deque()
        self.login_slots=asyncio.Semaphore(2)
    async def start(self):
        self.store.recover()
        self.tasks=[asyncio.create_task(self.worker()),asyncio.create_task(self.expire())]
    async def stop(self):
        for task in self.tasks:task.cancel()
        await asyncio.gather(*self.tasks,return_exceptions=True)
        self.store.recover();self.results.clear()
    async def expire(self):
        while True:
            await asyncio.sleep(30)
            now=time.time()
            self.results={k:v for k,v in self.results.items() if v['expires']>now}
    async def worker(self):
        while True:
            uid,jid,audio,prefs=await self.queue.get()
            try:
                if not self.store.me(uid)['enabled']:raise ValueError('disabled')
                self.store.state(uid,jid,'running')
                result=await self.provider.transcribe(audio,prefs)
                if not self.store.me(uid)['enabled']:raise ValueError('disabled')
                if not isinstance(result.get('text'),str):raise ValueError('Invalid response')
                self.store.state(uid,jid,'done')
                self.results[(uid,jid)]={'result':result,'expires':time.time()+900}
            except asyncio.CancelledError:
                self.store.state(uid,jid,'failed');raise
            except Exception:
                self.store.state(uid,jid,'failed')
            finally:self.queue.task_done()
    def user(self,request):
        token=request.headers.get('authorization','').removeprefix('Bearer ')
        return self.store.authenticate(token)
    def admin_check(self,request):
        if not secrets.compare_digest(request.headers.get('authorization',''),'Bearer '+self.admin):raise StoreError(401,'需要管理者金鑰')
    def progress(self,uid,jid):
        row=self.store.job(uid,jid);result={'id':jid,'state':row['state'],'queue_size':self.queue.qsize()}
        stored=self.results.get((uid,jid))
        if stored and stored['expires']>time.time():result.update(stored['result'])
        elif row['state']=='done':result.update(state='expired',message='結果已過期或服務重啟；請勿自動重送錄音')
        if row['state']=='failed':result['message']='處理失敗或服務重啟，這次未扣額度。可重新錄音。'
        return result

def install_beta(app,work,provider,decoder):
    beta=Beta(work,provider,decoder)
    previous=app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        async with previous(application):
            await beta.start()
            try:yield
            finally:await beta.stop()
    app.router.lifespan_context=lifespan
    @app.exception_handler(StoreError)
    async def store_error(request,error):return JSONResponse({'detail':error.message},status_code=error.status)
    @app.middleware('http')
    async def beta_guard(request,call_next):
        if request.url.path.startswith('/v2/'):
            try:
                length=int(request.headers.get('content-length','0'))
                cap=2*1024*1024+65536 if request.url.path=='/v2/dictations' else 16384
                if length<0:return JSONResponse({'detail':'無效請求'},status_code=400)
                if length>cap:return JSONResponse({'detail':'請求太大'},status_code=413)
                if request.method in ('POST','PATCH','DELETE') and 'content-length' not in request.headers:return JSONResponse({'detail':'需要 Content-Length'},status_code=411)
                if request.url.path.startswith('/v2/admin/'):
                    beta.admin_check(request)
                elif request.url.path!='/v2/login':beta.user(request)
                if request.method in ('POST','PATCH','DELETE'):
                    chunks=[];received=0
                    async for chunk in request.stream():
                        received+=len(chunk)
                        if received>cap:return JSONResponse({'detail':'請求太大'},status_code=413)
                        chunks.append(chunk)
                    request._body=b''.join(chunks)
            except StoreError as e:return JSONResponse({'detail':e.message},status_code=e.status)
            except ValueError:return JSONResponse({'detail':'無效請求'},status_code=400)
        response=await call_next(request)
        if request.url.path.startswith(('/v2/','/admin','/account')):
            response.headers['Cache-Control']='no-store'
            response.headers['X-Content-Type-Options']='nosniff'
            response.headers['Referrer-Policy']='no-referrer'
            response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"
        return response
    @app.get('/admin')
    async def admin_page():return FileResponse(Path(__file__).with_name('admin.html'))
    @app.get('/account')
    async def account_page():return FileResponse(Path(__file__).with_name('account.html'))
    @app.post('/v2/login')
    async def login(request:Request):
        now=time.monotonic()
        while beta.logins and beta.logins[0]<now-60:beta.logins.popleft()
        if len(beta.logins)>=20:raise StoreError(429,'登入嘗試太頻繁，請一分鐘後重試')
        beta.logins.append(now)
        body=await object_body(request)
        async with beta.login_slots:return await asyncio.to_thread(beta.store.login,body.get('username',''),body.get('password',''))
    @app.post('/v2/logout')
    async def logout(request:Request):
        beta.store.logout(request.headers.get('authorization','').removeprefix('Bearer '));return {'ok':True}
    @app.get('/v2/me')
    async def me(request:Request):return beta.store.me(beta.user(request)['id'])
    @app.get('/v2/me/latest-dictation')
    async def latest(request:Request):
        uid=beta.user(request)['id'];jid=beta.store.latest(uid)
        return beta.progress(uid,jid) if jid else {'state':'none','message':'還沒有錄音紀錄'}
    @app.post('/v2/me/preferences')
    @app.patch('/v2/me/preferences')
    async def prefs(request:Request):
        body=await object_body(request)
        try:p,v,t=validate_preferences(body.get('personal_prompt',''),body.get('vocabulary',''),body.get('taiwan_places',True))
        except ValueError as e:raise StoreError(400,str(e))
        uid=beta.user(request)['id'];beta.store.preferences(uid,{'personal_prompt':p,'vocabulary':v,'taiwan_places':t})
        return beta.store.me(uid)['preferences']
    @app.delete('/v2/me')
    async def delete(request:Request):
        uid=beta.user(request)['id'];body=await object_body(request)
        await asyncio.to_thread(beta.store.delete,uid,body.get('password',''))
        beta.results={k:v for k,v in beta.results.items() if k[0]!=uid}
        return {'deleted':True}
    @app.post('/v2/me/password')
    async def password(request:Request):
        uid=beta.user(request)['id'];body=await object_body(request)
        async with beta.login_slots:
            await asyncio.to_thread(beta.store.change_password,uid,body.get('current_password'),body.get('new_password'))
        return {'ok':True,'message':'密碼已更新，所有裝置需重新登入'}
    @app.post('/v2/dictations',status_code=202)
    async def dictation(request:Request):
        uid=beta.user(request)['id'];jid=request.headers.get('idempotency-key','')
        if not re.fullmatch(r'[A-Za-z0-9_-]{16,80}',jid):raise StoreError(400,'需要有效請求代碼')
        async with request.form(max_files=1,max_fields=5,max_part_size=16384) as form:
            file=form.get('file')
            if file is None or not hasattr(file,'read'):raise StoreError(400,'需要錄音檔案')
            audio=await file.read(2*1024*1024+1)
        if not audio or len(audio)>2*1024*1024:raise StoreError(413,'錄音需小於 2 MB')
        prefs=beta.store.me(uid)['preferences']
        # Personal settings are fetched from the authenticated account, never from another user ID.
        digest=hashlib.sha256(audio+json.dumps(prefs,sort_keys=True).encode()).hexdigest()
        try:
            old=beta.store.job(uid,jid)
            if old['digest']!=digest:raise StoreError(409,'請求代碼與錄音不符')
            return beta.progress(uid,jid)
        except StoreError as error:
            if error.status!=404:raise
        if beta.queue.full():raise StoreError(429,'目前排隊已滿，請稍後再試')
        try:duration=await asyncio.to_thread(beta.decoder,audio)
        except Exception:raise StoreError(400,'無法讀取錄音')
        if not 0<duration<=120:raise StoreError(413,'每段錄音最多兩分鐘')
        _,fresh=beta.store.reserve(uid,jid,digest,math.ceil(duration))
        if fresh:
            try:beta.queue.put_nowait((uid,jid,audio,prefs))
            except asyncio.QueueFull:
                beta.store.state(uid,jid,'failed');raise StoreError(429,'目前排隊已滿，未扣額度')
        return beta.progress(uid,jid)
    @app.get('/v2/dictations/{jid}')
    async def progress(jid:str,request:Request):return beta.progress(beta.user(request)['id'],jid)
    @app.get('/v2/admin/users')
    async def users():
        url=''
        try:
            matches=re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com',(work/'logs/tunnel.err.log').read_text(encoding='utf-8'))
            if matches:url=matches[-1]
        except OSError:pass
        return {'users':beta.store.users(),'queue_size':beta.queue.qsize(),'provider':'home-pc','service_url':url}
    @app.post('/v2/admin/users',status_code=201)
    async def create(request:Request):
        body=await object_body(request)
        uid=await asyncio.to_thread(beta.store.create,body.get('username',''),body.get('password',''),body.get('minutes',1200))
        return {'id':uid}
    @app.patch('/v2/admin/users/{uid}')
    async def update(uid:str,request:Request):
        body=await object_body(request);beta.store.update(uid,body.get('enabled'),body.get('minutes'));return {'ok':True}
    return beta
