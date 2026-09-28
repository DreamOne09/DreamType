"""Per-process bounded background work; cancellation never frees a running slot."""
import asyncio
from beta_store import StoreError


class DecoderBudget:
    def __init__(self,limit=2,timeout=15,wait_timeout=2):
        self.limit,self.timeout,self.wait_timeout=limit,timeout,wait_timeout
        self.slots=asyncio.Semaphore(limit);self.waiting=0
        self.tasks=set()

    def finished(self,task):
        self.tasks.discard(task)
        self.slots.release()
        # Retrieve failures even if the requesting client has already gone away.
        if not task.cancelled():task.exception()

    async def run(self,decoder,audio):
        # At most limit running and limit waiting, even if a future caller omits upload admission.
        if self.waiting>=self.limit:
            raise StoreError(429,'正在檢查其他錄音，請稍後重試。','upload_busy')
        self.waiting+=1
        try:
            async with asyncio.timeout(self.wait_timeout):await self.slots.acquire()
        except TimeoutError:
            raise StoreError(429,'正在檢查其他錄音，請稍後重試。','upload_busy')
        finally:self.waiting-=1
        task=asyncio.create_task(asyncio.to_thread(decoder,audio))
        self.tasks.add(task);task.add_done_callback(self.finished)
        try:
            return await asyncio.wait_for(asyncio.shield(task),timeout=self.timeout)
        except TimeoutError:
            # A Python thread cannot be safely killed. Keep counting it until it exits.
            raise StoreError(503,'錄音檢查逾時，未加入排隊。請稍後重試。','decode_timeout')
