from datetime import datetime,timezone
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest
from beta_store import Store,StoreError
from billing_test_fixture import prepared_store
from billing_store import BillingStore
from play_billing import VerifiedSubscription
from backup import create,restore

VERIFIED=VerifiedSubscription('fixture','monthly','SUBSCRIPTION_STATE_ACTIVE',datetime(2027,1,1,tzinfo=timezone.utc),True,True,False)


class BillingStoreTests(unittest.TestCase):
    def account(self,root):
        store=prepared_store(root/'work/beta/accounts.sqlite3')
        uid=store.create('alice','fixture-password');session=store.login('alice','fixture-password')['token']
        return store,uid,session

    def test_atomic_pending_restarts_and_stale_update_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);store,uid,session=self.account(root);billing=BillingStore(store)
            self.assertTrue(billing.save_verified(uid,session,'fixture-secret',VERIFIED,0))
            pending=BillingStore(Store(store.path)).pending()
            self.assertEqual(len(pending),1);self.assertEqual(pending[0]['revision'],1)
            with self.assertRaises(StoreError):billing.save_verified(uid,session,'fixture-secret',VERIFIED,0)
            canceled=replace(VERIFIED,state='SUBSCRIPTION_STATE_EXPIRED',entitled=False,needs_acknowledgement=False)
            self.assertFalse(billing.save_verified(uid,session,'fixture-secret',canceled,1))
            self.assertEqual(billing.pending(),[])
            self.assertNotIn(b'fixture-secret',store.path.read_bytes())
            with store.db() as db:
                db.execute("CREATE TRIGGER reject_subscription BEFORE INSERT ON play_subscriptions BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
            with self.assertRaises(sqlite3.IntegrityError):billing.save_verified(uid,session,'different-token',VERIFIED,0)
            with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM purchase_claims').fetchone()[0],1)

    def test_snapshot_restores_pending_but_requires_fresh_provider_check(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'source';store,uid,session=self.account(root);work=root/'work'
            (work/'beta/admin.key').write_text('a'*43);(work/'local-voice.key').write_text('b'*43)
            billing=BillingStore(store);billing.save_verified(uid,session,'fixture-secret',VERIFIED,0)
            archive=create(root)
            path=restore(Path(d)/'restored',archive,work/'backup-recovery.key')/'accounts.sqlite3'
            tasks=BillingStore(Store(path)).pending()
            self.assertEqual(len(tasks),1);self.assertEqual(tasks[0]['needs_refresh'],1)
            key=work/'beta/billing.key';original=key.read_bytes();key.unlink()
            with self.assertRaises(ValueError):billing.save_verified(uid,session,'fixture-secret',VERIFIED,1)
            self.assertFalse(key.exists())
            with self.assertRaises(ValueError):create(root)
            key.write_bytes(b'z'*32)
            with self.assertRaises(Exception):create(root)
            key.write_bytes(original)


if __name__=='__main__':unittest.main()
