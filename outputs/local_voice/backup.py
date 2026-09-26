"""Private SQLite snapshot and non-overwriting restore for moving a DreamType host."""
import argparse
import json
import secrets
import sqlite3
import tempfile
import zipfile
import io
import hashlib
import time
import re
from private_crypto import key_file,encrypt,decrypt
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path

FILES={'accounts.sqlite3','admin.key','local-voice.key','manifest.json'}

def export_deletions(root):
    """Export an encrypted, separate deletion ledger for reconciling old backups."""
    work=root/'work';exported_at=time.time()
    database=(work/'beta/accounts.sqlite3').resolve().as_uri()+'?mode=ro'
    with closing(sqlite3.connect(database,uri=True)) as db:
        rows=db.execute('SELECT uid,deleted_at FROM deletions ORDER BY uid').fetchall()
    payload={'format':1,'exported_at':exported_at,
        'host':hashlib.sha256((work/'local-voice.key').read_bytes().strip()).hexdigest(),
        'deletions':rows}
    target=work/'backups/latest-deletions.dtledger';target.parent.mkdir(exist_ok=True)
    temporary=target.with_name('deletions-'+secrets.token_hex(8)+'.tmp')
    try:
        temporary.write_bytes(b'DTD1'+encrypt(key_file(work/'backup-recovery.key'),
            json.dumps(payload).encode(),b'DreamType deletions v1'))
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target

def read_deletions(ledger,recovery_key,host_key,minimum_time=0):
    if ledger.stat().st_size>16*1024*1024:raise ValueError('Deletion ledger is too large.')
    data=ledger.read_bytes()
    if not data.startswith(b'DTD1'):raise ValueError('Invalid deletion ledger.')
    if recovery_key is None:raise ValueError('Deletion ledger requires the recovery key.')
    payload=json.loads(decrypt(Path(recovery_key).read_bytes(),data[4:],b'DreamType deletions v1'))
    if payload.get('format')!=1 or payload.get('host')!=hashlib.sha256(host_key.strip()).hexdigest():
        raise ValueError('Deletion ledger belongs to another host or has an unsupported format.')
    exported_at=payload.get('exported_at')
    if type(exported_at) not in (int,float) or not minimum_time<=exported_at<=time.time()+300:
        raise ValueError('Deletion ledger predates this backup or has an invalid export time; obtain a newer ledger.')
    rows=payload.get('deletions')
    if not isinstance(rows,list) or any(not isinstance(row,list) or len(row)!=2 or
        not isinstance(row[0],str) or not re.fullmatch('[0-9a-f]{32}',row[0]) or
        type(row[1]) not in (int,float) or not 0<row[1]<=time.time()+300 for row in rows):
        raise ValueError('Invalid deletion records.')
    return rows

