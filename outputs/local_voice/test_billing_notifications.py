import base64
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from beta_store import StoreError
from billing_notifications import PlayNotifications
from billing_store import BillingStore,token_digest
import test_billing_worker as worker_fixture
from play_billing import PACKAGE


class NotificationTests(unittest.TestCase):
    def receiver(self,store,claims=None):
        identity={'aud':'https://fixture.invalid/push','email':'push@fixture.iam.gserviceaccount.com','email_verified':True}
        return PlayNotifications(store,audience=identity['aud'],email=identity['email'],subscription='projects/fixture/subscriptions/play',verify_identity=lambda token,aud:identity if claims is None else claims)

    def body(self,token='fixture-token',package=PACKAGE):
        event={'packageName':package,'subscriptionNotification':{'purchaseToken':token,'notificationType':12}}
        return json.dumps({'subscription':'projects/fixture/subscriptions/play','message':{'data':base64.b64encode(json.dumps(event).encode()).decode()}}).encode()

    def test_notification_fences_inflight_state_and_requires_reverification(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=worker_fixture.WorkerTests().setup_store(d)
            receiver=self.receiver(store);billing=BillingStore(store)
            self.assertEqual(receiver.receive('Bearer fixture',self.body())['status'],'refresh_queued')
            self.assertEqual(store.me(uid)['entitlement_status'],'verification_required')
            with self.assertRaises(StoreError):billing.refresh_verified(uid,'fixture-token',value,1)
            # A delayed/repeated notification still cannot assert a purchase state.
            receiver.receive('Bearer fixture',self.body())
            billing.refresh_verified(uid,'fixture-token',replace(value,entitled=False,needs_acknowledgement=False,state='SUBSCRIPTION_STATE_EXPIRED'),3)
            self.assertEqual(store.me(uid)['entitlement_status'],'subscription_required')

    def test_wrong_identity_malformed_and_unknown_token_never_write(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=worker_fixture.WorkerTests().setup_store(d)
            for claims in ({},{'aud':'wrong','email':'push@fixture.iam.gserviceaccount.com','email_verified':True}):
                with self.assertRaises(StoreError):self.receiver(store,claims).receive('Bearer fixture',self.body())
            receiver=self.receiver(store)
            for auth,body in [('no-auth',self.body()),('Bearer fixture',b'x'*32769),('Bearer fixture',self.body(package='wrong')),('Bearer fixture',self.body('unknown'))]:
                with self.assertRaises(StoreError):receiver.receive(auth,body)
            self.assertEqual(BillingStore(store).revision(uid,'fixture-token'),1)
            with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM purchase_claims').fetchone()[0],1)

    def test_old_purchase_notification_refreshes_only_latest_successor(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=worker_fixture.WorkerTests().setup_store(d);billing=BillingStore(store)
            billing.save_verified(uid,session,'new',replace(value,linked_digest=token_digest('fixture-token')),0)
            self.receiver(store).receive('Bearer fixture',self.body())
            self.assertEqual(billing.revision(uid,'new'),2)
            with store.db() as db:
                old=db.execute('SELECT needs_refresh FROM play_subscriptions WHERE digest=?',(token_digest('fixture-token'),)).fetchone()
                self.assertEqual(old[0],0)


if __name__=='__main__':unittest.main()
