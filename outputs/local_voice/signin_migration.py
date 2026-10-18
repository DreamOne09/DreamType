"""Explicit offline schema 10 -> 11 preparation for self-service identity."""
from contextlib import closing
from pathlib import Path
import sqlite3
from billing_migration import _require_offline,validate_billing_schema
from backup import create
from process_lock import exclusive

TABLES={
 'login_identities': "CREATE TABLE login_identities(provider TEXT NOT NULL,subject TEXT NOT NULL,uid TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,PRIMARY KEY(provider,subject),UNIQUE(provider,uid))",
 'login_challenges': "CREATE TABLE login_challenges(id TEXT PRIMARY KEY,secret TEXT NOT NULL,nonce TEXT NOT NULL,purpose TEXT NOT NULL CHECK(purpose IN ('signin','signup')),expires REAL NOT NULL)"
}
COLUMNS={'login_identities':{'provider','subject','uid'},'login_challenges':{'id','secret','nonce','purpose','expires'}}

def validate_signin(db):
    if db.execute('PRAGMA user_version').fetchone()[0]!=11:
        raise ValueError('Explicit sign-in storage preparation required.')
    for name,columns in COLUMNS.items():
        if {r[1] for r in db.execute('PRAGMA table_info('+name+')')}!=columns:
            raise ValueError('Invalid sign-in storage.')

def _upgrade(db):
    for ddl in TABLES.values():db.execute(ddl)
    db.execute('PRAGMA user_version=11');validate_signin(db)


def prepare_signin(root):
    root=Path(root).resolve();work=root/'work';path=work/'beta/accounts.sqlite3'
    if not path.is_file():raise ValueError('Existing schema 10 installation required.')
    _require_offline(root)
    with exclusive(work/'maintenance.lock'),closing(sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=1)) as db:
        db.execute('PRAGMA foreign_keys=ON');db.execute('BEGIN IMMEDIATE')
        try:
            if db.execute('PRAGMA user_version').fetchone()[0]!=10:raise ValueError('Schema 10 required.')
            validate_billing_schema(db)
            from notification_migration import validate_notifications
            validate_notifications(db)
            if any(db.execute("SELECT 1 FROM sqlite_master WHERE name=?",(name,)).fetchone() for name in TABLES):raise ValueError("Unexpected sign-in tables.")
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Invalid database.')
            if (db.execute("SELECT 1 FROM jobs WHERE state IN ('queued','running') LIMIT 1").fetchone()
                or db.execute('SELECT 1 FROM pending_audio LIMIT 1').fetchone()
                or db.execute('SELECT 1 FROM receipts WHERE confirmed=0 LIMIT 1').fetchone()):raise ValueError('Finish pending recordings first.')
            archive=create(root);_upgrade(db);db.commit()
        except BaseException:db.rollback();raise
    return {'previous_version':10,'version':11,'backup':str(archive),'billing_policy_unchanged':True}
