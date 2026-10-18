"""Opt-in notification router; not enabled on the live beta application."""
import asyncio
import time
from collections import deque
import anyio
from fastapi import APIRouter,Request
from fastapi.responses import JSONResponse,Response
from starlette.requests import ClientDisconnect
from beta_store import StoreError

PATH='/billing/google/play/notifications'


def notification_router(receiver,*,per_minute=60,concurrency=4,read_timeout=10):
    if type(per_minute) is not int or not 1<=per_minute<=600 or type(concurrency) is not int or not 1<=concurrency<=8 or not 0<read_timeout<=30:
        raise ValueError('Invalid notification limits')
    router=APIRouter();arrivals=deque();active=0;workers=set()

    def failure(status,message):
        return JSONResponse({'detail':message},status_code=status,headers={'Cache-Control':'no-store',**({'Retry-After':'30'} if status in (429,503) else {})})

    @router.post(PATH,include_in_schema=False)
    async def notify(request:Request):
        nonlocal active
        now=time.monotonic()
        while arrivals and arrivals[0]<=now-60:arrivals.popleft()
        if len(arrivals)>=per_minute:return failure(429,'通知流量過高，請稍後重試')
        arrivals.append(now)
        authorization=request.headers.get('authorization','')
        if not authorization.startswith('Bearer ') or len(authorization)>16384:return failure(401,'付款通知驗證失敗')
        if request.headers.get('content-encoding','identity')!='identity':return failure(415,'不支援壓縮通知')
        if request.headers.get('content-type','').split(';')[0].strip().lower()!='application/json':return failure(415,'請使用 JSON 通知')
        length=request.headers.get('content-length')
        if length is not None:
            if not length.isascii() or not length.isdigit():return failure(400,'無效的內容長度')
            if len(length)>8 or int(length)>32768:return failure(413,'通知內容過大')
        if active>=concurrency:return failure(503,'通知處理忙碌，請稍後重試')
        active+=1;task=None
        try:
            body=bytearray()
            async with asyncio.timeout(read_timeout):
                async for chunk in request.stream():
                    if len(body)+len(chunk)>32768:return failure(413,'通知內容過大')
                    body.extend(chunk)
            # Do not block the event loop with certificate fetch or SQLite I/O.
            # Default non-abandoning thread behavior retains capacity until done.
            task=asyncio.create_task(anyio.to_thread.run_sync(receiver.receive,authorization,bytes(body)))
            workers.add(task)
            def finished(done):
                workers.discard(done)
                if not done.cancelled():done.exception()
            task.add_done_callback(finished)
            await asyncio.shield(task)
            return Response(status_code=204,headers={'Cache-Control':'no-store'})
        except StoreError as error:return failure(error.status,error.message)
        except TimeoutError:return failure(408,'通知讀取逾時')
        except ClientDisconnect:return failure(400,'通知傳送中斷')
        except Exception:return failure(503,'通知暫時無法處理，請稍後重試')
        finally:
            def release(_=None):
                nonlocal active
                active-=1
            if task is not None and not task.done():task.add_done_callback(release)
            else:release()

    return router
