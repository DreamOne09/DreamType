from dataclasses import replace
from datetime import datetime,timezone
from pathlib import Path
import tempfile
import time
import unittest
from beta_store import Store,StoreError
from billing_test_fixture import prepared_store
from billing_store import BillingStore,token_digest
from entitlements import SubscriptionPolicy
from play_billing import VerifiedSubscription
from backup import create,restore


class ReplacementTests(unittest.TestCase):
    def test_out_of_order_chain_reconciles_without_reviving_intermediate(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,billing,value=self.setup_account(Path(d))
            billing.save_verified(uid,session,'first',value,0)
            latest=replace(value,product_id='pro',linked_digest=token_digest('middle'))
            billing.save_verified(uid,session,'latest',latest,0)
            self.assertEqual(store.me(uid)['entitlement_status'],'entitlement_conflict')
            intermediate=replace(value,linked_digest=token_digest('first'),needs_acknowledgement=True)
            self.assertFalse(billing.save_verified(uid,session,'middle',intermediate,0))
            self.assertEqual(store.me(uid)['limit_seconds'],120)
            self.assertEqual(billing.pending(),[])
            # Duplicate delivery is harmless and does not create a snapshot.
            self.assertFalse(billing.save_verified(uid,session,'middle',intermediate,0))
            with store.db() as db:
                self.assertIsNone(db.execute('SELECT 1 FROM play_subscriptions WHERE digest=?',(token_digest('middle'),)).fetchone())
                self.assertEqual(db.execute('SELECT count(*) FROM play_replacements').fetchone()[0],2)
            # Closing a multi-hop cycle cannot retire the latest valid purchase.
            with self.assertRaises(StoreError):
                billing.save_verified(uid,session,'first',replace(value,linked_digest=token_digest('latest')),billing.revision(uid,'first'))
            self.assertEqual(store.me(uid)['limit_seconds'],120)
            with self.assertRaises(StoreError):billing.refresh_verified(uid,'middle',intermediate,0)

    def setup_account(self,root):
        policy=SubscriptionPolicy({('basic','monthly'):('basic',60),('pro','monthly'):('pro',120)})
        store=prepared_store(root/'work/beta/accounts.sqlite3',policy)
        uid=store.create('alice','fixture-password');session=store.login('alice','fixture-password')['token']
        value=VerifiedSubscription('basic','monthly','SUBSCRIPTION_STATE_ACTIVE',datetime.fromtimestamp(time.time()+86400,timezone.utc),True,False,False)
        return store,uid,session,BillingStore(store),value

    def test_upgrade_does_not_stack_quota_or_revive_old_purchase(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,billing,value=self.setup_account(Path(d))
            billing.save_verified(uid,session,'old',value,0)
            store.reserve(uid,'one','fixture',40);store.state(uid,'one','done')
            upgraded=replace(value,product_id='pro',linked_digest=token_digest('old'),needs_acknowledgement=True)
            billing.save_verified(uid,session,'new',upgraded,0)
            with store.db() as db:db.execute('UPDATE play_subscriptions SET checked_at=0 WHERE digest=?',(token_digest('old'),))
            self.assertEqual(store.me(uid)['limit_seconds'],120)
            self.assertEqual(store.me(uid)['remaining_seconds'],80)
            self.assertEqual([r['digest'] for r in billing.pending()],[token_digest('new')])
            with self.assertRaises(StoreError):billing.refresh_verified(uid,'old',value,2)
            billing.refresh_verified(uid,'new',replace(upgraded,entitled=False,state='SUBSCRIPTION_STATE_EXPIRED',needs_acknowledgement=False),1)
            self.assertEqual(store.me(uid)['entitlement_status'],'subscription_required')

    def test_pending_preserves_old_and_cross_account_branch_cycle_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,billing,value=self.setup_account(Path(d))
            billing.save_verified(uid,session,'old',value,0)
            pending=replace(value,state='SUBSCRIPTION_STATE_PENDING',entitled=False,linked_digest=token_digest('old'))
            billing.save_verified(uid,session,'new',pending,0)
            self.assertEqual(store.me(uid)['limit_seconds'],60)
            bob=store.create('bobby','fixture-password');bob_session=store.login('bobby','fixture-password')['token']
            with self.assertRaises(StoreError):billing.save_verified(bob,bob_session,'steal',replace(value,linked_digest=token_digest('old')),0)
            billing.save_verified(uid,session,'new',replace(value,product_id='pro',linked_digest=token_digest('old')),1)
            with self.assertRaises(StoreError):billing.save_verified(uid,session,'branch',replace(value,linked_digest=token_digest('old')),0)
            with self.assertRaises(StoreError):billing.save_verified(uid,session,'old',replace(value,linked_digest=token_digest('new')),2)
            with self.assertRaises(StoreError):billing.save_verified(uid,session,'self',replace(value,linked_digest=token_digest('self')),0)
            with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM play_replacements').fetchone()[0],1)

    def test_unknown_old_token_stays_retired_after_restore_and_deletion_cascades(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'source';store,uid,session,billing,value=self.setup_account(root)
            linked=replace(value,linked_digest=token_digest('unseen-old'))
            billing.save_verified(uid,session,'new',linked,0)
            with self.assertRaises(StoreError):billing.save_verified(uid,session,'unseen-old',value,0)
            work=root/'work';(work/'beta/admin.key').write_text('a'*43);(work/'local-voice.key').write_text('b'*43)
            archive=create(root)
            restored=Store(restore(Path(d)/'restored',archive,work/'backup-recovery.key')/'accounts.sqlite3',store.entitlement_policy)
            self.assertEqual(restored.me(uid)['entitlement_status'],'verification_required')
            restored_billing=BillingStore(restored)
            restored_billing.refresh_verified(uid,'new',linked,1)
            self.assertEqual(restored.me(uid)['limit_seconds'],60)
            with restored.db() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM play_replacements').fetchone()[0],1)
                db.execute('DELETE FROM users WHERE id=?',(uid,))
                self.assertEqual(db.execute('SELECT count(*) FROM play_replacements').fetchone()[0],0)


if __name__=='__main__':unittest.main()
