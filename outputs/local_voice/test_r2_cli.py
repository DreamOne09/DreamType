import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import r2_cli
from operations import summarize
from process_lock import LockBusy, exclusive
from r2_config import atomic_json, read_config


class R2CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'work').mkdir()
        self.config_path = self.root / 'work/r2-config.json'
        self.status_path = self.root / 'work/maintenance-status.json'
        atomic_json(self.config_path, dict(format=1, account_id='a'*32,
                    bucket='test-backups', enabled=False))

    def run_cli(self, action):
        with patch('sys.argv', ['r2_cli', action, '--root', str(self.root)]), contextlib.redirect_stdout(io.StringIO()):
            return r2_cli.main()

    def sync_patches(self, effect=None):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(r2_cli, 'client_for', return_value=Mock()))
        stack.enter_context(patch.object(r2_cli, 'create', return_value=Path('new.dtbackup')))
        stack.enter_context(patch.object(r2_cli, 'export_deletions', return_value=Path('new.dtledger')))
        stack.enter_context(patch.object(r2_cli.time, 'time', return_value=2000))
        return stack.enter_context(patch.object(r2_cli, 'sync_latest', side_effect=effect,
            return_value=dict(checked_at=2000, ledger_at=2000, archive_sha256='a'*64)))

    def test_disable_cannot_report_success_during_enable(self):
        def during_upload(*args):
            with self.assertRaises(LockBusy): self.run_cli('disable')
            return dict(checked_at=2000, ledger_at=2000, archive_sha256='a'*64)
        self.sync_patches(during_upload)
        self.assertEqual(self.run_cli('enable'), 0)
        self.assertTrue(read_config(self.root)['enabled'])
        self.assertEqual(self.run_cli('disable'), 0)
        self.assertFalse(read_config(self.root)['enabled'])

    def test_busy_lock_prevents_client_creation_and_configuration_reads(self):
        with exclusive(self.root / 'work/maintenance.lock'), patch.object(r2_cli, 'read_config') as read:
            for action in ('enable', 'sync', 'disable'):
                with self.assertRaises(LockBusy): self.run_cli(action)
            read.assert_not_called()

    def test_retry_clears_only_r2_error_without_refreshing_engine_health(self):
        atomic_json(self.status_path, dict(checked_at=100, ready=True, tunnel_ready=True,
                    errors=['r2_sync_failed', 'host_restart_failed']))
        self.sync_patches()
        self.run_cli('enable')
        state = json.loads(self.status_path.read_text())
        self.assertEqual(state['errors'], ['host_restart_failed'])
        self.assertEqual(state['checked_at'], 100)
        checks = {c['code']: c['state'] for c in summarize(state, now=2010)['checks']}
        self.assertEqual(checks['r2'], 'ok')
        self.assertEqual(checks['engine'], 'attention')
        self.assertEqual(checks['tunnel'], 'attention')

    def test_failed_enable_stays_disabled_and_records_failure(self):
        atomic_json(self.status_path, dict(checked_at=100, errors=['host_restart_failed']))
        self.sync_patches(RuntimeError('upload failed'))
        with self.assertRaises(RuntimeError): self.run_cli('enable')
        self.assertFalse(read_config(self.root)['enabled'])
        state = json.loads(self.status_path.read_text())
        self.assertEqual(state['errors'], ['host_restart_failed', 'r2_sync_failed'])
        self.assertEqual(state['checked_at'], 100)
        self.assertEqual(state['backup_verified_file'], 'new.dtbackup')


if __name__ == '__main__':
    unittest.main()
