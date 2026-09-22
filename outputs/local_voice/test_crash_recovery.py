"""Abrupt-process-exit checks against isolated SQLite databases, never the live host."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from beta_store import Store

CHILD = r"""
import os, sys
from pathlib import Path
from beta_store import Store
store=Store(Path(sys.argv[1]))
uid=store.create('crash-test','synthetic-password-12345')
store.reserve(uid,'crash-request-123456','synthetic-digest',10)
store.save_pending(uid,'crash-request-123456',b'synthetic-audio',{'mode':'translate','target_language':'ja','source_language':'zh-TW'},True)
store.state(uid,'crash-request-123456','running')
phase=sys.argv[2]
if phase=='uncommitted':
    with store.db() as db:
        db.execute("UPDATE jobs SET state='done' WHERE uid=?",(uid,))
        db.execute('DELETE FROM pending_audio WHERE uid=?',(uid,))
        os._exit(23)
if phase=='completed':
    store.complete(uid,'crash-request-123456',{'text':'synthetic-result','mode':'translate','target_language':'ja'})
os._exit(23)
"""


class CrashRecoveryTests(unittest.TestCase):
    def test_abrupt_exit_restores_pending_or_committed_result(self):
        for phase in ('running', 'uncommitted', 'completed'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/'accounts.sqlite3'
                child = subprocess.run([sys.executable,'-c',CHILD,str(path),phase],
                    cwd=Path(__file__).resolve().parent, capture_output=True, timeout=20)
                self.assertEqual(child.returncode,23,child.stderr.decode(errors='replace'))
                store=Store(path)
                with store.db() as db:
                    self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                    uid=db.execute("SELECT id FROM users WHERE name='crash-test'").fetchone()[0]
                store.recover()
                jid='crash-request-123456'
                if phase=='completed':
                    self.assertEqual(store.job(uid,jid)['state'],'done')
                    self.assertEqual(store.result(uid,jid)['text'],'synthetic-result')
                    self.assertEqual(list(store.pending()),[])
                else:
                    self.assertEqual(store.job(uid,jid)['state'],'queued')
                    pending=list(store.pending())
                    self.assertEqual(len(pending),1)
                    self.assertEqual(pending[0],(uid,jid,b'synthetic-audio',{'mode':'translate','target_language':'ja','source_language':'zh-TW'}))
                    self.assertEqual(store.me(uid)['used_seconds'],0)
                    self.assertEqual(store.me(uid)['reserved_seconds'],10)
                    store.state(uid,jid,'running')
                    store.complete(uid,jid,{'text':'synthetic-result'})
                store.receipt(uid,jid)
                store.receipt(uid,jid)
                self.assertEqual(store.me(uid)['used_seconds'],10)
                self.assertEqual(store.me(uid)['reserved_seconds'],0)
                self.assertNotIn(b'synthetic-audio',path.read_bytes())
                self.assertNotIn(b'synthetic-result',path.read_bytes())


if __name__=='__main__':
    unittest.main()
