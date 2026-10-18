import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx
from readiness import inspect


class ReadinessTests(unittest.TestCase):
    def report(self, state, mode='named'):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir()
            (work/'maintenance-status.json').write_text(json.dumps(state),encoding='utf-8')
            (work/'tunnel-config.json').write_text(json.dumps({'mode':mode}),encoding='utf-8')
            with patch('readiness.time.time',return_value=2000), \
                    patch('readiness.httpx.get',return_value=httpx.Response(200,json={'status':'ready'})):
                return inspect(root)

    def test_recent_cloud_sync_is_not_independent_restore_or_production(self):
        report=self.report({'r2_enabled':True,'last_r2_sync':1900})
        cloud=report['checks']['cloud_backup']
        self.assertTrue(cloud['recent_verified_sync_reported'])
        self.assertFalse(cloud['independent_restore_verified'])
        self.assertFalse(cloud['recovery_key_off_machine_verified'])
        self.assertFalse(report['public_paid_production'])
        self.assertEqual(report['checks']['tunnel_mode'],'named')

    def test_stale_future_boolean_and_malformed_state_never_claim_recent_sync(self):
        for state in ({'r2_enabled':True,'last_r2_sync':1000},
                      {'r2_enabled':True,'last_r2_sync':2001},
                      {'r2_enabled':True,'last_r2_sync':True},
                      {'r2_enabled':False,'last_r2_sync':1990}, [], None):
            with self.subTest(state=state):
                report=self.report(state,mode='quick')
                self.assertFalse(report['checks']['cloud_backup']['recent_verified_sync_reported'])
                self.assertIn('Configure and verify a fixed service hostname',report['remaining'])
