"""Published preview APK shared by setup downloads and the phone install route.

Update only after verifying the signed GitHub release asset. A local build
report alone is not authorization to distribute an unreleased build.
"""
import hashlib
from pathlib import Path
import tempfile
import urllib.request

VERSION = '0.9.13'
TAG = 'v0.9.13-rc1'
APK_NAME = 'DreamType-' + VERSION + '.apk'
APK_SHA256 = 'b10113b228abdb9e2a7045715c5244c540ca25a9666916789c9b80750ff43bdf'
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
