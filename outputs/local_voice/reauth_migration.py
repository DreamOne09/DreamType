"""Explicit offline schema 11 -> 12 preparation for account-deletion reauthentication."""
from contextlib import closing
from pathlib import Path
import sqlite3
from billing_migration import _require_offline,validate_billing_schema
from backup import create
from process_lock import exclusive

TABLES={'deletion_challenges': "CREATE TABLE deletion_challenges(id TEXT PRIMARY KEY,uid TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,session TEXT NOT NULL REFERENCES sessions(token) ON DELETE CASCADE,secret TEXT NOT NULL,nonce TEXT NOT NULL,expires REAL NOT NULL)"}

def validate_reauth(db):
    if db.execute('PRAGMA user_version').fetchone()[0]!=12 or {r[1] for r in db.execute('PRAGMA table_info(deletion_challenges)')}!={'id','uid','session','secret','nonce','expires'}:
        raise ValueError('Explicit account reauthentication storage preparation required.')

def _upgrade(db):
    for ddl in TABLES.values():db.execute(ddl)
    db.execute('PRAGMA user_version=12');validate_reauth(db)


def prepare_reauth(root):
    root=Path(root).resolve();work=root/'work';path=work/'beta/accounts.sqlite3'
    if not path.is_file():raise ValueError('Existing schema 11 installation required.')
    _require_offline(root)
    with exclusive(work/'maintenance.lock'),closing(sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=1)) as db:
        db.execute('PRAGMA foreign_keys=ON');db.execute('BEGIN IMMEDIATE')
        try:
            if db.execute('PRAGMA user_version').fetchone()[0]!=11:raise ValueError('Schema 11 required.')
            validate_billing_schema(db)
            from notification_migration import validate_notifications
            validate_notifications(db)
            from signin_migration import validate_signin
            validate_signin(db)
            if any(db.execute("SELECT 1 FROM sqlite_master WHERE name=?",(name,)).fetchone() for name in TABLES):raise ValueError("Unexpected sign-in tables.")
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Invalid database.')
            if (db.execute("SELECT 1 FROM jobs WHERE state IN ('queued','running') LIMIT 1").fetchone()
                or db.execute('SELECT 1 FROM pending_audio LIMIT 1').fetchone()
                or db.execute('SELECT 1 FROM receipts WHERE confirmed=0 LIMIT 1').fetchone()):raise ValueError('Finish pending recordings first.')
            archive=create(root);_upgrade(db);db.commit()
        except BaseException:db.rollback();raise
    return {'previous_version':11,'version':12,'backup':str(archive),'billing_policy_unchanged':True}
