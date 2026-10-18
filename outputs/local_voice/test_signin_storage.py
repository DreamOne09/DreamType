import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from beta_store import Store,StoreError
from billing_test_fixture import prepared_store,notification_store
from google_signin import GoogleSubject
from signin_store import SignInStore
from backup import create,restore,export_deletions
import signin_migration as migration

class Verifier:
    def verify(self,token,nonce):
        if token!=nonce:raise ValueError()
        return GoogleSubject('stable-subject')

class SignInStorageTests(unittest.TestCase):
    def fixture(self,d,upgrade=True):
        root=Path(d)/'source';work=root/'work'
        store=notification_store(prepared_store(work/'beta/accounts.sqlite3'))
        (work/'beta/admin.key').write_text('a'*43);(work/'local-voice.key').write_text('b'*43)
        if upgrade:migration.prepare_signin(root)
        return root,Store(store.path)

    def finish(self,service,challenge):
        return service.login(challenge['challenge'],challenge['secret'],challenge['nonce'])

    def test_signup_login_restart_replay_and_zero_quota(self):
        with tempfile.TemporaryDirectory() as d:
            root,store=self.fixture(d);service=SignInStore(store,Verifier())
            challenge=service.challenge('signup');result=self.finish(service,challenge)
            uid=result['user']['id'];self.assertEqual(store.authenticate(result['token'])['id'],uid)
            self.assertEqual(store.me(uid)['limit_seconds'],0)
            with self.assertRaises(StoreError):self.finish(service,challenge)
            reopened=SignInStore(Store(store.path),Verifier())
            self.assertEqual(self.finish(reopened,reopened.challenge('signin'))['user']['id'],uid)
            with store.db() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],1)
                self.assertNotIn(result['token'],[r[0] for r in db.execute('SELECT token FROM sessions')])

    def test_expiry_wrong_secret_bad_proof_and_signin_cannot_create(self):
        with tempfile.TemporaryDirectory() as d:
            root,store=self.fixture(d);service=SignInStore(store,Verifier());c=service.challenge('signup')
            for secret,token in [('x'*43,c['nonce']),(c['secret'],'bad')]:
                with self.assertRaises(StoreError):service.login(c['challenge'],secret,token)
            with store.db() as db:db.execute('UPDATE login_challenges SET expires=0')
            with self.assertRaises(StoreError):self.finish(service,c)
            with self.assertRaises(StoreError):self.finish(service,service.challenge('signin'))
            with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],0)

    def test_two_same_challenge_callbacks_issue_only_one_session(self):
        with tempfile.TemporaryDirectory() as d:
            root,store=self.fixture(d);barrier=threading.Barrier(2)
            class Racing(Verifier):
                def verify(self,token,nonce):
                    result=super().verify(token,nonce);barrier.wait(timeout=10);return result
            service=SignInStore(store,Racing());c=service.challenge('signup')
            def finish():
                try:return self.finish(service,c)
                except StoreError:return None
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:finish(),range(2)))
            self.assertEqual(sum(r is not None for r in results),1)
            with store.db() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],1)

    def test_disable_or_delete_during_verification_does_not_recreate(self):
        for action in ('disable','delete'):
            with self.subTest(action=action),tempfile.TemporaryDirectory() as d:
                root,store=self.fixture(d);service=SignInStore(store,Verifier())
                uid=self.finish(service,service.challenge('signup'))['user']['id']
                class Changed(Verifier):
                    def verify(self,token,nonce):
                        with store.db() as db:
                            if action=='disable':db.execute('UPDATE users SET enabled=0 WHERE id=?',(uid,))
                            else:db.execute('DELETE FROM users WHERE id=?',(uid,))
                        return super().verify(token,nonce)
                service=SignInStore(store,Changed())
                with self.assertRaises(StoreError):self.finish(service,service.challenge('signin'))
                with store.db() as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM users WHERE enabled=1').fetchone()[0],0)

    def test_session_failure_rolls_back_account_and_challenge_consumption(self):
        with tempfile.TemporaryDirectory() as d:
            root,store=self.fixture(d);service=SignInStore(store,Verifier());c=service.challenge('signup')
            with store.db() as db:db.execute("CREATE TRIGGER fail_session BEFORE INSERT ON sessions BEGIN SELECT RAISE(ABORT,'fixture'); END")
            with self.assertRaises(Exception):self.finish(service,c)
            with store.db() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],0)
                self.assertEqual(db.execute('SELECT count(*) FROM login_identities').fetchone()[0],0)
                self.assertEqual(db.execute('SELECT count(*) FROM login_challenges').fetchone()[0],1)
                db.execute('DROP TRIGGER fail_session')
            self.finish(service,c)

    def test_backup_retains_identity_but_never_challenge_and_applies_deletion(self):
        with tempfile.TemporaryDirectory() as d:
            root,store=self.fixture(d);service=SignInStore(store,Verifier())
            uid=self.finish(service,service.challenge('signup'))['user']['id'];c=service.challenge('signin')
            archive=create(root);key=root/'work/backup-recovery.key'
            restored=Store(restore(Path(d)/'restored',archive,key)/'accounts.sqlite3')
            with restored.db() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM login_challenges').fetchone()[0],0)
                self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],0)
                self.assertEqual(db.execute('SELECT uid FROM login_identities').fetchone()[0],uid)
            with self.assertRaises(StoreError):self.finish(SignInStore(restored,Verifier()),c)
            with store.db() as db:
                db.execute('DELETE FROM users WHERE id=?',(uid,));db.execute('INSERT INTO deletions VALUES(?,?)',(uid,__import__('time').time()))
            ledger=export_deletions(root)
            deleted=Store(restore(Path(d)/'deleted',archive,key,ledger)/'accounts.sqlite3')
            with deleted.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM login_identities').fetchone()[0],0)

    def test_different_signup_challenges_share_one_account(self):
        with tempfile.TemporaryDirectory() as d:
            root,store=self.fixture(d);service=SignInStore(store,Verifier())
            challenges=[service.challenge('signup'),service.challenge('signup')]
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda c:self.finish(service,c),challenges))
            self.assertEqual(results[0]['user']['id'],results[1]['user']['id'])
            with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM login_identities').fetchone()[0],1)

    def test_expiry_during_verification_prevents_session(self):
        with tempfile.TemporaryDirectory() as d:
            root,store=self.fixture(d)
            class Expired(Verifier):
                def verify(self,token,nonce):
                    with store.db() as db:db.execute('UPDATE login_challenges SET expires=0')
                    return super().verify(token,nonce)
            service=SignInStore(store,Expired())
            with self.assertRaises(StoreError):self.finish(service,service.challenge('signup'))
            with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],0)

    def test_migration_backup_and_ddl_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            root,store=self.fixture(d,False)
            def fail(db):
                db.execute(migration.TABLES['login_identities']);raise RuntimeError('fixture')
            with patch.object(migration,'_upgrade',fail),self.assertRaises(RuntimeError):migration.prepare_signin(root)
            with store.db() as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],10)
                self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='login_identities'").fetchone())
            result=migration.prepare_signin(root)
            before=Store(restore(Path(d)/'before',Path(result['backup']),root/'work/backup-recovery.key')/'accounts.sqlite3')
            with before.db() as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],10)
            with self.assertRaises(ValueError):migration.prepare_signin(root)

if __name__=='__main__':unittest.main()
