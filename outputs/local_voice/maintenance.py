"""One bounded maintenance pass; intended for Windows Task Scheduler every five minutes."""
import json
import hashlib
import argparse
import shutil
import subprocess
import sys
import time
import secrets
from pathlib import Path
from contextlib import closing
import httpx
import psutil
from backup import create,export_deletions
from backup_inventory import inventory
from process_lock import exclusive,LockBusy
from r2_config import read_config,client_for
from r2_sync import sync_latest

ROOT=Path(__file__).resolve().parents[2]

def copy_encrypted(source,target):
    """Publish a complete encrypted file without truncating the previous copy."""
    if source.suffix not in ('.dtbackup','.dtledger') or not target.is_dir():
        raise ValueError('Expected encrypted backup and existing sync directory')
    destination=target/source.name
    if source.resolve()==destination.resolve():
        raise ValueError('Backup copy destination must differ from source')
    temporary=target/(source.name+'.'+secrets.token_hex(8)+'.uploading')
    try:
        shutil.copy2(source,temporary)
        # Verify complete bytes before replacing the last usable copy. This
        # proves only the local destination, not a cloud provider's upload.
        with source.open('rb') as original, temporary.open('rb') as copied:
            if hashlib.file_digest(original,'sha256').digest()!=hashlib.file_digest(copied,'sha256').digest():
                raise ValueError('Encrypted backup copy verification failed')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)

def run(root=ROOT,force_backup=False):
    root=Path(root)
    try:
        with exclusive(root/'work/maintenance.lock'):
            return _run(root,force_backup)
    except LockBusy:
        return {'skipped':'maintenance_already_running','errors':[]}


def _run(root,force_backup=False):
    work=root/'work';state_path=work/'maintenance-status.json'
    try:state=json.loads(state_path.read_text())
    except (OSError,ValueError):state={}
    now=time.time();state['checked_at']=now;state['errors']=[]
    try:state['disk_free_bytes']=shutil.disk_usage(work).free
    except OSError:state['disk_free_bytes']=None
    try:
        memory=psutil.virtual_memory()
        state['memory_available_bytes']=memory.available
        state['memory_total_bytes']=memory.total
    except (OSError,psutil.Error):
        state['memory_available_bytes']=None;state['memory_total_bytes']=None
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
                state['last_backup_copy_verified']=now
                state['backup_copy_verified_file']=archive.name
        except Exception:
            state['errors'].append('backup_or_copy_failed')
            state['last_backup']=0
    # Refresh separately from daily backups, so an older archive can be safely
    # reconciled with later account deletions. A local copy is not cloud proof.
    ledger=None
    try:
        ledger=export_deletions(root)
        state['last_deletion_export']=now
        config=work/'backup-config.json'
        if config.exists():
            target=Path(json.loads(config.read_text())['sync_directory'])
            if not target.is_dir():raise ValueError('Backup destination must already exist')
            copy_encrypted(ledger,target)
            state['last_deletion_copy']=now
            state['last_deletion_copy_verified']=now
    except Exception:
        state['errors'].append('deletion_export_or_copy_failed')
    state['r2_enabled']=False
    if (work/'r2-config.json').exists():
        try:
            config=read_config(root);state['r2_enabled']=config['enabled']
            if config['enabled']:
                name=state.get('backup_file','')
                if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.dtbackup') or ledger is None:
                    raise ValueError('A verified backup and fresh deletion ledger are required')
                with closing(client_for(root,config)) as client:
                    remote=sync_latest(client,config['bucket'],root,work/'backups'/name,work/'backup-recovery.key',ledger)
                state['last_r2_sync']=remote['checked_at'];state['r2_ledger_at']=remote['ledger_at']
                state['r2_backup_file']=name;state['r2_archive_sha256']=remote['archive_sha256']
                state['r2_deletion_export']=state['last_deletion_export']
        except Exception:
            state['errors'].append('r2_sync_failed')
    state['backup_inventory']=inventory(work/'backups')
    temporary=state_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,indent=2),encoding='utf-8');temporary.replace(state_path)
    return state

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-now',action='store_true',help='Create and restore-verify a fresh backup during this maintenance pass')
    args=parser.parse_args()
    result=run(force_backup=args.backup_now);print(json.dumps(result,indent=2));sys.exit(1 if result['errors'] else 0)
