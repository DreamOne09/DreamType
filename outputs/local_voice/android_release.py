"""Published preview APK shared by setup downloads and the phone install route.

Update only after verifying the signed GitHub release asset. A local build
report alone is not authorization to distribute an unreleased build.
"""
import hashlib
from pathlib import Path
import tempfile
import urllib.request

VERSION = '0.9.22'
TAG = 'v0.9.22-rc1'
APK_NAME = 'DreamType-' + VERSION + '.apk'
APK_SHA256 = '27e1b081cdda845b58712bb2afc97ac0b35727f5f50c0958a45d2df930de5c72'
APK_URL = 'https://github.com/DreamOne09/DreamType/releases/download/' + TAG + '/' + APK_NAME


def verified_apk(directory):
    path = Path(directory) / APK_NAME
    try:
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        return path if digest == APK_SHA256 else None
    except OSError:
        return None


def download_apk(directory, fetch=urllib.request.urlretrieve):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    existing = verified_apk(directory)
    if existing:
        return existing
    with tempfile.TemporaryDirectory(prefix='apk-download-', dir=directory) as temporary:
        candidate = Path(temporary) / APK_NAME
        fetch(APK_URL, candidate)
        if verified_apk(Path(temporary)) is None:
            raise ValueError('Published APK checksum mismatch')
        destination = directory / APK_NAME
        candidate.replace(destination)
    return destination
