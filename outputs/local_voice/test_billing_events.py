import base64
import json
import tempfile
import time
import unittest
from beta_store import Store,StoreError
from billing_events import record,recent
from billing_health import snapshot
import test_billing_worker as workers
import test_billing_notifications as notices

class BillingEventTests(unittest.TestCase):
    def test_authenticated_refund_signal_survives_restart_without_sensitive_payload(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=workers.WorkerTests().setup_store(d)
            fixture=notices.NotificationTests();receiver=fixture.receiver(store)
            envelope=json.loads(fixture.body())
            event=json.loads(base64.b64decode(envelope['message']['data']))
            event.pop('subscriptionNotification')
            event['pendingRefundReviewNotification']={'pendingRefundToken':'secret-pending-token','orderId':'private-order'}
            envelope['message']['data']=base64.b64encode(json.dumps(event).encode()).decode()
            body=json.dumps(envelope).encode()
            for _ in range(2):
                with self.assertRaises(StoreError) as caught:receiver.receive('Bearer fixture',body)
                self.assertEqual(caught.exception.status,503)
            reopened=Store(store.path,store.entitlement_policy)
            health=snapshot(reopened,{'state':'ready','checked_at':time.time()},True)
            self.assertIn('refund_review_pending',{a['code'] for a in health['alerts']})
            with reopened.db() as db:
                rows=[tuple(r) for r in db.execute('SELECT created,action,uid FROM audit')]
                self.assertEqual(len(rows),1);self.assertIsNone(rows[0][2])
                self.assertNotIn('secret-pending-token',str(rows));self.assertNotIn('private-order',str(rows))
                self.assertEqual(db.execute('SELECT count(*) FROM play_notifications').fetchone()[0],0)
            self.assertEqual(store.me(uid)['entitlement_status'],'active')

    def test_wrong_identity_cannot_create_warning_and_signals_age_out(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=workers.WorkerTests().setup_store(d)
            fixture=notices.NotificationTests()
            with self.assertRaises(StoreError):fixture.receiver(store,{}).receive('Bearer fixture',fixture.body('unknown'))
            with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM audit').fetchone()[0],0)
            record(store,'purchase_unbound',now=100)
            record(store,'purchase_unbound',now=120)
            record(store,'purchase_unbound',now=161)
            with store.db() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM audit').fetchone()[0],2)
                self.assertEqual(len(recent(db,200)),1)
                self.assertEqual(recent(db,90000),[])

if __name__=='__main__':unittest.main()
