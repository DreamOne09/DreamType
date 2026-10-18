"""Public offline migration chain, synthetic installations only."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from beta_store import Store
from backup import create,restore,export_deletions
from process_lock import exclusive,LockBusy
from signin_store import SignInStore
from google_signin import GoogleSubject
from account_reauth import GoogleAccountDeletion
import storage_upgrade as upgrade


class StorageUpgradeTests(unittest.TestCase):
    def fixture(self,d):
        root=Path(d)/'host';work=root/'work';store=Store(work/'beta/accounts.sqlite3')
        uid=store.create('fixture','synthetic-password')
        store.preferences(uid,{'vocabulary':'新竹市、DreamType','personal_prompt':'保留意思','future_setting':True})
        (work/'beta/admin.key').write_text('a'*43);(work/'local-voice.key').write_text('b'*43)
        return root,store,uid

    def test_inspect_is_read_only_and_reports_pending_without_mutating(self):
        with tempfile.TemporaryDirectory() as d:
            root,store,uid=self.fixture(d)
            before={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            report=upgrade.inspect(root)
            self.assertEqual(report['version'],4);self.assertTrue(report['ready_for_next_step'])
            self.assertEqual(before,{p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()})
            store.reserve(uid,'synthetic-request-001','digest',1)
            report=upgrade.inspect(root)
            self.assertEqual(report['counts']['active_jobs'],1);self.assertFalse(report['ready_for_next_step'])
            with self.assertRaisesRegex(ValueError,'active_jobs'):upgrade.prepare(root,4,9)
            self.assertFalse((root/'work/backups').exists())

    def test_all_public_steps_preserve_accounts_and_each_snapshot_restores(self):
        with tempfile.TemporaryDirectory() as d:
            root,store,uid=self.fixture(d);preferences=store.me(uid)['preferences'];archives=[]
            deleted=store.create('deleted-user','synthetic-password');store.login('fixture','synthetic-password')
            for source,target in ((4,9),(9,10),(10,11),(11,12)):
                result=upgrade.prepare(root,source,target);archives.append((source,Path(result['backup'])))
                self.assertEqual(upgrade.inspect(root)['version'],target)
                reopened=Store(store.path)
                self.assertEqual(reopened.me(uid)['preferences'],preferences)
                self.assertFalse(result['configuration_changed']);self.assertFalse(result['restart_performed'])
                self.assertTrue(Path(result['backup']).read_bytes().startswith(b'DTB1'))
            self.assertIsNone(upgrade.inspect(root)['next_version'])
            self.assertFalse(upgrade.inspect(root)['billing_policy_required'])
            class Verifier:
                def verify(self,token,nonce):
                    if token!=nonce:raise ValueError()
                    return GoogleSubject('synthetic-subject')
            signin=SignInStore(reopened,Verifier());challenge=signin.challenge('signup')
            google=signin.login(challenge['challenge'],challenge['secret'],challenge['nonce'])
            deletion=GoogleAccountDeletion(reopened,Verifier());confirmation=deletion.challenge(google['token'])
            archives.append((12,create(root)))
            reopened.delete(deleted,'synthetic-password')
            deletion.delete(google['token'],confirmation['challenge'],confirmation['secret'],confirmation['nonce'])
            ledger=export_deletions(root);key=root/'work/backup-recovery.key'
            for version,archive in archives:
                destination=Path(d)/('restore-'+str(version))
                recovered=Store(restore(destination,archive,key,ledger)/'accounts.sqlite3')
                self.assertEqual(recovered.me(uid)['preferences'],preferences)
                with recovered.db() as db:
                    self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],version)
                    self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],0)
                    self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],1)
                    if version>=11:
                        self.assertEqual(db.execute('SELECT count(*) FROM login_challenges').fetchone()[0],0)
                        self.assertEqual(db.execute('SELECT count(*) FROM login_identities').fetchone()[0],0)
                    if version==12:self.assertEqual(db.execute('SELECT count(*) FROM deletion_challenges').fetchone()[0],0)
                self.assertTrue(recovered.login('fixture','synthetic-password')['token'])
                with self.assertRaisesRegex(ValueError,'overwrite'):restore(destination,archive,key,ledger)

    def test_wrong_step_repeated_step_live_gateway_and_lock_do_not_upgrade(self):
        with tempfile.TemporaryDirectory() as d:
            root,store,uid=self.fixture(d)
            with self.assertRaisesRegex(ValueError,'one supported step'):upgrade.prepare(root,4,12)
            with self.assertRaisesRegex(ValueError,'Source version'):upgrade.prepare(root,9,10)
            proc=SimpleNamespace(info={'cmdline':['python','-m','uvicorn','server:app','--app-dir',str(root/'outputs/local_voice')]})
            with patch('billing_migration.psutil.process_iter',return_value=[proc]):
                self.assertIn('gateway_running',upgrade.inspect(root)['blockers'])
                with self.assertRaisesRegex(ValueError,'gateway_running'):upgrade.prepare(root,4,9)
            with exclusive(root/'work/maintenance.lock'):
                with self.assertRaises(LockBusy):upgrade.prepare(root,4,9)
            self.assertEqual(upgrade.inspect(root)['version'],4)
            self.assertFalse((root/'work/backups').exists())
            upgrade.prepare(root,4,9)
            with self.assertRaisesRegex(ValueError,'already completed'):upgrade.prepare(root,4,9)

    def test_missing_partial_and_unknown_storage_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            missing=Path(d)/'missing'
            with self.assertRaises(ValueError):upgrade.inspect(missing)
            self.assertFalse(missing.exists())
            root,store,uid=self.fixture(d)
            (root/'work/beta/admin.key').unlink()
            self.assertIn('backup_host_keys_missing',upgrade.inspect(root)['blockers'])
            with store.db() as db:db.execute('CREATE TABLE login_identities(unexpected TEXT)')
            with self.assertRaisesRegex(ValueError,'Partial'):upgrade.inspect(root)
            with store.db() as db:db.execute('PRAGMA user_version=99')
            with self.assertRaisesRegex(ValueError,'Unsupported'):upgrade.inspect(root)

    def test_existing_required_billing_policy_survives_every_later_step(self):
        with tempfile.TemporaryDirectory() as d:
            root,store,uid=self.fixture(d);upgrade.prepare(root,4,9)
            with store.db() as db:db.execute('INSERT INTO billing_mode VALUES(1)')
            for source,target in ((9,10),(10,11),(11,12)):
                self.assertTrue(upgrade.inspect(root)['billing_policy_required'])
                upgrade.prepare(root,source,target)
            self.assertTrue(upgrade.inspect(root)['billing_policy_required'])
            with self.assertRaisesRegex(RuntimeError,'explicit billing policy'):Store(store.path)

    def test_cli_requires_explicit_versions_and_emits_safe_report(self):
        with tempfile.TemporaryDirectory() as d:
            root,store,uid=self.fixture(d);output=io.StringIO()
            with contextlib.redirect_stdout(output):self.assertEqual(upgrade.main(['inspect','--root',str(root)]),0)
            report=json.loads(output.getvalue());self.assertTrue(report['ok']);self.assertNotIn('synthetic-password',output.getvalue())
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):upgrade.main(['prepare','--root',str(root)])
            self.assertEqual(upgrade.inspect(root)['version'],4)


if __name__=='__main__':unittest.main()
