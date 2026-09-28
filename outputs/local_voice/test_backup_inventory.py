import tempfile,unittest,os
from pathlib import Path
from unittest.mock import patch
from backup_inventory import inventory

class BackupInventoryTests(unittest.TestCase):
    def test_inventory_is_read_only_and_does_not_claim_encryption(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            files={'a.dtbackup':b'not actually encrypted','old.zip':b'legacy','x.verifying':b'partial','latest.dtledger':b'ledger','ignored.key':b'private'}
            for name,data in files.items():(root/name).write_bytes(data)
            os.utime(root/'a.dtbackup',(100,100))
            with patch.object(Path,'open',side_effect=AssertionError('Inventory must not open file content')):
                report=inventory(root)
            self.assertEqual(report['encrypted_archive_files'],1)
            self.assertEqual(report['legacy_zip_files'],1);self.assertEqual(report['incomplete_files'],1)
            self.assertEqual(report['total_bytes'],sum(len(data) for name,data in files.items() if name!='ignored.key'))
            self.assertEqual(report['oldest_archive_mtime'],100)
            self.assertEqual(report['read_errors'],0)
            self.assertNotIn('ignored.key',str(report))
            for name,data in files.items():self.assertEqual((root/name).read_bytes(),data)
    def test_missing_folder_and_nested_files_are_not_created_or_traversed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'backups'
            self.assertEqual(inventory(root)['encrypted_archive_files'],0);self.assertFalse(root.exists())
            (root/'nested').mkdir(parents=True);(root/'nested/x.zip').write_bytes(b'private')
            self.assertEqual(inventory(root)['legacy_zip_files'],0)

if __name__=='__main__':unittest.main()
