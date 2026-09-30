import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from r2_config import configure, read_config, client_for, validate_config


class R2ConfigTests(unittest.TestCase):
    def test_arbitrary_endpoint_and_truthy_enabled_are_rejected(self):
        base={'format':1,'account_id':'a'*32,'bucket':'test-backups','enabled':False}
        for changed in ({'account_id':'example.com/evil'}, {'bucket':'../other'}, {'enabled':'true'}):
            with self.assertRaises(ValueError): validate_config({**base,**changed})
        self.assertNotIn('endpoint',validate_config({**base,'endpoint':'https://evil.invalid'}))

    def test_configuration_is_disabled_and_stores_only_protected_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch('r2_config.protect',return_value=b'protected-ciphertext') as protect:
                configure(root,'a'*32,'test-backups','k'*32,'s'*64)
            self.assertEqual((root/'work/r2-credentials.dpapi').read_bytes(),b'protected-ciphertext')
            self.assertFalse(read_config(root)['enabled'])
            self.assertNotIn('s'*64,(root/'work/r2-config.json').read_text())
            self.assertEqual(json.loads(protect.call_args.args[0])['secret_access_key'],'s'*64)
            with self.assertRaisesRegex(ValueError,'Existing'):
                configure(root,'a'*32,'test-backups','k'*32,'s'*64)

    def test_sdk_uses_only_validated_r2_endpoint_and_explicit_credentials(self):
        import boto3
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'work').mkdir();(root/'work/r2-credentials.dpapi').write_bytes(b'encrypted')
            with patch('r2_config.unprotect',return_value=b'{"access_key_id":"synthetic","secret_access_key":"synthetic"}'), \
                    patch.object(boto3,'client') as factory:
                client_for(root,{'format':1,'account_id':'a'*32,'bucket':'test-backups','enabled':False})
            arguments=factory.call_args.kwargs
            self.assertEqual(arguments['endpoint_url'],'https://'+'a'*32+'.r2.cloudflarestorage.com')
            self.assertEqual(arguments['region_name'],'auto')
            self.assertEqual(arguments['aws_secret_access_key'],'synthetic')


if __name__ == '__main__': unittest.main()
