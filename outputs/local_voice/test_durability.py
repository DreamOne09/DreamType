import tempfile
import unittest
from pathlib import Path
from beta_store import Store,StoreError

class DurabilityTests(unittest.TestCase):
    def test_missing_receipt_refunds_and_confirmed_receipt_keeps_charge(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'accounts.sqlite3');uid=store.create('alice','password-123456789')
            for jid,confirmed in [('lost',False),('received',True)]:
                store.reserve(uid,jid,'hash',10);store.expect_receipt(uid,jid);store.state(uid,jid,'running');store.complete(uid,jid,{'text':'hello'})
                if confirmed:store.receipt(uid,jid)
                else:
                    with self.assertRaises(StoreError):store.reserve(uid,'blocked','hash',10)
                with store.db() as db:db.execute('UPDATE results SET expires=0 WHERE uid=? AND id=?',(uid,jid))
                store.cleanup()
                self.assertEqual(store.job(uid,jid)['state'],'done' if confirmed else 'failed')
            self.assertEqual(store.me(uid)['used_seconds'],10)
    def test_restart_preserves_encrypted_result_and_charge_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'accounts.sqlite3';store=Store(path)
            uid=store.create('alice','password-123456789')
            store.reserve(uid,'request-123456789','hash',10);store.state(uid,'request-123456789','running')
            store.complete(uid,'request-123456789',{'text':'secret transcript marker'})
            self.assertNotIn(b'secret transcript marker',path.read_bytes())
            restarted=Store(path);restarted.recover()
            self.assertEqual(restarted.result(uid,'request-123456789')['text'],'secret transcript marker')
            self.assertEqual(restarted.me(uid)['used_seconds'],10)
            with self.assertRaises(ValueError):restarted.complete(uid,'request-123456789',{'text':'overwrite'})
            self.assertEqual(restarted.result(uid,'request-123456789')['text'],'secret transcript marker')
    def test_reset_is_single_use_and_revokes_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'accounts.sqlite3');uid=store.create('alice','password-123456789')
            token=store.login('alice','password-123456789')['token'];code=store.issue_reset(uid)
            store.reset_password(code,'new-password-123456')
            with self.assertRaises(StoreError):store.authenticate(token)
            with self.assertRaises(StoreError):store.reset_password(code,'another-password-123')
            self.assertTrue(store.login('alice','new-password-123456')['token'])

if __name__=='__main__':unittest.main()
