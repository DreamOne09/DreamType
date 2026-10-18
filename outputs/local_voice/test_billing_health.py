import tempfile
import unittest
import time
from dataclasses import replace
from billing_health import snapshot
from billing_store import BillingStore,token_digest
import test_billing_worker as fixtures


class HealthTests(unittest.TestCase):
    def test_durable_failures_are_visible_even_after_an_empty_successful_pass(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=fixtures.WorkerTests().setup_store(d);now=time.time()
            with store.db() as db:
                db.execute('INSERT INTO billing_retry VALUES(?,?,?,?)',(token_digest('fixture-token'),1,5,now+3600))
                db.execute('UPDATE purchase_claims SET created=?',(now-7200,))
                db.execute('UPDATE play_subscriptions SET needs_refresh=1')
            health=snapshot(store,{'state':'ready','checked_at':now},True,now=now)
            self.assertEqual(health['state'],'needs_attention')
            self.assertEqual(health['counts']['repeated_failures'],1)
            self.assertEqual({a['code'] for a in health['alerts']},{'repeated_failures','ack_delayed','verification_stale'})
            self.assertNotIn(uid,str(health));self.assertNotIn('fixture-token',str(health))
            stopped=snapshot(store,{'state':'ready','checked_at':now-700},False,now=now)
            self.assertIn('worker_stopped',{a['code'] for a in stopped['alerts']})
            self.assertIn('worker_stale',{a['code'] for a in stopped['alerts']})

    def test_replaced_and_disabled_records_do_not_create_false_backlogs(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=fixtures.WorkerTests().setup_store(d);now=time.time()
            BillingStore(store).save_verified(uid,session,'new',replace(value,needs_acknowledgement=False,linked_digest=token_digest('fixture-token')),0)
            with store.db() as db:db.execute('UPDATE play_subscriptions SET needs_refresh=1 WHERE digest=?',(token_digest('fixture-token'),))
            health=snapshot(store,{'state':'ready','checked_at':now},True,now=time.time())
            self.assertEqual(health['counts']['subscriptions'],1);self.assertEqual(health['alerts'],[])
            with store.db() as db:db.execute('UPDATE users SET enabled=0')
            self.assertEqual(snapshot(store,{'state':'ready'},True)['counts']['subscriptions'],0)


if __name__=='__main__':unittest.main()
