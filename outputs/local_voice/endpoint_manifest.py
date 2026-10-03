"""Signed public service discovery. No accounts, tokens or audio in manifests."""
import base64
import json
import re
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

SERVICE = 'dreamtype-home'
MAX_AGE = 86400


def endpoint(value):
    if not isinstance(value, str) or len(value) > 253:
        raise ValueError('Invalid service address')
    parsed = urlsplit(value)
    host = parsed.hostname or ''
    if (parsed.scheme != 'https' or parsed.username or parsed.password or
            parsed.port is not None or parsed.path or parsed.query or parsed.fragment or
            parsed.netloc != host or not re.fullmatch(
                r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.(?:trycloudflare\.com|dreamone\.li)', host)):
        raise ValueError('Service address must be an approved HTTPS origin')
    return value


def validate(payload, now, minimum_serial=0):
    if not isinstance(payload, dict) or set(payload) != {'service', 'url', 'issued', 'expires', 'serial'}:
        raise ValueError('Invalid discovery fields')
    if payload['service'] != SERVICE:
        raise ValueError('Wrong service')
    for field in ('issued', 'expires', 'serial'):
        if type(payload[field]) is not int:
            raise ValueError('Invalid discovery number')
    issued, expires, serial = (payload[k] for k in ('issued', 'expires', 'serial'))
    if issued < 0 or serial < 1 or serial > 2**53-1 or serial < minimum_serial:
        raise ValueError('Invalid or stale discovery serial')
    if issued > now + 300 or expires <= now or not 0 < expires-issued <= MAX_AGE:
        raise ValueError('Expired or invalid discovery lifetime')
    endpoint(payload['url'])
    return payload


def sign(private_key, url, now, serial):
    if not isinstance(private_key, ec.EllipticCurvePrivateKey) or not isinstance(private_key.curve, ec.SECP256R1):
        raise ValueError('Discovery requires a P-256 key')
    payload = validate(dict(service=SERVICE, url=url, issued=now, expires=now+MAX_AGE, serial=serial), now)
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('ascii')
    signature = private_key.sign(raw, ec.ECDSA(hashes.SHA256()))
    return {'payload': base64.b64encode(raw).decode('ascii'), 'signature': base64.b64encode(signature).decode('ascii')}


def verify(envelope, public_key, now, minimum_serial=0):
    if not isinstance(envelope, dict) or set(envelope) != {'payload', 'signature'}:
        raise ValueError('Invalid discovery envelope')
    if any(not isinstance(envelope[k], str) or len(envelope[k]) > 4096 for k in envelope):
        raise ValueError('Oversized discovery envelope')
    raw = base64.b64decode(envelope['payload'], validate=True)
    signature = base64.b64decode(envelope['signature'], validate=True)
    public_key.verify(signature, raw, ec.ECDSA(hashes.SHA256()))
    return validate(json.loads(raw), now, minimum_serial)


def public_der(key):
    return key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
