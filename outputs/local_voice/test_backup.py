import tempfile
import unittest
import zipfile
from pathlib import Path
from beta_store import Store,StoreError
from backup import create,restore

class BackupTests(unittest.TestCase):
    def test_restore_preserves_preferences_revokes_sessions_and_releases_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'source';work=root/'work';store=Store(work/'beta/accounts.sqlite3')
            (work/'beta/admin.key').write_text('a'*43);(work/'local-voice.key').write_text('b'*43)
            uid=store.create('alice','test-password-12345');store.preferences(uid,{'vocabulary':'汐止'})
            token=store.login('alice','test-password-12345')['token'];store.reserve(uid,'pending-request','digest',10)
            archive=create(root);target=Path(directory)/'new-host';restore(target,archive)
            restored=Store(target/'work/beta/accounts.sqlite3')
            self.assertEqual(restored.me(uid)['preferences'],{'vocabulary':'汐止'})
            self.assertEqual(restored.me(uid)['reserved_seconds'],0)
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
