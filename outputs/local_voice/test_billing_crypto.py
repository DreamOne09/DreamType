from pathlib import Path
import tempfile
import unittest
from cryptography.exceptions import InvalidTag
from billing_crypto import BillingCipher
from beta_store import Store
from backup import create,restore,verify
from billing_migration import prepare_storage
from contextlib import closing
import sqlite3
import time


class BillingCryptoTests(unittest.TestCase):
    def test_schema_nine_restore_preserves_token_and_requires_fresh_verification(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'source';work=root/'work';beta=work/'beta'
            store=Store(beta/'accounts.sqlite3');uid=store.create('alice','fixture-password')
            (beta/'admin.key').write_text('a'*43);(work/'local-voice.key').write_text('b'*43)
            prepare_storage(root)
            cipher=BillingCipher(beta);digest,payload=cipher.seal(uid,'fixture-purchase-secret')
            with store.db() as db:
                db.execute('INSERT INTO play_subscriptions VALUES(?,?,?,?,?,?,?,?)',(digest,uid,payload,'{}',1,1,0,time.time()))
            archive=create(root)
            destination=restore(Path(d)/'restored',archive,work/'backup-recovery.key')
            with closing(sqlite3.connect(destination/'accounts.sqlite3')) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],9)
                row=db.execute('SELECT uid,digest,token,needs_refresh FROM play_subscriptions').fetchone()
                self.assertEqual(row[3],1)
                self.assertEqual(BillingCipher(destination,existing_records=True).open(*row[:3]),'fixture-purchase-secret')
            self.assertNotIn(b'fixture-purchase-secret',archive.read_bytes())
            archives=set((work/'backups').glob('*.dtbackup'))
            (beta/'billing.key').unlink()
            with self.assertRaisesRegex(ValueError,'original billing key'):create(root)
            (beta/'billing.key').write_bytes(b'x'*32)
            with self.assertRaises(InvalidTag):create(root)
            self.assertEqual(set((work/'backups').glob('*.dtbackup')),archives)
            self.assertEqual(list((work/'backups').glob('*.verifying')),[])

    def test_key_survives_backup_and_restore_to_new_host(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'source';work=root/'work';beta=work/'beta'
            store=Store(beta/'accounts.sqlite3');uid=store.create('alice','fixture-password')
            (beta/'admin.key').write_text('a'*43);(work/'local-voice.key').write_text('b'*43)
            cipher=BillingCipher(beta);digest,payload=cipher.seal(uid,'fixture-purchase-secret')
            archive=create(root)
            self.assertTrue(verify(root,archive,work/'backup-recovery.key')['verified'])
            restored=restore(Path(d)/'destination',archive,work/'backup-recovery.key')
            self.assertEqual(BillingCipher(restored,existing_records=True).open(uid,digest,payload),'fixture-purchase-secret')
            self.assertFalse((restored/'payload.key').exists())
            self.assertNotIn(b'fixture-purchase-secret',archive.read_bytes())

    def test_context_tampering_and_missing_key_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            beta=Path(d);cipher=BillingCipher(beta)
            digest,payload=cipher.seal('alice','fixture-purchase')
            for uid,key,blob in [('bob',digest,payload),('alice','0'*64,payload),('alice',digest,payload[:-1]+bytes([payload[-1]^1]))]:
                with self.assertRaises(InvalidTag):cipher.open(uid,key,blob)
            (beta/'billing.key').unlink()
            with self.assertRaises(ValueError):BillingCipher(beta,existing_records=True)
            self.assertFalse((beta/'billing.key').exists())


if __name__=='__main__':unittest.main()
