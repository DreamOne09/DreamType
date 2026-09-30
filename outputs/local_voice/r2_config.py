"""Dedicated R2 endpoint and current-user encrypted credentials."""
import json
import re
import secrets
from pathlib import Path
from windows_secrets import protect, unprotect


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
    try:
        temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_config(value):
    if not isinstance(value, dict) or value.get('format') != 1:
        raise ValueError('Invalid R2 configuration')
    if not isinstance(value.get('account_id'), str) or not re.fullmatch('[0-9a-f]{32}', value['account_id']):
        raise ValueError('Invalid R2 account ID')
    if not isinstance(value.get('bucket'), str) or not re.fullmatch('[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', value['bucket']):
        raise ValueError('Invalid dedicated R2 bucket')
    if type(value.get('enabled')) is not bool:
        raise ValueError('R2 enabled must be explicit')
    return {field: value[field] for field in ('format', 'account_id', 'bucket', 'enabled')}


def read_config(root):
    return validate_config(json.loads((Path(root) / 'work/r2-config.json').read_text(encoding='utf-8')))


def configure(root, account_id, bucket, access_key_id, secret_access_key):
    config = validate_config({'format': 1, 'account_id': account_id, 'bucket': bucket, 'enabled': False})
    if not all(isinstance(item, str) and re.fullmatch('[A-Za-z0-9+/=_-]{20,128}', item)
               for item in (access_key_id, secret_access_key)):
        raise ValueError('Invalid R2 credentials')
    work = Path(root) / 'work'; work.mkdir(exist_ok=True)
    target = work / 'r2-credentials.dpapi'
    if target.exists() or (work / 'r2-config.json').exists():
        raise ValueError('Existing R2 configuration must be reviewed before replacement')
    encrypted = protect(json.dumps({'access_key_id': access_key_id, 'secret_access_key': secret_access_key}).encode())
    with target.open('xb') as stream:
        stream.write(encrypted)
    atomic_json(work / 'r2-config.json', config)
    return config


def client_for(root, config=None):
    config = read_config(root) if config is None else validate_config(config)
    credentials = json.loads(unprotect((Path(root) / 'work/r2-credentials.dpapi').read_bytes()))
    import boto3
    from botocore.config import Config
    # No arbitrary endpoint, default AWS credential chain, or disabled TLS.
    return boto3.client('s3', endpoint_url='https://' + config['account_id'] + '.r2.cloudflarestorage.com',
        region_name='auto', aws_access_key_id=credentials['access_key_id'],
        aws_secret_access_key=credentials['secret_access_key'], config=Config(
            connect_timeout=5, read_timeout=30, retries={'mode': 'standard', 'max_attempts': 2},
            request_checksum_calculation='when_required', response_checksum_validation='when_required',
            s3={'addressing_style': 'path'}))
