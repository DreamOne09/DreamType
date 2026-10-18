import tempfile
import threading
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from beta_store import Store,StoreError
from signin_store import SignInStore
from google_signin import GoogleSubject
from account_reauth import GoogleAccountDeletion
import test_signin_storage as fixtures
Verifier=fixtures.Verifier
from backup import create,restore,export_deletions
import reauth_migration as migration

class AccountReauthTests(unittest.TestCase):
    def fixture(self,d):
        root,store=fixtures.SignInStorageTests().fixture(d)
        migration.prepare_reauth(root);store=Store(store.path)
        signin=SignInStore(store,Verifier());c=signin.challenge('signup')
        result=signin.login(c['challenge'],c['secret'],c['nonce'])
        return root,store,result

    def delete(self,service,result,c):
        return service.delete(result['token'],c['challenge'],c['secret'],c['nonce'])

    def test_delete_cascades_and_backup_cannot_resurrect(self):
        with tempfile.TemporaryDirectory() as d:
            root,store,result=self.fixture(d);service=GoogleAccountDeletion(store,Verifier())
            c=service.challenge(result['token']);archive=create(root);key=root/'work/backup-recovery.key'
            restored=Store(restore(Path(d)/'before-delete',archive,key)/'accounts.sqlite3')
            with restored.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM deletion_challenges').fetchone()[0],0)
            self.assertEqual(self.delete(service,result,c),{'deleted':True,'subscription_cancelled':False})
            with self.assertRaises(StoreError):self.delete(service,result,c)
            with self.assertRaises(StoreError):store.authenticate(result['token'])
            with store.db() as db:
                for table in ('users','login_identities','sessions','deletion_challenges','audit'):
                    self.assertEqual(db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
                self.assertEqual(db.execute('SELECT uid FROM deletions').fetchone()[0],result['user']['id'])
            ledger=export_deletions(root)
            after=Store(restore(Path(d)/'after-delete',archive,key,ledger)/'accounts.sqlite3')
            with after.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],0)

    def test_other_google_subject_or_session_cannot_delete(self):
        with tempfile.TemporaryDirectory() as d:
            root,store,result=self.fixture(d);service=GoogleAccountDeletion(store,Verifier());c=service.challenge(result['token'])
            class Wrong(Verifier):
                def verify(self,token,nonce):return GoogleSubject('another-subject')
            with self.assertRaises(StoreError):self.delete(GoogleAccountDeletion(store,Wrong()),result,c)
            signin=SignInStore(store,Verifier());other=signin.challenge('signin')
            session2=signin.login(other['challenge'],other['secret'],other['nonce'])
            with self.assertRaises(StoreError):self.delete(service,session2,c)
            with self.assertRaises(StoreError):self.delete(service,result,other)
            with self.assertRaises(StoreError):signin.login(c['challenge'],c['secret'],c['nonce'])
            self.assertEqual(store.authenticate(result['token'])['id'],result['user']['id'])

    def test_logout_disable_expiry_during_verification_stop_deletion(self):
        for action in ('logout','disable','expire','replace'):
            with self.subTest(action=action),tempfile.TemporaryDirectory() as d:
                root,store,result=self.fixture(d)
                class Changed(Verifier):
                    def verify(self,token,nonce):
                        if action=='logout':store.logout(result['token'])
                        elif action=='disable':store.update(result['user']['id'],False,0)
                        elif action=='replace':GoogleAccountDeletion(store,Verifier()).challenge(result['token'])
                        else:
                            with store.db() as db:db.execute('UPDATE deletion_challenges SET expires=0')
                        return super().verify(token,nonce)
                service=GoogleAccountDeletion(store,Changed());c=service.challenge(result['token'])
                with self.assertRaises(StoreError):self.delete(service,result,c)
                with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],1)

    def test_tombstone_failure_rolls_back_deletion(self):
        with tempfile.TemporaryDirectory() as d:
            root,store,result=self.fixture(d);service=GoogleAccountDeletion(store,Verifier());c=service.challenge(result['token'])
            with store.db() as db:db.execute("CREATE TRIGGER fail_delete BEFORE INSERT ON deletions BEGIN SELECT RAISE(ABORT,'fixture'); END")
            with self.assertRaises(Exception):self.delete(service,result,c)
            self.assertEqual(store.authenticate(result['token'])['id'],result['user']['id'])
            with store.db() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM deletion_challenges').fetchone()[0],1)
                db.execute('DROP TRIGGER fail_delete')
            self.delete(service,result,c)

    def test_concurrent_confirmations_only_delete_once(self):
        with tempfile.TemporaryDirectory() as d:
            root,store,result=self.fixture(d);barrier=threading.Barrier(2)
            class Racing(Verifier):
                def verify(self,token,nonce):
                    subject=super().verify(token,nonce);barrier.wait(timeout=10);return subject
            service=GoogleAccountDeletion(store,Racing());c=service.challenge(result['token'])
            def finish(_):
                try:return self.delete(service,result,c)
                except StoreError:return None
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(finish,range(2)))
            self.assertEqual(sum(r is not None for r in results),1)

    def test_migration_rolls_back_and_preserves_eleven_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root,store=fixtures.SignInStorageTests().fixture(d)
            def fail(db):
                db.execute(migration.TABLES['deletion_challenges']);raise RuntimeError('fixture')
            with patch.object(migration,'_upgrade',fail),self.assertRaises(RuntimeError):migration.prepare_reauth(root)
            with store.db() as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],11)
                self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='deletion_challenges'").fetchone())
            result=migration.prepare_reauth(root)
            before=Store(restore(Path(d)/'before',Path(result['backup']),root/'work/backup-recovery.key')/'accounts.sqlite3')
            with before.db() as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],11)

if __name__=='__main__':unittest.main()
