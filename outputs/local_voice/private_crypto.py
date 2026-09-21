"""Authenticated local encryption. Keep the recovery key separate from cloud backups."""
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def key_file(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(AESGCM.generate_key(bit_length=256))
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        pass
    key = path.read_bytes()
    if len(key) != 32:
        raise ValueError('Invalid encryption key; do not replace an existing key.')
    return key

def encrypt(key, data, context):
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, data, context)

def decrypt(key, data, context):
    return AESGCM(key).decrypt(data[:12], data[12:], context)
