import tempfile
import unittest
from pathlib import Path
from beta_store import Store,StoreError

class DurabilityTests(unittest.TestCase):
    def test_pending_audio_survives_restart_encrypted_and_preserves_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'accounts.sqlite3';store=Store(path);uid=store.create('alice','password-123456789')
            store.reserve(uid,'pending','digest',10);store.save_pending(uid,'pending',b'private-audio-marker',{'vocabulary':'汐止'})
            store.state(uid,'pending','running');restarted=Store(path);restarted.recover()
            self.assertEqual(list(restarted.pending()),[(uid,'pending',b'private-audio-marker',{'vocabulary':'汐止'})])
            self.assertNotIn(b'private-audio-marker',path.read_bytes())
            restarted.state(uid,'pending','running');restarted.complete(uid,'pending',{'text':'done'})
            with restarted.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM pending_audio').fetchone()[0],0)
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
    def test_corrupt_delivered_result_keeps_completed_charge_and_blocks_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'accounts.sqlite3');uid=store.create('alice','password-123456789')
            jid='delivered-request-12345'
            store.reserve(uid,jid,'hash',10);store.expect_receipt(uid,jid)
            store.state(uid,jid,'running');store.complete(uid,jid,{'text':'received text'})
            store.receipt(uid,jid)
            with store.db() as db:db.execute('UPDATE results SET payload=? WHERE uid=? AND id=?',(b'corrupt',uid,jid))
            self.assertIsNone(store.result(uid,jid))
            self.assertEqual(store.job(uid,jid)['state'],'done')
            self.assertEqual(store.me(uid)['used_seconds'],10)
            row,created=store.reserve(uid,jid,'hash',10,retry_failed=True)
            self.assertFalse(created);self.assertEqual(row['state'],'done')

    def test_corrupt_undelivered_result_refunds_and_retry_requires_fresh_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'accounts.sqlite3');uid=store.create('alice','password-123456789')
            jid='undelivered-request-12345'
            store.reserve(uid,jid,'hash',10);store.expect_receipt(uid,jid)
            store.state(uid,jid,'running');store.complete(uid,jid,{'text':'not yet received'})
            with store.db() as db:db.execute('UPDATE results SET payload=? WHERE uid=? AND id=?',(b'corrupt',uid,jid))
            self.assertIsNone(store.result(uid,jid))
            self.assertEqual(store.job(uid,jid)['state'],'failed');self.assertEqual(store.me(uid)['used_seconds'],0)
            _,created=store.reserve(uid,jid,'hash',10,retry_failed=True);self.assertTrue(created)
            with store.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],0)
            store.save_pending(uid,jid,b'fixture audio',{},True)
            store.state(uid,jid,'running');store.complete(uid,jid,{'text':'retry received'})
            with store.db() as db:self.assertEqual(db.execute('SELECT confirmed FROM receipts').fetchone()[0],0)
            store.receipt(uid,jid);store.receipt(uid,jid)
            self.assertEqual(store.me(uid)['used_seconds'],10)

    def test_reset_is_single_use_and_revokes_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'accounts.sqlite3');uid=store.create('alice','password-123456789')
            token=store.login('alice','password-123456789')['token'];code=store.issue_reset(uid)
            store.reset_password(code,'new-password-123456')
            with self.assertRaises(StoreError):store.authenticate(token)
            with self.assertRaises(StoreError):store.reset_password(code,'another-password-123')
            self.assertTrue(store.login('alice','new-password-123456')['token'])

if __name__=='__main__':unittest.main()
