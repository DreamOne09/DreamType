import tempfile
import unittest
from pathlib import Path
from beta_store import Store,StoreError
from billing_test_fixture import prepared_store
from entitlements import SubscriptionPolicy
from backup import create,restore


class ModeTests(unittest.TestCase):
    def test_policy_requires_explicit_migration_and_does_not_create_or_modify_storage(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'fresh/accounts.sqlite3'
            policy=SubscriptionPolicy({('fixture','monthly'):('pro',120)})
            with self.assertRaisesRegex(RuntimeError,'offline'):Store(path,policy)
            self.assertFalse(path.parent.exists())
            trial=Store(path);uid=trial.create('alice','fixture-password')
            before=path.read_bytes()
            with self.assertRaisesRegex(RuntimeError,'offline'):Store(path,policy)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(trial.me(uid)['plan'],'closed-beta')
            with trial.db() as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],4)

    def test_incomplete_prepared_schema_does_not_enable_paid_mode(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'accounts.sqlite3';trial=prepared_store(path)
            with trial.db() as db:db.execute('DROP TABLE play_replacements')
            policy=SubscriptionPolicy({('fixture','monthly'):('pro',120)})
            with self.assertRaises(ValueError):Store(path,policy)
            with trial.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM billing_mode').fetchone()[0],0)

    def test_paid_database_and_restored_copy_cannot_silently_become_trial(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'source';work=root/'work';path=work/'beta/accounts.sqlite3'
            trial=Store(path);uid=trial.create('alice','fixture-password')
            policy=SubscriptionPolicy({('fixture','monthly'):('pro',120)})
            paid=prepared_store(path,policy)
            with self.assertRaises(StoreError):trial.me(uid)
            with self.assertRaises(StoreError):trial.reserve(uid,'fixture','fixture',10)
            self.assertEqual(paid.me(uid)['entitlement_status'],'subscription_required')
            with self.assertRaisesRegex(RuntimeError,'refusing trial fallback'):Store(path)
            (work/'beta/admin.key').write_text('a'*43);(work/'local-voice.key').write_text('b'*43)
            archive=create(root)
            target=restore(Path(d)/'restored',archive,work/'backup-recovery.key')/'accounts.sqlite3'
            with self.assertRaisesRegex(RuntimeError,'refusing trial fallback'):Store(target)
            self.assertEqual(Store(target,policy).me(uid)['limit_seconds'],0)
            with paid.db() as db:db.execute('DELETE FROM users')
            with self.assertRaises(RuntimeError):Store(path)


if __name__=='__main__':unittest.main()
