"""Schema migration and durable dedup acceptance with synthetic installations."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from billing_test_fixture import prepared_store
from beta_store import Store
from billing_store import BillingStore
from entitlements import SubscriptionPolicy
from backup import create,restore
import notification_migration as migration
import test_billing_notifications as notices
import test_billing_worker as workers

class NotificationStorageTests(unittest.TestCase):
    def fixture(self,d):
        root=Path(d)/'source';work=root/'work';store=prepared_store(work/'beta/accounts.sqlite3')
        uid=store.create('alice','synthetic-password')
        (work/'beta/admin.key').write_text('a'*43);(work/'local-voice.key').write_text('b'*43)
        return root,store,uid

    def test_upgrade_backup_and_schema_ten_restore(self):
        with tempfile.TemporaryDirectory() as d:
            root,store,uid=self.fixture(d)
            result=migration.prepare_notifications(root)
            with store.db() as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],10)
                db.execute('INSERT INTO play_notifications VALUES(?,?,?,?)',('a'*64,'b'*64,uid,1))
            old=Store(restore(Path(d)/'before',Path(result['backup']),root/'work/backup-recovery.key')/'accounts.sqlite3')
            with old.db() as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],9)
            archive=create(root)
            new=Store(restore(Path(d)/'after',archive,root/'work/backup-recovery.key')/'accounts.sqlite3')
            with new.db() as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],10)
                self.assertEqual(db.execute('SELECT count(*) FROM play_notifications').fetchone()[0],1)
                db.execute('DELETE FROM users WHERE id=?',(uid,))
                self.assertEqual(db.execute('SELECT count(*) FROM play_notifications').fetchone()[0],0)
            with self.assertRaises(ValueError):migration.prepare_notifications(root)

    def test_failed_ddl_rolls_back_to_nine(self):
        with tempfile.TemporaryDirectory() as d:
            root,store,uid=self.fixture(d)
            def fail(db):
                db.execute(migration.DDL);db.execute('PRAGMA user_version=10');raise RuntimeError('synthetic failure')
            with patch.object(migration,'_upgrade',fail),self.assertRaises(RuntimeError):migration.prepare_notifications(root)
            with store.db() as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],9)
                self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='play_notifications'").fetchone())

    def test_duplicate_survives_reopen_and_conflicting_payload_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=workers.WorkerTests().setup_store(d)
            fixture=notices.NotificationTests();receiver=fixture.receiver(store)
            self.assertEqual(receiver.receive('Bearer fixture',fixture.body())['status'],'refresh_queued')
            reopened=Store(store.path,store.entitlement_policy)
            self.assertEqual(fixture.receiver(reopened).receive('Bearer fixture',fixture.body())['status'],'duplicate')
            self.assertEqual(BillingStore(reopened).revision(uid,'fixture-token'),2)
            from beta_store import StoreError
            with self.assertRaises(StoreError):fixture.receiver(reopened).receive('Bearer fixture',fixture.body('different-token'))
            self.assertEqual(BillingStore(reopened).revision(uid,'fixture-token'),2)

    def test_ledger_failure_does_not_mark_subscription_refreshed(self):
        with tempfile.TemporaryDirectory() as d:
            store,uid,session,value=workers.WorkerTests().setup_store(d)
            fixture=notices.NotificationTests();receiver=fixture.receiver(store)
            with store.db() as db:db.execute("CREATE TRIGGER fail_notice BEFORE INSERT ON play_notifications BEGIN SELECT RAISE(ABORT,'fixture'); END")
            with self.assertRaises(Exception):receiver.receive('Bearer fixture',fixture.body())
            self.assertEqual(BillingStore(store).revision(uid,'fixture-token'),1)
            self.assertEqual(store.me(uid)['entitlement_status'],'active')

if __name__=='__main__':unittest.main()
