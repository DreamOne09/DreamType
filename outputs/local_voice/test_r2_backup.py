import io
import tempfile
import unittest
from pathlib import Path
from backup import create, export_deletions
from beta_store import Store
from r2_backup import upload_verified_pair


class FakeS3:
    def __init__(self, damage=False, fail_ledger=False):
        self.objects = {}; self.damage = damage; self.fail_ledger = fail_ledger

    def put_object(self, **request):
        if self.fail_ledger and request['Key'].endswith('.dtledger'):
            raise OSError('simulated upload failure')
        self.objects[request['Key']] = request['Body']

    def get_object(self, **request):
        data = self.objects[request['Key']]
        return {'Body': io.BytesIO(data[:-1] if self.damage else data)}


class R2BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); work = self.root / 'work'
        Store(work / 'beta/accounts.sqlite3')
        (work / 'beta/admin.key').write_text('a' * 43)
        (work / 'local-voice.key').write_text('b' * 43)
        self.archive = create(self.root)
        self.key = work / 'backup-recovery.key'
        self.ledger = work / 'backups/latest-deletions.dtledger'

    def upload(self, client):
        return upload_verified_pair(client, 'test-backups', self.root,
                                    self.archive, self.key, self.ledger)

    def test_downloaded_pair_is_restorable_and_key_is_not_uploaded(self):
        client = FakeS3(); report = self.upload(client)
        self.assertTrue(report['verified'])
        self.assertEqual(set(client.objects), {report['archive_object'], report['ledger_object']})
        self.assertEqual(set(client.objects.values()), {self.archive.read_bytes(), self.ledger.read_bytes()})
        self.assertNotIn(self.key.read_bytes(), client.objects.values())
        first = dict(client.objects); self.upload(client)
        self.assertEqual(len(client.objects), 4)
        for name, value in first.items(): self.assertEqual(client.objects[name], value)

    def test_corrupt_download_never_reports_success(self):
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.upload(FakeS3(damage=True))

    def test_partial_pair_failure_does_not_replace_previous_pair(self):
        client = FakeS3(); self.upload(client); first = dict(client.objects)
        client.fail_ledger = True
        with self.assertRaises(OSError): self.upload(client)
        for name, value in first.items(): self.assertEqual(client.objects[name], value)

    def test_invalid_ciphertext_is_rejected_before_network(self):
        client = FakeS3()
        self.archive.write_bytes(b'DTB1' + b'broken' * 20)
        with self.assertRaises(Exception): self.upload(client)
        self.assertEqual(client.objects, {})

    def test_old_ledger_is_rejected_before_network(self):
        old = export_deletions(self.root).read_bytes()
        self.archive = create(self.root); self.ledger.write_bytes(old)
        client = FakeS3()
        with self.assertRaisesRegex(ValueError, 'predates'): self.upload(client)
        self.assertEqual(client.objects, {})

    def test_plaintext_archive_is_not_uploaded(self):
        self.archive = self.archive.with_suffix('.zip')
        self.archive.write_bytes(b'PK' + b'private data' * 20)
        client = FakeS3()
        with self.assertRaises(ValueError): self.upload(client)
        self.assertEqual(client.objects, {})


if __name__ == '__main__': unittest.main()
