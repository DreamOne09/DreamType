from datetime import datetime,timezone
from dataclasses import replace
from pathlib import Path
import tempfile
import time
import unittest
import httpx
from billing_test_fixture import prepared_store
from beta_store import Store
from billing_store import BillingStore
from billing_service import play_account_id
from billing_worker import run
from entitlements import SubscriptionPolicy
from play_billing import PlayVerifier,VerifiedSubscription
from process_lock import exclusive


class WorkerTests(unittest.TestCase):
    def test_disable_during_google_recheck_prevents_acknowledgement_post(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=self.setup_store(d);methods=[]
            def respond(request):
                methods.append(request.method)
                if len(methods)==2:
                    with store.db() as db:db.execute('UPDATE users SET enabled=0 WHERE id=?',(uid,))
                return httpx.Response(200,json={'subscriptionState':value.state,
                    'externalAccountIdentifiers':{'obfuscatedExternalAccountId':play_account_id(uid)},
                    'acknowledgementState':'ACKNOWLEDGEMENT_STATE_PENDING',
                    'lineItems':[{'productId':'fixture','offerDetails':{'basePlanId':'monthly'},'expiryTime':value.expires_at.isoformat()}]})
            verifier=PlayVerifier(lambda:'fixture-oauth',{('fixture','monthly')},transport=httpx.MockTransport(respond))
            result=run(store,verifier)
            self.assertEqual(result['superseded'],1)
            self.assertEqual(methods,['GET','GET'])

    def test_periodic_recheck_revokes_expired_purchase_without_ack(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=self.setup_store(d)
            with store.db() as db:db.execute('UPDATE play_subscriptions SET ack_pending=0,checked_at=0')
            class ExpiredVerifier:
                def verify(self,*args):return replace(value,entitled=False,state='SUBSCRIPTION_STATE_EXPIRED',needs_acknowledgement=False)
                def ensure_acknowledged(self,*args,**kwargs):raise AssertionError('Expired purchases must not be acknowledged')
            self.assertEqual(run(store,ExpiredVerifier())['checked'],1)
            self.assertEqual(store.me(uid)['limit_seconds'],0)
            from beta_store import StoreError
            with self.assertRaises(StoreError):store.reserve(uid,'expired-job','digest',1)

    def test_elapsed_budget_leaves_unstarted_purchases_for_next_pass(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=self.setup_store(d)
            class NoCalls:
                def verify(self,*args):raise AssertionError('Budget already elapsed')
            ticks=iter([0,2])
            result=run(store,NoCalls(),budget_seconds=1,monotonic=lambda:next(ticks))
            self.assertEqual(result,{'checked':0,'confirmed':0,'retry':0,'superseded':0})
            self.assertEqual(len(BillingStore(store).pending()),1)

    def setup_store(self,d):
        policy=SubscriptionPolicy({('fixture','monthly'):('pro',60)})
        store=prepared_store(Path(d)/'accounts.sqlite3',policy);uid=store.create('alice','fixture-password')
        session=store.login('alice','fixture-password')['token']
        value=VerifiedSubscription('fixture','monthly','SUBSCRIPTION_STATE_ACTIVE',datetime.fromtimestamp(time.time()+86400,timezone.utc),True,True,False)
        BillingStore(store).save_verified(uid,session,'fixture-token',value,0)
        return store,uid,session,value

    def test_restart_retains_backoff_then_recovers_lost_ack(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=self.setup_store(d);methods=[];ack=[False];now=time.time()
            def respond(request):
                methods.append(request.method)
                if request.method=='POST':
                    ack[0]=True
                    raise httpx.ReadTimeout('fixture lost response',request=request)
                return httpx.Response(200,json={'subscriptionState':value.state,
                    'externalAccountIdentifiers':{'obfuscatedExternalAccountId':play_account_id(uid)},
                    'acknowledgementState':'ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED' if ack[0] else 'ACKNOWLEDGEMENT_STATE_PENDING',
                    'lineItems':[{'productId':'fixture','offerDetails':{'basePlanId':'monthly'},'expiryTime':value.expires_at.isoformat()}]})
            verifier=PlayVerifier(lambda:'fixture-oauth',{('fixture','monthly')},transport=httpx.MockTransport(respond))
            self.assertEqual(run(store,verifier,clock=lambda:now)['retry'],1)
            reopened=Store(store.path,store.entitlement_policy)
            prior=len(methods)
            self.assertEqual(run(reopened,verifier,clock=lambda:now+10)['checked'],0)
            self.assertEqual(len(methods),prior)
            self.assertEqual(run(reopened,verifier,clock=lambda:now+31)['checked'],1)
            self.assertEqual(methods.count('POST'),1)
            self.assertEqual(BillingStore(reopened).pending(),[])
            with reopened.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM billing_retry').fetchone()[0],0)

    def test_single_worker_and_newer_result_wins(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=self.setup_store(d)
            class RacingVerifier:
                def verify(self,*args):
                    BillingStore(store).save_verified(uid,session,'fixture-token',replace(value,state='SUBSCRIPTION_STATE_EXPIRED',entitled=False,needs_acknowledgement=False),1)
                    return value
                def ensure_acknowledged(self,*args):raise AssertionError('Must not acknowledge superseded work')
            with exclusive(store.path.parent/'billing-worker.lock'):
                self.assertEqual(run(store,RacingVerifier()),{'skipped':'billing_worker_running'})
            self.assertEqual(run(store,RacingVerifier())['superseded'],1)
            self.assertEqual(store.me(uid)['limit_seconds'],0)
            self.assertEqual(BillingStore(store).pending(),[])


if __name__=='__main__':unittest.main()
