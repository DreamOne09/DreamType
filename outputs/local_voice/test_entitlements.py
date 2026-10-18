from datetime import datetime,timezone
from dataclasses import replace
from pathlib import Path
import tempfile
import time
import unittest
from beta_store import Store,StoreError
from billing_test_fixture import prepared_store
from billing_store import BillingStore
from entitlements import SubscriptionPolicy
from play_billing import VerifiedSubscription


class EntitlementTests(unittest.TestCase):
    def test_paid_policy_controls_real_reservation_not_beta_allowance(self):
        with tempfile.TemporaryDirectory() as d:
            policy=SubscriptionPolicy({('fixture','monthly'):('pro',60)})
            store=prepared_store(Path(d)/'accounts.sqlite3',policy)
            uid=store.create('alice','fixture-password',minutes=1200)
            session=store.login('alice','fixture-password')['token'];billing=BillingStore(store)
            with self.assertRaises(StoreError):store.reserve(uid,'one','digest',10)
            value=VerifiedSubscription('fixture','monthly','SUBSCRIPTION_STATE_ACTIVE',datetime.fromtimestamp(time.time()+86400,timezone.utc),True,True,False)
            billing.save_verified(uid,session,'fixture-token',value,0)
            self.assertEqual(store.me(uid)['limit_seconds'],60)
            self.assertTrue(store.reserve(uid,'one','digest',50)[1]);store.state(uid,'one','done')
            with self.assertRaises(StoreError):store.reserve(uid,'two','other',11)
            self.assertEqual(store.me(uid)['remaining_seconds'],10)
            billing.save_verified(uid,session,'fixture-token',replace(value,entitled=False,state='SUBSCRIPTION_STATE_EXPIRED',needs_acknowledgement=False),1)
            with self.assertRaises(StoreError):store.reserve(uid,'three','different',1)
            self.assertEqual(store.me(uid)['entitlement_status'],'subscription_required')

    def test_stale_restored_test_and_ambiguous_purchases_cannot_grant(self):
        with tempfile.TemporaryDirectory() as d:
            store=prepared_store(Path(d)/'accounts.sqlite3',SubscriptionPolicy({('fixture','monthly'):('pro',60)}))
            uid=store.create('alice','fixture-password');session=store.login('alice','fixture-password')['token']
            billing=BillingStore(store)
            value=VerifiedSubscription('fixture','monthly','SUBSCRIPTION_STATE_ACTIVE',datetime.fromtimestamp(time.time()+86400,timezone.utc),True,False,False)
            billing.save_verified(uid,session,'one',value,0)
            for column,value_sql in [('needs_refresh',1),('checked_at',0)]:
                with store.db() as db:db.execute('UPDATE play_subscriptions SET '+column+'=?',(value_sql,))
                self.assertEqual(store.me(uid)['entitlement_status'],'verification_required')
                with store.db() as db:db.execute('UPDATE play_subscriptions SET needs_refresh=0,checked_at=?',(time.time(),))
            billing.save_verified(uid,session,'two',value,0)
            self.assertEqual(store.me(uid)['entitlement_status'],'entitlement_conflict')
            with store.db() as db:db.execute('DELETE FROM play_subscriptions')
            billing.save_verified(uid,session,'test',replace(value,test_purchase=True),0)
            self.assertEqual(store.me(uid)['limit_seconds'],0)


if __name__=='__main__':unittest.main()
