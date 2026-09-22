import tempfile
import unittest
import zipfile
from pathlib import Path
from beta_store import Store,StoreError
from backup import create,restore,export_deletions

class BackupTests(unittest.TestCase):
    def test_old_backup_does_not_resurrect_deleted_account(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'source';work=root/'work';store=Store(work/'beta/accounts.sqlite3')
            (work/'beta/admin.key').write_text('a'*43);(work/'local-voice.key').write_text('b'*43)
            uid=store.create('alice','test-password-12345')
            store.preferences(uid,{'vocabulary':'private words'})
            token=store.login('alice','test-password-12345')['token']
            archive=create(root)
            with self.assertRaises(StoreError):store.delete(uid,'wrong-password')
            with store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM deletions').fetchone()[0],0)
            store.delete(uid,'test-password-12345')
            replacement=store.create('alice','replacement-password')
            ledger=export_deletions(root)
            self.assertNotIn(uid.encode(),ledger.read_bytes())
            target=Path(directory)/'restored'
            restore(target,archive,work/'backup-recovery.key',ledger)
            restored=Store(target/'work/beta/accounts.sqlite3')
            with restored.db() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],0)
                self.assertEqual(db.execute('SELECT uid FROM deletions').fetchone()[0],uid)
            with self.assertRaises(StoreError):restored.authenticate(token)
            # Re-registering the same name has a new identity and remains usable
            # when restoring a backup that actually contains that new account.
            new_archive=create(root);new_target=Path(directory)/'newer'
            restore(new_target,new_archive,work/'backup-recovery.key',ledger)
            self.assertEqual(Store(new_target/'work/beta/accounts.sqlite3').me(replacement)['id'],replacement)
            ledger.unlink()
            with self.assertRaises(ValueError):restore(Path(directory)/'missing-ledger',archive,work/'backup-recovery.key')
            self.assertFalse((Path(directory)/'missing-ledger').exists())

    def test_restore_rejects_ledger_tampering_and_other_host(self):
        from cryptography.exceptions import InvalidTag
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'source';work=root/'work';Store(work/'beta/accounts.sqlite3')
            (work/'beta/admin.key').write_text('a'*43);(work/'local-voice.key').write_text('b'*43)
            archive=create(root);ledger=work/'backups/latest-deletions.dtledger'
            damaged=bytearray(ledger.read_bytes());damaged[-1]^=1;ledger.write_bytes(damaged)
            with self.assertRaises(InvalidTag):restore(Path(directory)/'tampered',archive,work/'backup-recovery.key')
            (work/'local-voice.key').write_text('c'*43);export_deletions(root)
            with self.assertRaises(ValueError):restore(Path(directory)/'other-host',archive,work/'backup-recovery.key')
            self.assertFalse((Path(directory)/'other-host').exists())

    def test_restore_preserves_preferences_revokes_sessions_and_releases_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'source';work=root/'work';store=Store(work/'beta/accounts.sqlite3')
            (work/'beta/admin.key').write_text('a'*43);(work/'local-voice.key').write_text('b'*43)
            uid=store.create('alice','test-password-12345');store.preferences(uid,{'vocabulary':'汐止'})
            token=store.login('alice','test-password-12345')['token'];store.reserve(uid,'pending-request','digest',10)
            store.save_pending(uid,'pending-request',b'private recording',{})
            archive=create(root);target=Path(directory)/'new-host';restore(target,archive,work/'backup-recovery.key')
            self.assertTrue(archive.read_bytes().startswith(b'DTB1'))
            self.assertNotIn(b'alice',archive.read_bytes())
            with self.assertRaises(ValueError):restore(Path(directory)/'without-key',archive)
            damaged=archive.with_name('damaged.dtbackup');data=bytearray(archive.read_bytes());data[-1]^=1;damaged.write_bytes(data)
            from cryptography.exceptions import InvalidTag
            with self.assertRaises(InvalidTag):restore(Path(directory)/'damaged-host',damaged,work/'backup-recovery.key')
            self.assertFalse((Path(directory)/'damaged-host').exists())
            restored=Store(target/'work/beta/accounts.sqlite3')
            self.assertEqual(restored.me(uid)['preferences'],{'vocabulary':'汐止'})
            self.assertEqual(restored.me(uid)['reserved_seconds'],0)
            with restored.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM pending_audio').fetchone()[0],0)
            with self.assertRaises(StoreError):restored.authenticate(token)
            self.assertTrue(restored.login('alice','test-password-12345')['token'])
            with self.assertRaises(ValueError):restore(root,archive)
    def test_rejects_zip_paths_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/'bad.zip'
            with zipfile.ZipFile(archive,'w') as package:package.writestr('../outside','bad')
            target=Path(directory)/'target'
            with self.assertRaises(ValueError):restore(target,archive)
            self.assertFalse(target.exists())

if __name__=='__main__':unittest.main()
