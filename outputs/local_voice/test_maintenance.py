import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from maintenance import run,copy_encrypted

class MaintenanceTests(unittest.TestCase):
    def test_failed_copy_preserves_previous_complete_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'sync';target.mkdir()
            source=root/'latest-deletions.dtledger';source.write_bytes(b'new encrypted ledger')
            destination=target/source.name;destination.write_bytes(b'previous complete ledger')
            def interrupted(src,dst):
                dst.write_bytes(b'partial')
                raise OSError('simulated interrupted copy')
            with patch('maintenance.shutil.copy2',side_effect=interrupted):
                with self.assertRaises(OSError):copy_encrypted(source,target)
            self.assertEqual(destination.read_bytes(),b'previous complete ledger')
            self.assertEqual(list(target.iterdir()),[destination])
            copy_encrypted(source,target)
            self.assertEqual(destination.read_bytes(),source.read_bytes())

    def test_ledger_export_and_copy_follow_daily_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir();cloud=root/'sync';cloud.mkdir()
            (work/'backup-config.json').write_text(json.dumps({'sync_directory':str(cloud)}))
            events=[];archive=work/'test.dtbackup';ledger=work/'latest-deletions.dtledger'
            def snapshot(_):
                events.append('snapshot');archive.write_bytes(b'DTB1 new');return archive
            def export(_):
                self.assertEqual(events,['snapshot'])
                events.append('ledger');ledger.write_bytes(b'DTD1 new');return ledger
            with patch('maintenance.httpx.get',return_value=Mock(status_code=200,json=lambda:{'status':'ready'})), \
                    patch('maintenance.create',side_effect=snapshot),patch('maintenance.export_deletions',side_effect=export):
                state=run(root)
            self.assertEqual(state['errors'],[])
            self.assertEqual((cloud/ledger.name).read_bytes(),b'DTD1 new')

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
