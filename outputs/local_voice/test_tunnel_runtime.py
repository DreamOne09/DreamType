import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from tunnel_runtime import configuration,is_owned
from maintenance import run


class TunnelTests(unittest.TestCase):
    def test_named_mode_keeps_credentials_out_of_arguments(self):
        with tempfile.TemporaryDirectory() as d:
            work=Path(d)
            (work/'tunnel-config.json').write_text('{"mode":"named"}')
            with self.assertRaises(ValueError):configuration(work)
            (work/'dreamtype-tunnel.token').write_text('fixture-secret')
            settings=configuration(work)
            self.assertNotIn('fixture-secret',str(settings))
            self.assertEqual(settings['ready_url'],'http://127.0.0.1:19874/ready')
            args=settings['arguments'];self.assertIn('--token-file',args)
            self.assertTrue(is_owned(work,args[0],args[1:]))
            self.assertFalse(is_owned(work,args[0],['run','--token-file',str(work/'other.token')]))

    def test_quick_default_and_invalid_config_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            work=Path(d)
            settings=configuration(work)
            self.assertEqual(settings['mode'],'quick')
            self.assertTrue(is_owned(work,settings['arguments'][0],settings['arguments'][1:]))
            for data in ({'mode':'typo'},{'mode':'named','token':'unsafe'},[],None):
                (work/'tunnel-config.json').write_text(json.dumps(data))
                with self.assertRaises(ValueError):configuration(work)

    def test_maintenance_restarts_selected_mode_and_rejects_missing_token(self):
        for credential in (True,False):
            with self.subTest(credential=credential),tempfile.TemporaryDirectory() as d:
                root=Path(d);work=root/'work';work.mkdir()
                (work/'tunnel-config.json').write_text('{"mode":"named"}')
                if credential:(work/'dreamtype-tunnel.token').write_text('fixture')
                (work/'maintenance-status.json').write_text(json.dumps({'last_backup':9900}))
                calls=[]
                def get(url,**kwargs):
                    calls.append(url)
                    return Mock(status_code=503,json=lambda:{'status':'ready'})
                with patch('maintenance.time.time',return_value=10000),patch('maintenance.httpx.get',side_effect=get),patch('maintenance.subprocess.run') as restart,patch('maintenance.export_deletions'):
                    state=run(root)
                if credential:
                    restart.assert_called_once()
                    self.assertEqual(restart.call_args.args[0][-1],'tunnel')
                    self.assertIn('http://127.0.0.1:19874/ready',calls)
                    self.assertNotIn('http://127.0.0.1:19872/ready',calls)
                    self.assertFalse(state['phone_url_may_have_changed'])
                else:
                    restart.assert_not_called()
                    self.assertIn('tunnel_configuration_invalid',state['errors'])


if __name__=='__main__':unittest.main()
