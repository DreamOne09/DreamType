import base64
import unittest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ec
from endpoint_manifest import endpoint, sign, verify


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.now = 1800000000
        self.url = 'https://fixture.trycloudflare.com'
        self.envelope = sign(self.key, self.url, self.now, 5)

    def test_round_trip_and_custom_domain(self):
        self.assertEqual(verify(self.envelope, self.key.public_key(), self.now)['url'], self.url)
        self.assertEqual(endpoint('https://voice.dreamone.li'), 'https://voice.dreamone.li')

    def test_wrong_key_and_changed_signed_bytes_rejected(self):
        with self.assertRaises(InvalidSignature):
            verify(self.envelope, ec.generate_private_key(ec.SECP256R1()).public_key(), self.now)
        changed = dict(self.envelope)
        raw = base64.b64decode(changed['payload']).replace(b'fixture', b'hostile')
        changed['payload'] = base64.b64encode(raw).decode()
        with self.assertRaises(InvalidSignature):
            verify(changed, self.key.public_key(), self.now)

    def test_expiry_future_issue_and_rollback_rejected(self):
        for now, serial in [(self.now+86400, 0), (self.now-301, 0), (self.now, 6)]:
            with self.subTest(now=now, serial=serial), self.assertRaises(ValueError):
                verify(self.envelope, self.key.public_key(), now, serial)

    def test_credentials_paths_and_unapproved_origins_rejected(self):
        for url in ['http://fixture.trycloudflare.com', 'https://user@fixture.trycloudflare.com',
                    'https://fixture.trycloudflare.com:443', 'https://fixture.trycloudflare.com/',
                    'https://fixture.trycloudflare.com?key=secret', 'https://fixture.trycloudflare.com#x',
                    'https://dreamcube.tw', 'https://evil.example', 'https://trycloudflare.com.evil.example',
                    'https://127.0.0.1', 'https://nested.voice.dreamone.li']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                endpoint(url)

    def test_extra_fields_and_bad_numbers_rejected(self):
        with self.assertRaises(ValueError):
            verify({**self.envelope, 'token': 'must-not-exist'}, self.key.public_key(), self.now)
        for serial in [True, 0, -1, 2**53, '5']:
            with self.subTest(serial=serial), self.assertRaises(ValueError):
                sign(self.key, self.url, self.now, serial)


if __name__ == '__main__':
    unittest.main()
