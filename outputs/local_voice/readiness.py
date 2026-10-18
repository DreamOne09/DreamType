"""Read-only readiness report. Evidence is not inferred from source code or feature counts."""
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path
import httpx

def inspect(root):
    work=root/'work';report={'public_paid_production':False,'checks':{},'remaining':[
        'Pixel 9 native keyboard, Keystore, background and cellular testing',
        'Host sleep/power-loss drills and external outage alerts',
        'Full restore on another device and separately retained recovery key',
        'Sustained real-audio load and recovery testing',
        'Independent security review and backup deletion policy',
        'Play Console, real Billing purchase/RTDN/refund tests and store disclosures',
        'Apple Developer, Mac/iPhone, iOS implementation and App Store acceptance']}
    try:
        with closing(sqlite3.connect(f"file:{(work/'beta/accounts.sqlite3').as_posix()}?mode=ro",uri=True)) as db:
            report['checks']['database_integrity']=db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            report['checks']['schema_version']=db.execute('PRAGMA user_version').fetchone()[0]
    except Exception:report['checks']['database_integrity']=False
    try:report['checks']['health']=httpx.get('http://127.0.0.1:19870/health',timeout=5).json()
    except Exception:report['checks']['health']='unavailable'
    try:report['checks']['maintenance']=json.loads((work/'maintenance-status.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):report['checks']['maintenance']='not_run'
    state=report['checks']['maintenance']
    state=state if isinstance(state,dict) else {}
    timestamp=state.get('last_r2_sync')
    recent=(type(timestamp) in (int,float) and 0 <= time.time()-timestamp <= 900)
    report['checks']['cloud_backup']={
        'enabled_reported':state.get('r2_enabled') is True,
        'recent_verified_sync_reported':state.get('r2_enabled') is True and recent,
        'last_verified_sync':timestamp if type(timestamp) in (int,float) else None,
        'independent_restore_verified':False,
        'recovery_key_off_machine_verified':False}
    try:
        config=json.loads((work/'tunnel-config.json').read_text(encoding='utf-8'))
        mode=config.get('mode') if isinstance(config,dict) else None
    except (OSError,ValueError):mode=None
    report['checks']['tunnel_mode']=mode if mode in ('named','quick') else 'unknown'
    # Configuration is not DNS reachability or an uptime guarantee.
    if mode!='named':report['remaining'].append('Configure and verify a fixed service hostname')
    if not report['checks']['cloud_backup']['recent_verified_sync_reported']:
        report['remaining'].append('Verify current encrypted off-machine backup synchronization')
    report['checks']['encrypted_backup_count']=len(list((work/'backups').glob('*.dtbackup')))
    return report

if __name__=='__main__':print(json.dumps(inspect(Path(__file__).resolve().parents[2]),ensure_ascii=False,indent=2))
