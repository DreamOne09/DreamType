"""One bounded maintenance pass; intended for Windows Task Scheduler every five minutes."""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
import httpx
from backup import create

ROOT=Path(__file__).resolve().parents[2]

def run(root=ROOT):
    work=root/'work';state_path=work/'maintenance-status.json'
    try:state=json.loads(state_path.read_text())
    except (OSError,ValueError):state={}
    now=time.time();state['checked_at']=now;state['errors']=[]
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
    if now-state.get('last_backup',0)>86400:
        try:
            archive=create(root)
            state['last_backup']=now;state['backup_file']=archive.name
            # Optional local sync folder. No cloud credentials or recovery keys are copied.
            config=work/'backup-config.json'
            if config.exists():
                target=Path(json.loads(config.read_text())['sync_directory'])
                if not target.is_dir():raise ValueError('Backup destination must already exist')
                shutil.copy2(archive,target/archive.name)
                state['last_backup_copy']=now
        except Exception:
            state['errors'].append('backup_or_copy_failed')
            state['last_backup']=0  # Retry at the next maintenance pass.
    temporary=state_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,indent=2),encoding='utf-8');temporary.replace(state_path)
    return state

if __name__=='__main__':
    result=run();print(json.dumps(result,indent=2));sys.exit(1 if result['errors'] else 0)
