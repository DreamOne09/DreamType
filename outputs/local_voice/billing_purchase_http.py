"""Opt-in authenticated phone purchase endpoints, requiring a paid policy."""
import asyncio
import json
import time
from collections import deque
from datetime import datetime,timezone
import anyio
from fastapi import APIRouter,Request
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect
from beta_store import StoreError
from play_billing import BillingVerificationError


def purchase_router(service,*,per_minute=30,concurrency=4,read_timeout=10):
    if service.store.entitlement_policy is None:raise ValueError('Explicit paid policy required')
    if type(per_minute) is not int or not 1<=per_minute<=300 or type(concurrency) is not int or not 1<=concurrency<=8 or not 0<read_timeout<=30:
        raise ValueError('Invalid purchase API limits')
    router=APIRouter();arrivals=deque();active=0;workers=set()

    def response(data,status=200):
        return JSONResponse(data,status_code=status,headers={'Cache-Control':'no-store',**({'Retry-After':'30'} if status in (429,503) else {})})

    async def handle(request,purchase=False):
        nonlocal active
        now=time.monotonic()
        while arrivals and arrivals[0]<=now-60:arrivals.popleft()
        if len(arrivals)>=per_minute or active>=concurrency:return response({'detail':'購買驗證忙碌，請稍後重試'},429)
        arrivals.append(now);active+=1
        inflight=None
        async def io(function,*args):
            nonlocal inflight
            inflight=asyncio.create_task(anyio.to_thread.run_sync(function,*args))
            workers.add(inflight)
            def finished(task):
                workers.discard(task)
                if not task.cancelled():task.exception()
            inflight.add_done_callback(finished)
            return await asyncio.shield(inflight)
        try:
            auth=request.headers.get('authorization','')
            if not auth.startswith('Bearer ') or not 1<=len(auth[7:])<=512:raise StoreError(401,'請先登入')
            session=auth[7:]
            identifier=await io(service.account_identifier,session)
            if not purchase:return response({'obfuscated_account_id':identifier,'products':[
                {'product_id':pair[0],'base_plan_id':pair[1],
                 'monthly_seconds':service.store.entitlement_policy.catalog[pair][1],
                 'quota_reset':'utc_calendar_month'} for pair in sorted(service.store.entitlement_policy.catalog)]})
            if request.headers.get('content-type','').split(';')[0].strip().lower()!='application/json' or request.headers.get('content-encoding','identity')!='identity':
                raise StoreError(415,'請使用未壓縮的 JSON')
            body=bytearray()
            length=request.headers.get('content-length')
            if length is not None:
                if not length.isascii() or not length.isdigit():raise StoreError(400,'無效的內容長度')
                if len(length)>8 or int(length)>8192:raise StoreError(413,'購買資料過大')
            async with asyncio.timeout(read_timeout):
                async for chunk in request.stream():
                    if len(body)+len(chunk)>8192:raise StoreError(413,'購買資料過大')
                    body.extend(chunk)
            try:
                data=json.loads(body)
                if not isinstance(data,dict) or set(data)!= {'purchase_token'}:raise ValueError()
                token=data['purchase_token']
                if not isinstance(token,str) or not 1<=len(token)<=4096 or any(c.isspace() for c in token):raise ValueError()
            except (ValueError,TypeError):raise StoreError(400,'購買資料格式錯誤') from None
            def verify():
                service.verify_and_claim(session,token,datetime.now(timezone.utc))
                # Return current stored policy, never provider/client entitlement flags.
                user=service.store.authenticate(session)
                me=service.store.me(user['id'])
                return {key:me[key] for key in ('plan','entitlement_status','limit_seconds','remaining_seconds')}
            return response(await io(verify))
        except StoreError as error:return response({'detail':error.message,'error_code':error.code},error.status)
        except BillingVerificationError:return response({'detail':'無法確認購買，請稍後重試'},503)
        except TimeoutError:return response({'detail':'購買資料讀取逾時'},408)
        except ClientDisconnect:return response({'detail':'購買資料傳送中斷'},400)
        except Exception:return response({'detail':'購買驗證暫時無法使用'},503)
        finally:
            def release(_=None):
                nonlocal active
                active-=1
            # A disconnected request does not cancel a blocking provider call.
            # Keep its slot occupied until the actual thread finishes.
            if inflight is not None and not inflight.done():inflight.add_done_callback(release)
            else:release()

    @router.get('/v2/billing/google/account')
    async def account(request:Request):return await handle(request)

    @router.post('/v2/billing/google/verify')
    async def verify(request:Request):return await handle(request,True)

    return router
