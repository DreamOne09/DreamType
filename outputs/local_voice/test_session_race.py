"""Exercise changes between password verification and session issuance."""
from pathlib import Path
import tempfile
import sqlite3
import unittest
from unittest.mock import patch
import beta_store
from beta_store import Store, StoreError


class SessionRaceTests(unittest.TestCase):
    def test_failed_deletion_record_rolls_back_account_and_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'accounts.sqlite3')
            uid=store.create('alice','old-password-12345')
            token=store.login('alice','old-password-12345')['token']
            with store.db() as db:
                db.execute("CREATE TRIGGER reject_deletion BEFORE INSERT ON deletions BEGIN SELECT RAISE(ABORT,'synthetic write failure'); END")
            with self.assertRaises(sqlite3.IntegrityError):store.delete(uid,'old-password-12345')
            self.assertEqual(store.authenticate(token)['id'],uid)
            with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM deletions').fetchone()[0],0)

    def test_manual_password_change_revokes_previously_issued_reset_code(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'accounts.sqlite3')
            uid=store.create('alice','old-password-12345')
            code=store.issue_reset(uid)
            store.change_password(uid,'old-password-12345','new-password-12345')
            with self.assertRaises(StoreError):store.reset_password(code,'unexpected-password')
            self.assertTrue(store.login('alice','new-password-12345')['token'])

    def test_stale_password_cannot_delete_account_or_overwrite_newer_password(self):
        for action in ('change','delete'):
            with self.subTest(action=action),tempfile.TemporaryDirectory() as directory:
                store=Store(Path(directory)/'accounts.sqlite3')
                uid=store.create('alice','old-password-12345')
                real_hash=beta_store.password_hash;changed=False
                def hashing(password,salt):
                    nonlocal changed
                    result=real_hash(password,salt)
                    if not changed:
                        changed=True
                        store.change_password(uid,'old-password-12345','winner-password-12345')
                    return result
                with patch.object(beta_store,'password_hash',side_effect=hashing):
                    with self.assertRaises(StoreError) as error:
                        if action=='delete':store.delete(uid,'old-password-12345')
                        else:store.change_password(uid,'old-password-12345','stale-password-12345')
                self.assertEqual(error.exception.status,403)
                self.assertTrue(store.login('alice','winner-password-12345')['token'])
                with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM deletions').fetchone()[0],0)

    def test_old_login_cannot_survive_password_change_disable_or_delete(self):
        for action in ('password','disable','delete','reset'):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as directory:
                store=Store(Path(directory)/'accounts.sqlite3')
                uid=store.create('alice','old-password-12345')
                token=store.login('alice','old-password-12345')['token']
                real_hash=beta_store.password_hash
                changed=False
                def hashing(password,salt):
                    nonlocal changed
                    result=real_hash(password,salt)
                    if not changed:
                        changed=True
                        if action=='password':store.change_password(uid,'old-password-12345','new-password-12345')
                        elif action=='disable':store.update(uid,False,1200)
                        elif action=='delete':store.delete(uid,'old-password-12345')
                        else:store.reset_password(store.issue_reset(uid),'new-password-12345')
                    return result
                with patch.object(beta_store,'password_hash',side_effect=hashing):
                    with self.assertRaises(StoreError) as error:
                        store.login('alice','old-password-12345')
                self.assertEqual(error.exception.status,401)
                with store.db() as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],0)
                with self.assertRaises(StoreError):store.authenticate(token)
                if action in ('password','reset'):
                    self.assertTrue(store.login('alice','new-password-12345')['token'])

if __name__=='__main__':unittest.main()
