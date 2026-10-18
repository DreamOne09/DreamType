"""Explicit, offline billing storage preparation; never runs on import/startup.

The current schema-4 server must remain stopped after a successful preparation.
This module does not enable billing or change user allowances. Deploy the
billing-aware server before restarting, or restore the saved encrypted snapshot
into a new directory. Never downgrade a database in place.
"""
from contextlib import closing
from pathlib import Path
import sqlite3
import psutil
from backup import create
from process_lock import exclusive

TARGET_VERSION = 9
TABLES = {
    'purchase_claims': '''CREATE TABLE purchase_claims(provider TEXT NOT NULL,
        digest TEXT NOT NULL,uid TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created REAL NOT NULL,PRIMARY KEY(provider,digest))''',
    'play_subscriptions': '''CREATE TABLE play_subscriptions(digest TEXT PRIMARY KEY,
        uid TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token BLOB NOT NULL,snapshot TEXT NOT NULL,revision INTEGER NOT NULL,
        ack_pending INTEGER NOT NULL,needs_refresh INTEGER NOT NULL DEFAULT 0,
        checked_at REAL NOT NULL)''',
    'billing_retry': '''CREATE TABLE billing_retry(digest TEXT PRIMARY KEY REFERENCES play_subscriptions(digest) ON DELETE CASCADE,
        revision INTEGER NOT NULL,attempts INTEGER NOT NULL,next_attempt REAL NOT NULL)''',
    'play_replacements': '''CREATE TABLE play_replacements(old_digest TEXT PRIMARY KEY,new_digest TEXT NOT NULL UNIQUE,
        uid TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE)''',
    'billing_mode': '''CREATE TABLE billing_mode(required INTEGER PRIMARY KEY CHECK(required=1))''',
}
COLUMNS = {
    'purchase_claims': {'provider','digest','uid','created'},
    'play_subscriptions': {'digest','uid','token','snapshot','revision','ack_pending','needs_refresh','checked_at'},
    'billing_retry': {'digest','revision','attempts','next_attempt'},
    'play_replacements': {'old_digest','new_digest','uid'},
    'billing_mode': {'required'},
}

def validate_billing_schema(db):
    for name,columns in COLUMNS.items():
        if {row[1] for row in db.execute('PRAGMA table_info('+name+')')}!=columns:
            raise ValueError('Incomplete or unsupported billing database.')

def _require_offline(root):
    expected=(root/'outputs/local_voice').resolve()
    for process in psutil.process_iter(['cmdline']):
        args=process.info['cmdline'] or []
        if 'uvicorn' in args and '--app-dir' in args:
            i=args.index('--app-dir')+1
            if i<len(args) and Path(args[i]).resolve()==expected:
                raise ValueError('Stop this installation gateway before preparing billing storage.')

def _check_base(db):
    if db.execute('PRAGMA user_version').fetchone()[0]!=4:
        raise ValueError('Billing preparation requires an unmodified schema-4 database.')
    tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required={'users','sessions','jobs','results','audit','reset_codes','receipts','pending_audio','deletions'}
    if not required<=tables or set(TABLES)&tables:
        raise ValueError('Unexpected or partially migrated database.')
    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('Database integrity must pass before migration.')
    if (db.execute("SELECT 1 FROM jobs WHERE state IN ('queued','running') LIMIT 1").fetchone()
            or db.execute('SELECT 1 FROM pending_audio LIMIT 1').fetchone()
            or db.execute('SELECT 1 FROM receipts WHERE confirmed=0 LIMIT 1').fetchone()):
        raise ValueError('Finish or recover pending recordings and receipts before migration.')

def _upgrade(db):
    # execute(), not executescript(): every DDL statement stays in the caller's
    # transaction, including user_version. An exception/crash rolls all of it back.
    for statement in TABLES.values():db.execute(statement)
    validate_billing_schema(db)
    db.execute('PRAGMA user_version=9')
    if db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Invalid migrated references.')

def prepare_storage(root):
    root=Path(root).resolve();work=root/'work';database=work/'beta/accounts.sqlite3'
    if not database.is_file():raise ValueError('An existing schema-4 installation is required.')
    _require_offline(root)
    with exclusive(work/'maintenance.lock'),closing(sqlite3.connect(database.as_uri()+'?mode=rw',uri=True,timeout=1)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        try:
            _check_base(db)
            # Hold the writer reservation while snapshotting through a second
            # read connection. create() encrypts and restore-verifies the backup
            # before returning; it never writes the source database.
            archive=create(root)
            _upgrade(db)
            db.commit()
        except BaseException:
            db.rollback()
            raise
    return {'previous_version':4,'version':TARGET_VERSION,'backup':str(archive),
            'billing_enabled':False,'restart_requires_billing_aware_server':True}
