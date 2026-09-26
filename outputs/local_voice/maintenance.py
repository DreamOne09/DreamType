"""One bounded maintenance pass; intended for Windows Task Scheduler every five minutes."""
import json
import argparse
import shutil
import subprocess
import sys
import time
import secrets
from pathlib import Path
import httpx
from backup import create,export_deletions

ROOT=Path(__file__).resolve().parents[2]

def copy_encrypted(source,target):
    """Publish a complete encrypted file without truncating the previous copy."""
    if source.suffix not in ('.dtbackup','.dtledger') or not target.is_dir():
        raise ValueError('Expected encrypted backup and existing sync directory')
    destination=target/source.name
    if source.resolve()==destination.resolve():return
    temporary=target/(source.name+'.'+secrets.token_hex(8)+'.uploading')
    try:
        shutil.copy2(source,temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)

def run(root=ROOT,force_backup=False):
    work=root/'work';state_path=work/'maintenance-status.json'
    try:state=json.loads(state_path.read_text())
    except (OSError,ValueError):state={}
    now=time.time();state['checked_at']=now;state['errors']=[]
    try:state['disk_free_bytes']=shutil.disk_usage(work).free
    except OSError:state['disk_free_bytes']=None
    try:
        ready=httpx.get('http://127.0.0.1:19870/health',timeout=10).json().get('status')=='ready'
    except Exception:ready=False
    state['ready']=ready
    state['consecutive_failures']=0 if ready else state.get('consecutive_failures',0)+1
    # Two failures avoid restarting for a transient GPU warm-up. Never rapid-loop.
    if not ready and state['consecutive_failures']>=2 and now-state.get('last_restart',0)>900:
        try:
            subprocess.run([sys.executable,str(root/'outputs/local_voice/control.py'),'start'],check=True,timeout=45,capture_output=True)
            state['last_restart']=now
        except Exception:state['errors'].append('host_restart_failed')
    try:
        tunnel=httpx.get('http://127.0.0.1:19872/ready',timeout=5).status_code==200
    except Exception:tunnel=False
    state['tunnel_ready']=tunnel
    # Restarting a Quick Tunnel changes the phone URL; expose this explicitly in status.
    if not tunnel and now-state.get('last_tunnel_restart',0)>900:
        try:
            subprocess.run([sys.executable,str(root/'outputs/local_voice/control.py'),'tunnel'],check=True,timeout=45,capture_output=True)
            state['last_tunnel_restart']=now;state['phone_url_may_have_changed']=True
        except Exception:state['errors'].append('tunnel_restart_failed')
    # Create the snapshot first: create() also refreshes the local ledger.
    if force_backup or now-state.get('last_backup',0)>86400:
        try:
            archive=create(root)
            state['last_backup']=now;state['backup_file']=archive.name
            # create() validates the shared restore preparation in memory.
            state['last_backup_verified']=now;state['backup_verified_file']=archive.name
            config=work/'backup-config.json'
            if config.exists():
                target=Path(json.loads(config.read_text())['sync_directory'])
                copy_encrypted(archive,target)
                state['last_backup_copy']=now
        except Exception:
            state['errors'].append('backup_or_copy_failed')
            state['last_backup']=0
    # Refresh separately from daily backups, so an older archive can be safely
    # reconciled with later account deletions. A local copy is not cloud proof.
    try:
        ledger=export_deletions(root)
        state['last_deletion_export']=now
        config=work/'backup-config.json'
        if config.exists():
            target=Path(json.loads(config.read_text())['sync_directory'])
            if not target.is_dir():raise ValueError('Backup destination must already exist')
            copy_encrypted(ledger,target)
            state['last_deletion_copy']=now
    except Exception:
        state['errors'].append('deletion_export_or_copy_failed')
    temporary=state_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,indent=2),encoding='utf-8');temporary.replace(state_path)
    return state

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-now',action='store_true',help='Create and restore-verify a fresh backup during this maintenance pass')
    args=parser.parse_args()
    result=run(force_backup=args.backup_now);print(json.dumps(result,indent=2));sys.exit(1 if result['errors'] else 0)
