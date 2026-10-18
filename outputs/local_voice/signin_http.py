"""Opt-in Google sign-in API with bounded ingress and explicit browser origin."""
import asyncio
import json
import time
from collections import deque
import anyio
from fastapi import APIRouter,Request
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect
from beta_store import StoreError

ORIGIN='https://dreamtype.dreamone.li'
BASE='/v2/auth/google'
DELETE='/v2/me/google/delete'
PATHS=frozenset((BASE+'/config',BASE+'/challenge',BASE+'/complete',DELETE+'/challenge',DELETE+'/complete'))
LIMIT=24576


def signin_router(signin,deletion,client_id,*,allow_signup=False,per_minute=60,concurrency=4,read_timeout=10):
    if signin.store is not deletion.store:raise ValueError('Identity services must share account storage')
    if type(allow_signup) is not bool or type(per_minute) is not int or not 1<=per_minute<=300 or type(concurrency) is not int or not 1<=concurrency<=8 or not 0<read_timeout<=30:
        raise ValueError('Invalid login API limits')
    router=APIRouter();arrivals=deque();active=0;workers=set()
    def response(data,status=200):
        return JSONResponse(data,status_code=status,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',**({'Retry-After':'30'} if status in (429,503) else {})})
    async def handle(request,operation):
        nonlocal active
        # A custom header forces cross-origin browser preflight. No CORS is granted.
        # Missing Origin is accepted only for native clients; this is not attestation.
        origin=request.headers.get('origin');client=request.headers.get('x-dreamtype-client')
        site=request.headers.get('sec-fetch-site')
        if client not in ('web','android') or (origin is not None and origin!=ORIGIN) or (client=='web' and origin!=ORIGIN) or (site is not None and site!='same-origin'):
            return response({'detail':'請從 DreamType 開始登入。'},403)
        now=time.monotonic()
        while arrivals and arrivals[0]<=now-60:arrivals.popleft()
        if len(arrivals)>=per_minute or active>=concurrency:return response({'detail':'登入服務忙碌，請稍後重試。'},429)
        arrivals.append(now);active+=1;inflight=None
        async def io(function,*args):
            nonlocal inflight
            inflight=asyncio.create_task(anyio.to_thread.run_sync(function,*args));workers.add(inflight)
            def finished(task):
                workers.discard(task)
                if not task.cancelled():task.exception()
            inflight.add_done_callback(finished)
            return await asyncio.shield(inflight)
        try:
            if operation=='config':return response({'client_id':client_id,'signup_enabled':allow_signup})
            session=None
            if operation.startswith('delete'):
                auth=request.headers.get('authorization','')
                if not auth.startswith('Bearer ') or len(auth)!=50:raise StoreError(401,'請先登入。')
                session=auth[7:];await io(deletion.store.authenticate,session)
            if request.headers.get('content-type','').split(';')[0].strip().lower()!='application/json' or request.headers.get('content-encoding','identity')!='identity':
                raise StoreError(415,'請使用未壓縮的 JSON。')
            length=request.headers.get('content-length')
            if length is not None:
                if not length.isascii() or not length.isdigit():raise StoreError(400,'無效的內容長度。')
                if len(length)>8 or int(length)>LIMIT:raise StoreError(413,'登入資料過大。')
            body=bytearray()
            async with asyncio.timeout(read_timeout):
                async for chunk in request.stream():
                    if len(body)+len(chunk)>LIMIT:raise StoreError(413,'登入資料過大。')
                    body.extend(chunk)
            try:
                data=json.loads(body)
                if not isinstance(data,dict):raise ValueError()
            except (ValueError,TypeError):raise StoreError(400,'登入資料格式錯誤。') from None
            if operation=='challenge':
                if set(data)!={'purpose'} or data['purpose'] not in ('signin','signup'):raise StoreError(400,'請選擇登入或建立帳號。')
                if data['purpose']=='signup' and not allow_signup:raise StoreError(403,'目前尚未開放自行註冊。')
                return response(await io(signin.challenge,data['purpose']))
            if operation=='delete-challenge':
                if data:raise StoreError(400,'刪除確認資料格式錯誤。')
                return response(await io(deletion.challenge,session))
            expected={'challenge','secret','id_token'}|({'confirm'} if operation=='delete-complete' else set())
            if set(data)!=expected or any(not isinstance(data[k],str) for k in ('challenge','secret','id_token')):raise StoreError(400,'登入資料格式錯誤。')
            if operation=='delete-complete':
                if data['confirm'] is not True:raise StoreError(400,'請確認刪除帳號。')
                return response(await io(deletion.delete,session,data['challenge'],data['secret'],data['id_token']))
            def complete_login():
                # Configuration is immutable for this runtime. Perform SQLite I/O
                # in the same worker as verification, never on the event loop.
                if not allow_signup:
                    with signin.store.db() as db:
                        row=db.execute('SELECT purpose FROM login_challenges WHERE id=?',(data['challenge'],)).fetchone()
                        if row and row['purpose']=='signup':raise StoreError(403,'目前尚未開放自行註冊。')
                return signin.login(data['challenge'],data['secret'],data['id_token'])
            return response(await io(complete_login))
        except StoreError as error:return response({'detail':error.message,'error_code':error.code},error.status)
        except TimeoutError:return response({'detail':'登入資料讀取逾時。'},408)
        except ClientDisconnect:return response({'detail':'登入資料傳送中斷。'},400)
        except Exception:return response({'detail':'登入服務暫時無法使用。'},503)
        finally:
            def release(_=None):
                nonlocal active
                active-=1
            if inflight is not None and not inflight.done():inflight.add_done_callback(release)
            else:release()
    @router.get(BASE+'/config')
    async def config(request:Request):return await handle(request,'config')
    @router.post(BASE+'/challenge')
    async def challenge(request:Request):return await handle(request,'challenge')
    @router.post(BASE+'/complete')
    async def complete(request:Request):return await handle(request,'complete')
    @router.post(DELETE+'/challenge')
    async def delete_challenge(request:Request):return await handle(request,'delete-challenge')
    @router.post(DELETE+'/complete')
    async def delete_complete(request:Request):return await handle(request,'delete-complete')
    return router
