import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from maintenance import run,copy_encrypted

class MaintenanceTests(unittest.TestCase):
    def test_parallel_pass_does_not_overwrite_running_status(self):
        from process_lock import exclusive
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir()
            status=work/'maintenance-status.json';status.write_text('{"checked_at": 123}')
            with exclusive(work/'maintenance.lock'),patch('maintenance.httpx.get') as request:
                result=run(root)
            self.assertEqual(result['skipped'],'maintenance_already_running')
            self.assertEqual(status.read_text(),'{"checked_at": 123}');request.assert_not_called()

    def test_r2_fresh_ledger_is_synced_without_new_daily_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir()
            (work/'maintenance-status.json').write_text(json.dumps({'last_backup':100,'backup_file':'a.dtbackup'}))
            (work/'r2-config.json').write_text('{}')
            ledger=work/'backups/latest-deletions.dtledger';client=Mock()
            with patch('maintenance.time.time',return_value=110), \
                    patch('maintenance.httpx.get',return_value=Mock(status_code=200,json=lambda:{'status':'ready'})), \
                    patch('maintenance.create') as create,patch('maintenance.export_deletions',return_value=ledger), \
                    patch('maintenance.read_config',return_value={'enabled':True,'bucket':'test-backups'}), \
                    patch('maintenance.client_for',return_value=client), \
                    patch('maintenance.sync_latest',return_value={'checked_at':110,'ledger_at':110,'archive_sha256':'a'*64}) as sync:
                state=run(root);create.assert_not_called()
            self.assertEqual(state['errors'],[]);self.assertEqual(state['r2_backup_file'],'a.dtbackup')
            self.assertEqual(sync.call_args.args[-1],ledger);client.close.assert_called_once()
            self.assertEqual(state['r2_deletion_export'],state['last_deletion_export'])

    def test_r2_failure_does_not_claim_new_verification_or_disable_local_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir()
            (work/'maintenance-status.json').write_text(json.dumps({'last_backup':100,'backup_file':'a.dtbackup','last_r2_sync':90}))
            (work/'r2-config.json').write_text('{}')
            with patch('maintenance.time.time',return_value=110), \
                    patch('maintenance.httpx.get',return_value=Mock(status_code=200,json=lambda:{'status':'ready'})), \
                    patch('maintenance.export_deletions',return_value=work/'backups/latest-deletions.dtledger'), \
                    patch('maintenance.read_config',return_value={'enabled':True,'bucket':'test-backups'}), \
                    patch('maintenance.client_for',side_effect=ValueError('secret detail must not be logged')):
                state=run(root)
            self.assertEqual(state['last_backup'],100);self.assertEqual(state['last_r2_sync'],90)
            self.assertEqual(state['errors'],['r2_sync_failed']);self.assertNotIn('secret detail',json.dumps(state))

    def test_explicit_backup_now_runs_even_with_recent_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir()
            archive=work/'new.dtbackup';ledger=work/'latest-deletions.dtledger'
            (work/'maintenance-status.json').write_text(json.dumps({'last_backup':100}))
            with patch('maintenance.time.time',return_value=110), \
                    patch('maintenance.httpx.get',return_value=Mock(status_code=200,json=lambda:{'status':'ready'})), \
                    patch('maintenance.create',return_value=archive) as create, \
                    patch('maintenance.export_deletions',return_value=ledger):
                run(root);create.assert_not_called()
                state=run(root,force_backup=True);create.assert_called_once_with(root)
            self.assertEqual(state['last_backup_verified'],110)

    def test_failed_verified_create_is_not_copied_or_marked_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir();cloud=root/'sync';cloud.mkdir()
            (work/'backup-config.json').write_text(json.dumps({'sync_directory':str(cloud)}))
            ledger=work/'latest-deletions.dtledger';ledger.write_bytes(b'DTD1 encrypted')
            with patch('maintenance.httpx.get',return_value=Mock(status_code=200,json=lambda:{'status':'ready'})), \
                    patch('maintenance.create',side_effect=ValueError('verification failed')), \
                    patch('maintenance.export_deletions',return_value=ledger):
                state=run(root)
            self.assertIn('backup_or_copy_failed',state['errors'])
            self.assertNotIn('last_backup_verified',state)
            self.assertEqual(list(cloud.glob('*.dtbackup')),[])

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

    def test_silent_corruption_never_replaces_previous_copy(self):
        for suffix in ('.dtbackup','.dtledger'):
            with self.subTest(suffix=suffix),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);target=root/'sync';target.mkdir()
                source=root/('encrypted'+suffix);source.write_bytes(b'new complete encrypted bytes')
                destination=target/source.name;destination.write_bytes(b'previous complete bytes')
                def corrupt(src,dst):dst.write_bytes(b'silent corruption')
                with patch('maintenance.shutil.copy2',side_effect=corrupt):
                    with self.assertRaisesRegex(ValueError,'verification failed'):copy_encrypted(source,target)
                self.assertEqual(destination.read_bytes(),b'previous complete bytes')
                self.assertEqual(list(target.iterdir()),[destination])

    def test_source_directory_is_not_a_verified_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'test.dtbackup';source.write_bytes(b'original encrypted bytes')
            with self.assertRaisesRegex(ValueError,'differ'):copy_encrypted(source,root)
            self.assertEqual(source.read_bytes(),b'original encrypted bytes')
            self.assertEqual(list(root.iterdir()),[source])

    def test_verification_read_failure_preserves_previous_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'sync';target.mkdir()
            source=root/'test.dtbackup';source.write_bytes(b'new encrypted bytes')
            destination=target/source.name;destination.write_bytes(b'previous encrypted bytes')
            with patch('maintenance.hashlib.file_digest',side_effect=OSError('read failed')):
                with self.assertRaises(OSError):copy_encrypted(source,target)
            self.assertEqual(destination.read_bytes(),b'previous encrypted bytes')
            self.assertEqual(list(target.iterdir()),[destination])

    def test_corrupt_copy_not_reported_as_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir();target=root/'sync';target.mkdir()
            (work/'backup-config.json').write_text(json.dumps({'sync_directory':str(target)}))
            archive=work/'test.dtbackup';archive.write_bytes(b'encrypted backup')
            ledger=work/'latest-deletions.dtledger';ledger.write_bytes(b'encrypted ledger')
            def corrupt(src,dst):dst.write_bytes(b'wrong bytes')
            with patch('maintenance.httpx.get',return_value=Mock(status_code=200,json=lambda:{'status':'ready'})), \
                    patch('maintenance.create',return_value=archive),patch('maintenance.export_deletions',return_value=ledger), \
                    patch('maintenance.shutil.copy2',side_effect=corrupt):
                state=run(root)
            self.assertIn('backup_or_copy_failed',state['errors'])
            self.assertIn('deletion_export_or_copy_failed',state['errors'])
            self.assertNotIn('last_backup_copy_verified',state)
            self.assertNotIn('last_deletion_copy_verified',state)
            self.assertEqual(list(target.iterdir()),[])

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
            self.assertEqual(state['last_backup_copy_verified'],state['last_backup_copy'])
            self.assertEqual(state['last_deletion_copy_verified'],state['last_deletion_copy'])
            self.assertEqual(state['errors'],[]);self.assertEqual(sorted(p.name for p in cloud.iterdir()),['latest-deletions.dtledger','test.dtbackup'])
            self.assertEqual(state['backup_verified_file'],archive.name)
            self.assertEqual(state['last_backup_verified'],state['last_backup'])
    def test_host_restart_waits_for_two_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'work').mkdir()
            with patch('maintenance.httpx.get',return_value=Mock(status_code=200,json=lambda:{'status':'loading'})),patch('maintenance.create',return_value=root/'backup'),patch('maintenance.subprocess.run') as process:
                run(root);process.assert_not_called();run(root);self.assertEqual(process.call_count,1)
                run(root);self.assertEqual(process.call_count,1)

if __name__=='__main__':unittest.main()
