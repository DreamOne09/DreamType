"""Authenticated latest-backup catalog with compare-and-swap publication."""
import hashlib
import io
import json
import math
import re
import tempfile
import time
import zipfile
from pathlib import Path
from backup import verify, restore
from private_crypto import encrypt, decrypt
from r2_backup import _encrypted_bytes, _put_verified

INDEX = 'current.dtindex'
CONTEXT = b'DreamType R2 index v1'
LIMITS = {'archive': 256 * 1024 * 1024, 'ledger': 16 * 1024 * 1024}


def _read_response(response, limit):
    stream = response['Body']
    try:
        value = stream.read(limit + 1)
    finally:
        stream.close()
    if len(value) > limit:
        raise ValueError('Remote object exceeds supported size')
    return value


def _decode_index(data, key):
    if not data.startswith(b'DTI1'):
        raise ValueError('Invalid encrypted index')
    value = json.loads(decrypt(key, data[4:], CONTEXT))
    if not isinstance(value, dict) or value.get('format') != 1:
        raise ValueError('Unsupported index format')
    if not isinstance(value.get('host'), str) or not re.fullmatch('[0-9a-f]{64}', value['host']):
        raise ValueError('Invalid host identity')
    for field in ('snapshot_at', 'ledger_at', 'checked_at'):
        stamp = value.get(field)
        if type(stamp) not in (int, float) or not math.isfinite(stamp) or not 0 < stamp <= time.time() + 300:
            raise ValueError('Invalid index timestamp')
    if not value['snapshot_at'] <= value['ledger_at'] <= value['checked_at']:
        raise ValueError('Invalid backup/ledger chronology')
    for field, extension in (('archive', 'dtbackup'), ('ledger', 'dtledger')):
        item = value.get(field)
        if not isinstance(item, dict) or not isinstance(item.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
            raise ValueError('Invalid object digest')
        if item.get('object') != field + 's/' + item['sha256'] + '.' + extension:
            raise ValueError('Invalid object path')
        if type(item.get('size')) is not int or not 32 <= item['size'] <= LIMITS[field]:
            raise ValueError('Invalid object size')
    return value


def read_index(client, bucket, key, *, allow_missing=False):
    try:
        response = client.get_object(Bucket=bucket, Key=INDEX)
    except Exception as error:
        # An inaccessible bucket/credential error is never an empty catalog.
        code = getattr(error, 'response', {}).get('Error', {}).get('Code')
        if allow_missing and code == 'NoSuchKey':
            return None, None
        raise
    data = _read_response(response, 32768)
    etag = response.get('ETag')
    if not isinstance(etag, str) or not etag:
        raise ValueError('Missing index version')
    return _decode_index(data, key), etag


def _download(client, bucket, item):
    value = _read_response(client.get_object(Bucket=bucket, Key=item['object']), item['size'])
    if len(value) != item['size'] or hashlib.sha256(value).hexdigest() != item['sha256']:
        raise ValueError('Remote encrypted object differs from catalog')
    return value


def _descriptor(value, field, extension):
    digest = hashlib.sha256(value).hexdigest()
    return {'object': field + 's/' + digest + '.' + extension, 'sha256': digest, 'size': len(value)}


def _verify_bytes(root, archive, ledger, recovery_key, destination=None, expected=None):
    with tempfile.TemporaryDirectory(prefix='dreamtype-r2-') as directory:
        archive_path = Path(directory) / 'snapshot.dtbackup'
        ledger_path = Path(directory) / 'latest-deletions.dtledger'
        archive_path.write_bytes(archive); ledger_path.write_bytes(ledger)
        verify(Path(root), archive_path, recovery_key, ledger_path)
        key = Path(recovery_key).read_bytes()
        deletion = json.loads(decrypt(key, ledger[4:], b'DreamType deletions v1'))
        with zipfile.ZipFile(io.BytesIO(decrypt(key, archive[4:], b'DreamType backup v1'))) as package:
            snapshot_at = json.loads(package.read('manifest.json'))['snapshot_completed_at']
        metadata = {'host': deletion['host'], 'ledger_at': deletion['exported_at'], 'snapshot_at': snapshot_at}
        if expected and any(metadata[field] != expected[field] for field in metadata):
            raise ValueError('Catalog does not describe downloaded snapshot and ledger')
        if destination is not None:
            # Existing non-empty host directories are rejected by restore().
            restore(Path(destination), archive_path, recovery_key, ledger_path)
        return metadata


def sync_latest(client, bucket, root, archive, recovery_key, ledger):
    root = Path(root); recovery_key = Path(recovery_key)
    key = recovery_key.read_bytes()
    archive_data = _encrypted_bytes(archive, '.dtbackup', b'DTB1', LIMITS['archive'])
    ledger_data = _encrypted_bytes(ledger, '.dtledger', b'DTD1', LIMITS['ledger'])
    metadata = _verify_bytes(root, archive_data, ledger_data, recovery_key)
    snapshot_at = metadata['snapshot_at']
    previous, etag = read_index(client, bucket, key, allow_missing=True)
    if previous and (previous['host'] != metadata['host'] or
                     previous['ledger_at'] > metadata['ledger_at'] or previous['snapshot_at'] > snapshot_at):
        raise ValueError('Refusing a different host or older backup/ledger publication')
    now = time.time()
    catalog = {'format': 1, **metadata, 'checked_at': now,
               'archive': _descriptor(archive_data, 'archive', 'dtbackup'),
               'ledger': _descriptor(ledger_data, 'ledger', 'dtledger')}
    encrypted_index = b'DTI1' + encrypt(key, json.dumps(catalog).encode(), CONTEXT)
    _decode_index(encrypted_index, key)
    downloaded = {}
    for field, content in (('archive', archive_data), ('ledger', ledger_data)):
        if previous and previous[field] == catalog[field]:
            downloaded[field] = _download(client, bucket, catalog[field])
        else:
            downloaded[field], _ = _put_verified(client, bucket, catalog[field]['object'], content)
    _verify_bytes(root, downloaded['archive'], downloaded['ledger'], recovery_key)
    # Publish only after both objects are verified. A concurrent newer writer
    # causes 412, never an unconditional overwrite or blind retry.
    condition = {'IfMatch': etag} if etag else {'IfNoneMatch': '*'}
    _put_verified(client, bucket, INDEX, encrypted_index, **condition)
    return {'verified': True, 'checked_at': now, 'ledger_at': catalog['ledger_at'],
            'snapshot_at': snapshot_at, 'archive_sha256': catalog['archive']['sha256'],
            'scope': 'R2 download and in-memory restore validation'}


def restore_latest(client, bucket, root, recovery_key, *, destination=None, accept_stale=False):
    """Verify/download the current published pair; install only to a new root.

    A stale ledger needs explicit operator acknowledgement. No cloud protocol
    can prove there were no unsynchronized deletions on an unavailable source.
    """
    if destination is not None and Path(destination).exists() and any(Path(destination).iterdir()):
        raise ValueError('Refusing to overwrite a non-empty restore destination')
    catalog, _ = read_index(client, bucket, Path(recovery_key).read_bytes())
    stale = time.time() - catalog['ledger_at'] > 900
    if stale and not accept_stale:
        raise ValueError('Deletion ledger is over 15 minutes old; explicit stale-ledger acknowledgement is required')
    archive = _download(client, bucket, catalog['archive'])
    ledger = _download(client, bucket, catalog['ledger'])
    _verify_bytes(root, archive, ledger, recovery_key, destination, expected=catalog)
    return {'verified': True, 'ledger_at': catalog['ledger_at'], 'snapshot_at': catalog['snapshot_at'],
            'stale_ledger_acknowledged': stale, 'restored': destination is not None}
