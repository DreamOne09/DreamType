import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from maintenance import run

class MaintenanceTests(unittest.TestCase):
    def test_healthy_host_copies_only_encrypted_archive_and_does_not_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir();cloud=root/'sync';cloud.mkdir()
            (work/'backup-config.json').write_text(json.dumps({'sync_directory':str(cloud)}))
            archive=work/'test.dtbackup';archive.write_bytes(b'DTB1 encrypted')
            ledger=work/'latest-deletions.dtledger';ledger.write_bytes(b'DTD1 encrypted')
            with patch('maintenance.export_deletions',return_value=ledger),patch('maintenance.httpx.get',return_value=Mock(status_code=200,json=lambda:{'status':'ready'})),patch('maintenance.create',return_value=archive),patch('maintenance.subprocess.run') as process:
                state=run(root);process.assert_not_called()
            self.assertEqual(state['errors'],[]);self.assertEqual(sorted(p.name for p in cloud.iterdir()),['latest-deletions.dtledger','test.dtbackup'])
    def test_host_restart_waits_for_two_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'work').mkdir()
            with patch('maintenance.httpx.get',return_value=Mock(status_code=200,json=lambda:{'status':'loading'})),patch('maintenance.create',return_value=root/'backup'),patch('maintenance.subprocess.run') as process:
                run(root);process.assert_not_called();run(root);self.assertEqual(process.call_count,1)
                run(root);self.assertEqual(process.call_count,1)

if __name__=='__main__':unittest.main()
