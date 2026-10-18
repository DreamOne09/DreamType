"""Explicit offline schema 9 -> 10 preparation for notification deduplication."""
from contextlib import closing
from pathlib import Path
import sqlite3
from billing_migration import _require_offline,validate_billing_schema
from backup import create
from process_lock import exclusive

DDL='''CREATE TABLE play_notifications(message_hash TEXT PRIMARY KEY,payload_hash TEXT NOT NULL,
uid TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,created REAL NOT NULL)'''

def validate_notifications(db):
    if db.execute('PRAGMA user_version').fetchone()[0] not in (10,11) or {r[1] for r in db.execute('PRAGMA table_info(play_notifications)')}!={'message_hash','payload_hash','uid','created'}:
        raise ValueError('Explicit notification storage preparation required.')

def _upgrade(db):
    db.execute(DDL);db.execute('PRAGMA user_version=10');validate_notifications(db)

def prepare_notifications(root):
    root=Path(root).resolve();work=root/'work';path=work/'beta/accounts.sqlite3'
    if not path.is_file():raise ValueError('Existing schema 9 installation required.')
    _require_offline(root)
    with exclusive(work/'maintenance.lock'),closing(sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=1)) as db:
        db.execute('PRAGMA foreign_keys=ON');db.execute('BEGIN IMMEDIATE')
        try:
            if db.execute('PRAGMA user_version').fetchone()[0]!=9:raise ValueError('Schema 9 required.')
            validate_billing_schema(db)
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Invalid database.')
            if (db.execute("SELECT 1 FROM jobs WHERE state IN ('queued','running') LIMIT 1").fetchone()
                or db.execute('SELECT 1 FROM pending_audio LIMIT 1').fetchone()
                or db.execute('SELECT 1 FROM receipts WHERE confirmed=0 LIMIT 1').fetchone()):raise ValueError('Finish pending recordings first.')
            archive=create(root);_upgrade(db);db.commit()
        except BaseException:db.rollback();raise
    return {'previous_version':9,'version':10,'backup':str(archive),'billing_policy_unchanged':True}