def create(root):
    work=root/'work';database=work/'beta/accounts.sqlite3'
    if not database.exists():raise ValueError('Start DreamType once before creating a backup.')
    keys={'admin.key':work/'beta/admin.key','local-voice.key':work/'local-voice.key'}
    contents={name:p.read_bytes() for name,p in keys.items()}
    target=work/'backups';target.mkdir(exist_ok=True)
    archive=target/('beta-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3)+'.dtbackup')
    with tempfile.TemporaryDirectory(dir=target) as temp:
        copy=Path(temp)/'accounts.sqlite3'
        with closing(sqlite3.connect(database)) as source,closing(sqlite3.connect(copy)) as destination:source.backup(destination)
        with closing(sqlite3.connect(copy)) as db,db:
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'receipts' in tables:
                db.execute("UPDATE jobs SET state='failed' WHERE state='done' AND EXISTS (SELECT 1 FROM receipts r WHERE r.uid=jobs.uid AND r.id=jobs.id AND r.confirmed=0)")
            for table in ('results','sessions','reset_codes','receipts','pending_audio'):
                if table in tables:db.execute('DELETE FROM '+table)
        with closing(sqlite3.connect(copy)) as db:db.execute('VACUUM')
        contents['accounts.sqlite3']=copy.read_bytes()
    contents['manifest.json']=json.dumps({'format':1,'snapshot_completed_at':time.time(),'contains_secrets':True,'audio_included':False,'transcripts_included':False}).encode()
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as package:
        for name,data in contents.items():package.writestr(name,data)
    pending=archive.with_suffix('.verifying')
    try:
        pending.write_bytes(b'DTB1'+encrypt(key_file(work/'backup-recovery.key'),buffer.getvalue(),b'DreamType backup v1'))
        export_deletions(root)
        verify(root,pending,work/'backup-recovery.key')
        pending.replace(archive)
    finally:
        pending.unlink(missing_ok=True)
    return archive

def restore(root,archive,recovery_key=None,deletion_ledger=None):
    work=root/'work';beta=work/'beta';key=work/'local-voice.key'
    if beta.exists() and any(beta.iterdir()):raise ValueError('Refusing to overwrite existing work/beta. Restore only to a new host directory before starting it.')
    if archive.stat().st_size>256*1024*1024:raise ValueError('Backup exceeds supported size.')
    data=archive.read_bytes()
    if data.startswith(b'DTB1'):
        if recovery_key is None:raise ValueError('Encrypted backup requires the separately stored recovery key.')
        data=decrypt(Path(recovery_key).read_bytes(),data[4:],b'DreamType backup v1')
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        if len(package.namelist())!=len(FILES) or set(package.namelist())!=FILES:raise ValueError('Unexpected backup contents.')
        if any(i.file_size>64*1024*1024 for i in package.infolist()):raise ValueError('Backup exceeds supported size.')
        contents={name:package.read(name) for name in FILES}
    manifest=json.loads(contents['manifest.json'])
    if manifest.get('format')!=1:raise ValueError('Unsupported backup format.')
    snapshot_time=manifest.get('snapshot_completed_at',0)
    if type(snapshot_time) not in (int,float) or not 0<=snapshot_time<=time.time()+300:raise ValueError('Invalid backup timestamp.')
    for name in ('admin.key','local-voice.key'):
        value=contents[name].strip()
        if not 32<=len(value)<=128 or not all(c in b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in value):raise ValueError('Invalid key format.')
    if key.exists() and key.read_bytes().strip()!=contents['local-voice.key'].strip():raise ValueError('Existing host key differs; refusing to replace it.')
    ledger=Path(deletion_ledger) if deletion_ledger else archive.parent/'latest-deletions.dtledger'
    if not ledger.is_file():raise ValueError('Restore requires the latest deletion ledger; export it on the source host and supply --deletion-ledger.')
    deletions=read_deletions(ledger,recovery_key,contents['local-voice.key'],snapshot_time)
    work.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as temp:
        path=Path(temp)/'accounts.sqlite3';path.write_bytes(contents['accounts.sqlite3'])
        with closing(sqlite3.connect(path)) as db,db:
            db.execute('PRAGMA foreign_keys=ON')
            if db.execute('PRAGMA user_version').fetchone()[0]>4:raise ValueError('Backup database is newer than this restore tool.')
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid database.')
            if db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Invalid database references.')
            db.execute('DELETE FROM sessions')
            db.execute("UPDATE jobs SET state='failed' WHERE state IN ('queued','running')")
            db.execute('CREATE TABLE IF NOT EXISTS deletions(uid TEXT PRIMARY KEY,deleted_at REAL NOT NULL)')
            for uid,deleted_at in deletions:
                db.execute('INSERT OR REPLACE INTO deletions(uid,deleted_at) VALUES(?,?)',(uid,deleted_at))
            has_audit=db.execute("SELECT 1 FROM sqlite_master WHERE name='audit'").fetchone()
            for uid, in db.execute('SELECT uid FROM deletions').fetchall():
                db.execute('DELETE FROM users WHERE id=?',(uid,))
                if has_audit:db.execute('DELETE FROM audit WHERE uid=?',(uid,))
            db.execute('PRAGMA user_version=4')
        with closing(sqlite3.connect(path)) as db:db.execute('VACUUM')
        beta.mkdir(exist_ok=True)
        # Targets are known filenames in a new host directory; never extract arbitrary ZIP paths.
        (beta/'accounts.sqlite3').write_bytes(path.read_bytes())
        (beta/'admin.key').write_bytes(contents['admin.key'])
        key.write_bytes(contents['local-voice.key'])
    return beta


def verify(root,archive,recovery_key=None,deletion_ledger=None):
    """Exercise real restore in a temporary host, never the live database.

    This proves local decrypt/restore at this moment, not offsite durability,
    source completeness, or that a separately supplied ledger is the latest.
    """
    work=root/'work';work.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='restore-check-',dir=work) as directory:
        restored=restore(Path(directory),archive,recovery_key,deletion_ledger)
        with closing(sqlite3.connect((restored/'accounts.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)) as db:
            tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ('sessions','results','reset_codes','receipts','pending_audio'):
                if table in tables and db.execute('SELECT count(*) FROM '+table).fetchone()[0]:
                    raise ValueError('Restored snapshot contains transient private data.')
            if db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]:
                raise ValueError('Restored snapshot contains active jobs.')
            if db.execute('SELECT count(*) FROM users u JOIN deletions d ON d.uid=u.id').fetchone()[0]:
                raise ValueError('Restored snapshot resurrected deleted accounts.')
    return {'verified':True,'scope':'local isolated restore','archive':archive.name}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['create','restore','verify','export-deletions']);parser.add_argument('--archive',type=Path);parser.add_argument('--recovery-key',type=Path);parser.add_argument('--deletion-ledger',type=Path)
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    if args.action in ('restore','verify') and not args.archive:parser.error(args.action+' requires --archive')
    if args.action=='verify':
        print(json.dumps(verify(root,args.archive,args.recovery_key,args.deletion_ledger)))
        raise SystemExit(0)
    result=create(root) if args.action=='create' else export_deletions(root) if args.action=='export-deletions' else restore(root,args.archive,args.recovery_key,args.deletion_ledger)
    print(str(result))
    if args.action=='export-deletions':
        print('Encrypted deletion ledger exported. Keep the latest copy; store its recovery key separately.')
    else:
        print('Private backup contains account data and host keys. Restored accounts must log in again.')
