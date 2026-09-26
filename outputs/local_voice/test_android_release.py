import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import android_release as release


class PublishedApkTests(unittest.TestCase):
    def test_missing_or_changed_build_is_not_served_as_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertIsNone(release.verified_apk(root))
            (root/release.APK_NAME).write_bytes(b'unreleased local build')
            self.assertIsNone(release.verified_apk(root))

    def test_failed_download_preserves_existing_file_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);destination=root/release.APK_NAME
            destination.write_bytes(b'previous copy')
            def invalid(url,path):path.write_bytes(b'interrupted or corrupted download')
            with self.assertRaises(ValueError):release.download_apk(root,invalid)
            self.assertEqual(destination.read_bytes(),b'previous copy')
            self.assertEqual(list(root.iterdir()),[destination])

    def test_verified_download_is_published_and_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);payload=b'fixture signed release bytes';seen=[]
            def fetch(url,path):seen.append(url);path.write_bytes(payload)
            with patch.object(release,'APK_SHA256',hashlib.sha256(payload).hexdigest()):
                path=release.download_apk(root,fetch)
                self.assertEqual(path.read_bytes(),payload)
                self.assertEqual(release.download_apk(root,fetch),path)
                self.assertEqual(seen,[release.APK_URL])
                self.assertEqual(list(root.iterdir()),[path])


if __name__=='__main__':unittest.main()
