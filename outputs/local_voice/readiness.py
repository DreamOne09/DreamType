"""Read-only readiness report. Evidence is not inferred from source code or feature counts."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
import httpx

def inspect(root):
    work=root/'work';report={'public_paid_production':False,'checks':{},'remaining':[
        'Pixel 9 native keyboard, Keystore, background and cellular testing',
        'Stable service hostname and outage drills (Quick Tunnel remains temporary)',
        'Off-machine backup and separately retained recovery key',
        'Sustained real-audio load and recovery testing',
        'Independent security review and backup deletion policy',
        'Play Console, AAB, Billing purchase verification/RTDN/refunds and store disclosures']}
    try:
        with closing(sqlite3.connect(f"file:{(work/'beta/accounts.sqlite3').as_posix()}?mode=ro",uri=True)) as db:
            report['checks']['database_integrity']=db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            report['checks']['schema_version']=db.execute('PRAGMA user_version').fetchone()[0]
    except Exception:report['checks']['database_integrity']=False
    try:report['checks']['health']=httpx.get('http://127.0.0.1:19870/health',timeout=5).json()
    except Exception:report['checks']['health']='unavailable'
    try:report['checks']['maintenance']=json.loads((work/'maintenance-status.json').read_text())
    except (OSError,ValueError):report['checks']['maintenance']='not_run'
    report['checks']['encrypted_backup_count']=len(list((work/'backups').glob('*.dtbackup')))
    return report

if __name__=='__main__':print(json.dumps(inspect(Path(__file__).resolve().parents[2]),ensure_ascii=False,indent=2))
