"""Private SQLite snapshot and non-overwriting restore for moving a DreamType host."""
import argparse
import json
import secrets
import sqlite3
import tempfile
import zipfile
import io
from private_crypto import key_file,encrypt,decrypt
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path

FILES={'accounts.sqlite3','admin.key','local-voice.key','manifest.json'}

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
            for table in ('results','sessions','reset_codes','receipts'):
                if table in tables:db.execute('DELETE FROM '+table)
        with closing(sqlite3.connect(copy)) as db:db.execute('VACUUM')
        contents['accounts.sqlite3']=copy.read_bytes()
    contents['manifest.json']=json.dumps({'format':1,'contains_secrets':True,'audio_included':False,'transcripts_included':False}).encode()
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as package:
        for name,data in contents.items():package.writestr(name,data)
    archive.write_bytes(b'DTB1'+encrypt(key_file(work/'backup-recovery.key'),buffer.getvalue(),b'DreamType backup v1'))
    return archive

def restore(root,archive,recovery_key=None):
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
    if json.loads(contents['manifest.json']).get('format')!=1:raise ValueError('Unsupported backup format.')
    for name in ('admin.key','local-voice.key'):
        value=contents[name].strip()
        if not 32<=len(value)<=128 or not all(c in b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in value):raise ValueError('Invalid key format.')
    if key.exists() and key.read_bytes().strip()!=contents['local-voice.key'].strip():raise ValueError('Existing host key differs; refusing to replace it.')
    work.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as temp:
        path=Path(temp)/'accounts.sqlite3';path.write_bytes(contents['accounts.sqlite3'])
        with closing(sqlite3.connect(path)) as db,db:
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid database.')
            if db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Invalid database references.')
            db.execute('DELETE FROM sessions')
            db.execute("UPDATE jobs SET state='failed' WHERE state IN ('queued','running')")
        beta.mkdir(exist_ok=True)
        # Targets are known filenames in a new host directory; never extract arbitrary ZIP paths.
        (beta/'accounts.sqlite3').write_bytes(path.read_bytes())
        (beta/'admin.key').write_bytes(contents['admin.key'])
        key.write_bytes(contents['local-voice.key'])
    return beta

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['create','restore']);parser.add_argument('--archive',type=Path);parser.add_argument('--recovery-key',type=Path)
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    if args.action=='restore' and not args.archive:parser.error('restore requires --archive')
    result=create(root) if args.action=='create' else restore(root,args.archive,args.recovery_key)
    print(str(result))
    print('Private backup contains account data and host keys. Restored accounts must log in again.')
