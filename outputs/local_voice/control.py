from pathlib import Path
import os
import secrets
import subprocess
import sys
import psutil
import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = ROOT / 'work'
LOGS = WORK / 'logs'
LOGS.mkdir(exist_ok=True)
KEY = WORK / 'local-voice.key'
if not KEY.exists():
    KEY.write_text(secrets.token_urlsafe(32), encoding='ascii')

def owned_processes():
    for process in psutil.process_iter(['pid', 'exe', 'cmdline']):
        args = process.info['cmdline'] or []
        exe = (process.info['exe'] or '').lower()
        gateway = False
        if 'uvicorn' in args and '--app-dir' in args:
            i = args.index('--app-dir')
            gateway = i + 1 < len(args) and Path(args[i+1]).resolve() == HERE
        engine = exe == str(WORK / 'llama/llama-server.exe').lower()
        translation = engine and '19873' in args
        tunnel = exe == str(WORK / 'cloudflared.exe').lower() and 'http://127.0.0.1:19870' in args
        if gateway or engine or tunnel:
            yield process, ('gateway' if gateway else 'translation' if translation else 'engine' if engine else 'tunnel')

def stop(kinds):
    matches = [p for p, kind in owned_processes() if kind in kinds]
    for process in matches:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(matches, timeout=5)

def spawn(name, arguments):
    env = os.environ.copy()
    paths = [str(p) for p in (WORK / 'venv/Lib/site-packages/nvidia').glob('*/bin')]
    env['PATH'] = os.pathsep.join(paths + [env.get('PATH', '')])
    env['HF_HUB_OFFLINE'] = '1'
    env['PYTHONUTF8'] = '1'
    with (LOGS / f'{name}.out.log').open('w', encoding='utf-8') as out, (LOGS / f'{name}.err.log').open('w', encoding='utf-8') as err:
        child = subprocess.Popen(arguments, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
            stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
    print(name, 'started', child.pid)

action = sys.argv[1] if len(sys.argv) > 1 else 'status'
def start_translation():
    path=WORK/'models/translategemma/translategemma-4b-it.Q4_K_M.gguf'
    if not path.exists():return
    spawn('translation',[str(WORK/'llama/llama-server.exe'),'-m',str(path),'--host','127.0.0.1','--port','19873',
        '-ngl','10','-c','2048','-np','1','-t','4','-b','128','-ub','128','--flash-attn','on','--no-jinja','--chat-template','gemma','--alias','local-translate','--no-webui','--api-key-file',str(KEY)])
if action in ('start', 'restart'):
    try:
        ready = httpx.get('http://127.0.0.1:19870/health', timeout=2).json()['status'] == 'ready'
    except Exception:
        ready = False
    if ready and action == 'start':
        print('Local Voice is already ready.')
        sys.exit(0)
    stop({'gateway', 'engine','translation'})
    spawn('llama', [str(WORK / 'llama/llama-server.exe'), '-m',
        str(WORK / 'models/qwen-instruct/Qwen3-4B-Instruct-2507-Q4_K_M.gguf'), '--host', '127.0.0.1',
        '--port', '19871', '-ngl', '99', '-c', '4096', '-np', '1',
        '--flash-attn', 'on', '--jinja', '--alias', 'local-format', '--no-webui',
        '--api-key-file', str(KEY), '--cors-origins', 'http://127.0.0.1:19870'])
    spawn('gateway', [sys.executable, '-m', 'uvicorn', 'server:app', '--app-dir', str(HERE),
        '--host', '127.0.0.1', '--port', '19870', '--no-access-log'])
    start_translation()
elif action=='translation':
    stop({'translation'});start_translation()
elif action == 'tunnel':
    stop({'tunnel'})
    spawn('tunnel', [str(WORK / 'cloudflared.exe'), 'tunnel', '--url',
        'http://127.0.0.1:19870', '--no-autoupdate', '--protocol', 'http2',
        '--metrics', '127.0.0.1:19872'])
elif action == 'stop':
    stop({'gateway', 'engine','translation', 'tunnel'})
    print('Local Voice and its tunnel stopped.')
else:
    for process, kind in owned_processes():
        print(kind, process.pid)
    try:
        print(httpx.get('http://127.0.0.1:19870/health', timeout=3).json())
    except httpx.HTTPError:
        print('Gateway is not responding.')
