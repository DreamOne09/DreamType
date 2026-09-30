"""Opt-in encrypted backup transport; caller supplies a bucket-scoped S3 client.

Not wired into maintenance until credentials, latest-ledger synchronization and
an actual offsite restore have been configured and verified.
"""
import hashlib
import re
import secrets
import tempfile
from pathlib import Path
from backup import verify


def _encrypted_bytes(path, suffix, magic, limit):
    path = Path(path)
    if path.suffix != suffix or path.is_symlink():
        raise ValueError('Expected a regular encrypted backup file')
    with path.open('rb') as stream:
        value = stream.read(limit + 1)
    if len(value) > limit or not value.startswith(magic) or len(value) < 32:
        raise ValueError('Invalid encrypted backup envelope or size')
    return value


def _put_verified(client, bucket, name, value, **conditions):
    digest = hashlib.sha256(value).hexdigest()
    client.put_object(Bucket=bucket, Key=name, Body=value,
                      ContentType='application/octet-stream',
                      Metadata={'sha256': digest}, **conditions)
    response = client.get_object(Bucket=bucket, Key=name)
    stream = response['Body']
    try:
        # Do not trust metadata/ETag as proof that uploaded bytes are readable.
        downloaded = stream.read(len(value) + 1)
    finally:
        stream.close()
    if len(downloaded) != len(value) or hashlib.sha256(downloaded).hexdigest() != digest:
        raise ValueError('Downloaded encrypted backup does not match upload')
    return downloaded, digest


def upload_verified_pair(client, bucket, root, archive, recovery_key, ledger):
    """Upload a frozen archive/ledger pair, then verify downloaded restore data.

    No recovery key is uploaded. Each attempt uses new object names, so a failed
    attempt cannot overwrite the last verified pair. Failure may leave encrypted
    orphan objects; retention and automatic deletion are intentionally absent.
    The caller must supply the latest ledger, including later deletions when
    eventually restoring an older backup. A snapshot pair is not a latest-ledger
    publication mechanism.
    """
    if not isinstance(bucket, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', bucket):
        raise ValueError('Invalid dedicated backup bucket name')
    archive_data = _encrypted_bytes(archive, '.dtbackup', b'DTB1', 256 * 1024 * 1024)
    ledger_data = _encrypted_bytes(ledger, '.dtledger', b'DTD1', 16 * 1024 * 1024)
    # Only ciphertext is written to staging; decrypted restore checks use RAM.
    with tempfile.TemporaryDirectory(prefix='dreamtype-r2-') as directory:
        staged_archive = Path(directory) / 'snapshot.dtbackup'
        staged_ledger = Path(directory) / 'deletions.dtledger'
        staged_archive.write_bytes(archive_data)
        staged_ledger.write_bytes(ledger_data)
        verify(Path(root), staged_archive, recovery_key, staged_ledger)
        prefix = 'snapshots/' + secrets.token_hex(16) + '/'
        archive_name = prefix + staged_archive.name
        ledger_name = prefix + staged_ledger.name
        downloaded, archive_hash = _put_verified(client, bucket, archive_name, archive_data)
        staged_archive.write_bytes(downloaded)
        downloaded, ledger_hash = _put_verified(client, bucket, ledger_name, ledger_data)
        staged_ledger.write_bytes(downloaded)
        verify(Path(root), staged_archive, recovery_key, staged_ledger)
    return {'verified': True, 'scope': 'downloaded pair restore validation',
            'archive_object': archive_name, 'ledger_object': ledger_name,
            'archive_sha256': archive_hash, 'ledger_sha256': ledger_hash}
