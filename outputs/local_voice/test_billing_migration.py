"""All fixtures live under TemporaryDirectory; never use an installed host."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from beta_store import Store
from backup import restore
import billing_migration as migration

class BillingMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'synthetic-host'
        self.work=self.root/'work';self.database=self.work/'beta/accounts.sqlite3'
        self.store=Store(self.database);self.uid=self.store.create('fixture','synthetic-password')
        self.preferences={'vocabulary':'DreamType','personal_prompt':'保留意思','future':True}
        self.store.preferences(self.uid,self.preferences)
        (self.work/'beta/admin.key').write_text('a'*43)
        (self.work/'local-voice.key').write_text('b'*43)
    def tearDown(self):self.temp.cleanup()
    def assert_baseline(self):
        with self.store.db() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],4)
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertFalse(set(migration.TABLES)&tables)
            self.assertEqual(json.loads(db.execute('SELECT preferences FROM users').fetchone()[0]),self.preferences)
    def test_explicit_migration_preserves_data_and_has_restorable_encrypted_snapshot(self):
        self.assert_baseline()
        result=migration.prepare_storage(self.root)
        self.assertFalse(result['billing_enabled'])
        archive=Path(result['backup']);self.assertTrue(archive.read_bytes().startswith(b'DTB1'))
        with self.store.db() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],9)
            self.assertEqual(db.execute('SELECT count(*) FROM billing_mode').fetchone()[0],0)
            self.assertEqual(json.loads(db.execute('SELECT preferences FROM users').fetchone()[0]),self.preferences)
        destination=Path(self.temp.name)/'restored-host'
        restored=restore(destination,archive,self.work/'backup-recovery.key')
        recovered=Store(restored/'accounts.sqlite3')
        self.assertEqual(recovered.me(self.uid)['preferences'],self.preferences)
        self.assertTrue(recovered.login('fixture','synthetic-password')['token'])
        with self.assertRaises(ValueError):migration.prepare_storage(self.root)
    def test_failure_after_first_ddl_rolls_back_all_schema_changes(self):
        def fail(db):
            db.execute(next(iter(migration.TABLES.values())))
            raise RuntimeError('synthetic failure')
        with patch.object(migration,'_upgrade',fail),self.assertRaises(RuntimeError):migration.prepare_storage(self.root)
        self.assert_baseline()
        self.assertEqual(len(list((self.work/'backups').glob('*.dtbackup'))),1)
    def test_backup_failure_prevents_any_schema_change(self):
        with patch.object(migration,'create',side_effect=OSError('synthetic disk failure')),self.assertRaises(OSError):
            migration.prepare_storage(self.root)
        self.assert_baseline()
    def test_abrupt_exit_before_commit_recovers_schema_four(self):
        script="""import os,sys
from pathlib import Path
import billing_migration as m
def crash(db):
    db.execute(next(iter(m.TABLES.values())))
    db.execute('PRAGMA user_version=9')
    os._exit(73)
m._upgrade=crash
m.prepare_storage(Path(sys.argv[1]))
"""
        result=subprocess.run([sys.executable,'-c',script,str(self.root)],cwd=Path(__file__).parent,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,73,result.stderr.decode(errors='replace'))
        self.assert_baseline()
    def test_pending_recording_blocks_migration(self):
        self.store.reserve(self.uid,'synthetic-request-001','digest',1)
        with self.assertRaisesRegex(ValueError,'pending recordings'):migration.prepare_storage(self.root)
        self.assert_baseline()
        self.assertFalse((self.work/'backups').exists())
    def test_owned_gateway_blocks_migration_without_stopping_any_process(self):
        process=SimpleNamespace(info={'cmdline':['python','-m','uvicorn','server:app','--app-dir',str(self.root/'outputs/local_voice')]})
        with patch('billing_migration.psutil.process_iter',return_value=[process]),self.assertRaisesRegex(ValueError,'Stop this installation'):
            migration.prepare_storage(self.root)
        self.assert_baseline()
    def test_partial_or_future_schema_is_rejected(self):
        with self.store.db() as db:db.execute(next(iter(migration.TABLES.values())))
        with self.assertRaisesRegex(ValueError,'partially migrated'):migration.prepare_storage(self.root)
        with self.store.db() as db:db.execute('PRAGMA user_version=10')
        with self.assertRaisesRegex(ValueError,'schema-4'):migration.prepare_storage(self.root)
    def test_missing_installation_does_not_create_database(self):
        missing=Path(self.temp.name)/'does-not-exist'
        with self.assertRaises(ValueError):migration.prepare_storage(missing)
        self.assertFalse(missing.exists())

if __name__=='__main__':unittest.main()
