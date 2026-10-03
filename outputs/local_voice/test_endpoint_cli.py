import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
import endpoint_cli
from endpoint_manifest import verify


class PublisherPreparationTests(unittest.TestCase):
    def test_encrypted_key_is_not_replaced_and_serial_survives_clock_rollback(self):
        # Portable encrypted-store fixture; the Windows DPAPI path is exercised
        # separately on the host. No production key enters this test.
        box=Fernet(Fernet.generate_key())
        with tempfile.TemporaryDirectory() as directory, patch.object(endpoint_cli,'protect',box.encrypt), patch.object(endpoint_cli,'unprotect',box.decrypt):
            work=Path(directory)
            public=endpoint_cli.initialize(work)
            encrypted=(work/'endpoint-signing.dpapi').read_bytes()
            with self.assertRaises(ValueError):endpoint_cli.initialize(work)
            self.assertEqual((work/'endpoint-signing.dpapi').read_bytes(),encrypted)
            first=endpoint_cli.prepare(work,'https://first.trycloudflare.com',1800000000)
            second=endpoint_cli.prepare(work,'https://second.trycloudflare.com',1799999999)
            self.assertGreater(second['serial'],first['serial'])
            payload=json.loads((work/'endpoint-public.json').read_text())
            parsed=verify(payload,serialization.load_der_public_key(base64.b64decode(public)),1800000000,first['serial'])
            self.assertEqual(parsed['url'],'https://second.trycloudflare.com')
            self.assertNotIn(base64.b64encode(box.decrypt(encrypted)).decode(),json.dumps(payload))
            self.assertFalse(list(work.glob('*.tmp')))

    def test_invalid_origin_does_not_consume_serial_or_touch_output(self):
        box=Fernet(Fernet.generate_key())
        with tempfile.TemporaryDirectory() as directory, patch.object(endpoint_cli,'protect',box.encrypt), patch.object(endpoint_cli,'unprotect',box.decrypt):
            work=Path(directory);endpoint_cli.initialize(work)
            endpoint_cli.prepare(work,'https://first.trycloudflare.com',1800000000)
            before={p.name:p.read_bytes() for p in work.iterdir()}
            with self.assertRaises(ValueError):endpoint_cli.prepare(work,'https://evil.example',1800000001)
            self.assertEqual(before,{p.name:p.read_bytes() for p in work.iterdir()})


if __name__=='__main__':unittest.main()
