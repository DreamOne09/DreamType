import hashlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from backup import create, export_deletions
from beta_store import Store
from private_crypto import encrypt
from r2_sync import sync_latest, restore_latest, read_index, INDEX, CONTEXT


class S3Error(Exception):
    def __init__(self, code): self.response = {'Error': {'Code': code}}


class MemoryS3:
    def __init__(self):
        self.objects = {}; self.puts = []; self.fail_prefix = None; self.conflict = False

    def put_object(self, **request):
        name = request['Key']; previous = self.objects.get(name)
        if self.fail_prefix and name.startswith(self.fail_prefix): raise S3Error('Unavailable')
        etag = hashlib.sha256(previous).hexdigest() if previous else None
        if (request.get('IfNoneMatch') == '*' and previous is not None or
            'IfMatch' in request and request['IfMatch'] != etag or self.conflict and name == INDEX):
            raise S3Error('PreconditionFailed')
        self.objects[name] = request['Body']; self.puts.append(name)

    def get_object(self, **request):
        if request['Key'] not in self.objects: raise S3Error('NoSuchKey')
        data = self.objects[request['Key']]
        return {'Body': io.BytesIO(data), 'ETag': hashlib.sha256(data).hexdigest()}


class R2SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'source'; work = self.root / 'work'
        self.store = Store(work / 'beta/accounts.sqlite3')
        (work / 'beta/admin.key').write_text('a' * 43)
        (work / 'local-voice.key').write_text('b' * 43)
        self.uid = self.store.create('alice', 'test-password-12345')
        self.archive = create(self.root); self.key = work / 'backup-recovery.key'
        self.ledger = work / 'backups/latest-deletions.dtledger'; self.client = MemoryS3()

    def sync(self):
        return sync_latest(self.client, 'test-backups', self.root, self.archive, self.key, self.ledger)

    def recover(self, **kwargs):
        return restore_latest(self.client, 'test-backups', self.root, self.key, **kwargs)

    def test_latest_deletions_restore_without_resurrecting_user(self):
        self.sync()
        self.store.delete(self.uid, 'test-password-12345'); export_deletions(self.root)
        result = self.sync()
        self.assertTrue(result['verified'])
        self.assertEqual(len([p for p in self.client.puts if p.startswith('archives/')]), 1)
        target = Path(self.temp.name) / 'restored'
        self.assertTrue(self.recover(destination=target)['restored'])
        with Store(target / 'work/beta/accounts.sqlite3').db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 0)
        self.assertNotIn(self.key.read_bytes(), self.client.objects.values())

    def test_verify_only_never_installs_plaintext(self):
        self.sync(); before = {p for p in self.root.rglob('*')}
        self.assertFalse(self.recover()['restored'])
        self.assertEqual(before, {p for p in self.root.rglob('*')})

    def test_partial_upload_preserves_previous_catalog(self):
        self.sync(); previous = self.client.objects[INDEX]
        export_deletions(self.root); self.client.fail_prefix = 'ledgers/'
        with self.assertRaises(S3Error): self.sync()
        self.assertEqual(self.client.objects[INDEX], previous)
        self.assertTrue(self.recover()['verified'])

    def test_catalog_compare_and_swap_rejects_concurrent_writer(self):
        self.sync(); previous = self.client.objects[INDEX]
        self.client.conflict = True; export_deletions(self.root)
        with self.assertRaises(S3Error): self.sync()
        self.assertEqual(self.client.objects[INDEX], previous)

    def test_older_ledger_cannot_replace_newer_catalog(self):
        old = self.ledger.read_bytes(); export_deletions(self.root); self.sync()
        previous = self.client.objects[INDEX]; self.ledger.write_bytes(old)
        with self.assertRaisesRegex(ValueError, 'older'): self.sync()
        self.assertEqual(self.client.objects[INDEX], previous)

    def test_old_backup_cannot_replace_newer_snapshot(self):
        old = self.archive; self.archive = create(self.root); self.sync(); self.archive = old
        with self.assertRaisesRegex(ValueError, 'older'): self.sync()

    def test_stale_ledger_requires_explicit_acknowledgement(self):
        self.sync()
        with patch('r2_sync.time.time', return_value=time.time() + 1000):
            with self.assertRaisesRegex(ValueError, '15 minutes'): self.recover()
            self.assertTrue(self.recover(accept_stale=True)['stale_ledger_acknowledged'])

    def test_corrupt_remote_ciphertext_is_rejected(self):
        self.sync(); catalog, _ = read_index(self.client, 'test-backups', self.key.read_bytes())
        name = catalog['archive']['object']; self.client.objects[name] = b'corrupted'
        with self.assertRaisesRegex(ValueError, 'differs'): self.recover()
        with self.assertRaisesRegex(ValueError, 'differs'): self.sync()

    def test_access_denied_never_treated_as_empty_catalog(self):
        with patch.object(self.client, 'get_object', side_effect=S3Error('AccessDenied')):
            with self.assertRaises(S3Error): self.sync()
        self.assertEqual(self.client.puts, [])

    def test_bad_catalog_schema_rejected(self):
        self.sync(); catalog, _ = read_index(self.client, 'test-backups', self.key.read_bytes())
        for field, value in [('checked_at', True), ('ledger_at', float('nan')), ('format', 99), ('host', 'bad')]:
            changed = {**catalog, field: value}
            self.client.objects[INDEX] = b'DTI1' + encrypt(self.key.read_bytes(), json.dumps(changed).encode(), CONTEXT)
            with self.assertRaises(ValueError): self.recover()

    def test_existing_destination_is_not_overwritten(self):
        self.sync(); before = (self.root / 'work/beta/accounts.sqlite3').read_bytes()
        with self.assertRaisesRegex(ValueError, 'overwrite'): self.recover(destination=self.root)
        self.assertEqual(before, (self.root / 'work/beta/accounts.sqlite3').read_bytes())

    def test_catalog_cannot_misrepresent_ledger_freshness(self):
        self.sync(); catalog, _ = read_index(self.client, 'test-backups', self.key.read_bytes())
        catalog['ledger_at'] += 1; catalog['checked_at'] += 1
        self.client.objects[INDEX] = b'DTI1' + encrypt(self.key.read_bytes(), json.dumps(catalog).encode(), CONTEXT)
        with self.assertRaisesRegex(ValueError, 'does not describe'): self.recover()


if __name__ == '__main__': unittest.main()
