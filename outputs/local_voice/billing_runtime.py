"""Explicit billing composition sharing the dictation Store and lifecycle."""
import asyncio
import time
import anyio
from billing_service import PlayPurchaseService
from billing_notifications import PlayNotifications
from billing_http import notification_router
from billing_purchase_http import purchase_router
from billing_worker import run


class BillingRuntime:
    def __init__(self,policy,verifier,*,audience,email,subscription,interval=30):
        if not 5<=interval<=300:raise ValueError('Invalid billing interval')
        # Validate push configuration before enabling the policy on any Store.
        PlayNotifications(None,audience=audience,email=email,subscription=subscription)
        if set(policy.catalog)!=set(verifier.catalog):raise ValueError('Billing catalogs must match')
        self.policy=policy;self.verifier=verifier
        self.push={'audience':audience,'email':email,'subscription':subscription}
        self.interval=interval;self.store=None;self.task=None;self.stop_event=None
        self.status={'state':'not_started'}

    def bind(self,app,store):
        if self.store is not None:raise ValueError('Billing runtime already bound')
        if store.entitlement_policy is not self.policy:raise ValueError('Billing must share the dictation policy')
        self.store=store
        app.include_router(purchase_router(PlayPurchaseService(store,self.verifier)))
        app.include_router(notification_router(PlayNotifications(store,**self.push)))

    async def start(self):
        if self.store is None:raise ValueError('Billing runtime not bound')
        if self.task is not None:raise ValueError('Billing runtime already started')
        self.status={'state':'starting','started_at':time.time()}
        self.stop_event=asyncio.Event();self.task=asyncio.create_task(self.loop())

    async def stop(self):
        if self.task is not None:
            self.stop_event.set()
            # Let the current durable pass finish; do not orphan its thread.
            await self.task
            self.task=None;self.status={'state':'stopped'}

    async def loop(self):
        while not self.stop_event.is_set():
            try:
                result=await anyio.to_thread.run_sync(run,self.store,self.verifier)
                self.status={'state':'retrying' if result.get('retry') else 'ready','checked_at':time.time(),**result}
            except Exception:
                self.status={'state':'failed','checked_at':time.time()}
            try:await asyncio.wait_for(self.stop_event.wait(),timeout=self.interval)
            except TimeoutError:pass
