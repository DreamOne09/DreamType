"""Prepare signed discovery files locally; publishing is a separate operation."""
import argparse
import base64
import json
from pathlib import Path
import secrets
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from endpoint_manifest import endpoint, public_der, sign, verify
from process_lock import exclusive
from windows_secrets import protect, unprotect


def atomic(path, value):
    temporary = path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
    try:
        temporary.write_text(json.dumps(value, sort_keys=True), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def initialize(work):
    work.mkdir(parents=True, exist_ok=True)
    with exclusive(work/'endpoint-signing.lock'):
        target = work/'endpoint-signing.dpapi'
        if target.exists():
            raise ValueError('Signing key already exists; key rotation requires an app update')
        key = ec.generate_private_key(ec.SECP256R1())
        raw = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        encrypted = protect(raw)
        with target.open('xb') as stream:
            stream.write(encrypted)
        return base64.b64encode(public_der(key)).decode('ascii')


def prepare(work, url, now=None):
    endpoint(url)
    now = int(time.time()) if now is None else now
    with exclusive(work/'endpoint-signing.lock'):
        key = serialization.load_der_private_key(unprotect((work/'endpoint-signing.dpapi').read_bytes()), password=None)
        state = work/'endpoint-serial.json'
        previous = json.loads(state.read_text())['serial'] if state.exists() else 0
        if type(previous) is not int or previous < 0:
            raise ValueError('Invalid saved discovery serial')
        serial = max(now, previous+1)
        envelope = sign(key, url, now, serial)
        verify(envelope, key.public_key(), now, previous)
        # Reserve the serial before writing output: interruptions cannot reuse it.
        atomic(state, {'serial': serial})
        atomic(work/'endpoint-public.json', envelope)
        return {'serial': serial, 'url': url, 'expires': now+86400,
                'public_key': base64.b64encode(public_der(key)).decode('ascii')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    signing = sub.add_parser('sign'); signing.add_argument('--url', required=True)
    args = parser.parse_args()
    result = {'public_key': initialize(args.work)} if args.command == 'init' else prepare(args.work, args.url)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
