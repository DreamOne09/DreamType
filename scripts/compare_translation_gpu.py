import argparse,asyncio,contextlib,hashlib,io,json,os,runpy,secrets,sqlite3,subprocess,sys,time
from pathlib import Path
import httpx,psutil
parser=argparse.ArgumentParser(description='Opt-in GPU offload comparison with resident Turbo and restoration watchdog.')
parser.add_argument('--runtime-root',type=Path,required=True)
parser.add_argument('--watchdog')
options=parser.parse_args()
if os.name!='nt':raise SystemExit('This service controller requires Windows')
ROOT=options.runtime_root.resolve();WORK=ROOT/'work';CONTROL=ROOT/'outputs/local_voice/control.py'
LEASE=WORK/'translation-gpu-layers-lease.json';REPORT=WORK/'translation-gpu-layers.json'
def task(command):
 subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],check=True,timeout=30,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
def restore():
 subprocess.run([sys.executable,str(CONTROL),'start'],check=True,timeout=60)
 task("Enable-ScheduledTask -TaskName 'DreamType Maintenance' -ErrorAction Stop | Out-Null")
 for _ in range(60):
  try:
   if httpx.get('http://127.0.0.1:19870/health',timeout=3).json().get('status')=='ready':return
  except (httpx.HTTPError,ValueError):pass
  time.sleep(1)
 raise RuntimeError('Restored processes still warming; inspect without restarting')
if options.watchdog:
 token=options.watchdog
 for _ in range(300):
  if not LEASE.exists():sys.exit(0)
  lease=json.loads(LEASE.read_text())
  if lease['token']!=token:sys.exit(0)
  try:parent=psutil.Process(lease['pid']);alive=parent.create_time()==lease['created']
  except psutil.NoSuchProcess:alive=False
  if not alive:break
  time.sleep(2)
 else:
  if alive:parent.kill();parent.wait(timeout=10)
 restore();LEASE.unlink(missing_ok=True);sys.exit(0)
if LEASE.exists():raise SystemExit('Existing lease; inspect before starting')
with sqlite3.connect((WORK/'beta/accounts.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
 if db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]:raise SystemExit('Active jobs; defer')
assert httpx.get('http://127.0.0.1:19870/health',timeout=5).json()['status']=='ready'
argv=sys.argv;sys.argv=[str(CONTROL),'status']
with contextlib.redirect_stdout(io.StringIO()):control=runpy.run_path(str(CONTROL))
sys.argv=argv
owned=list(control['owned_processes']());translation=[p for p,k in owned if k=='translation']
assert len(translation)==1
base=translation[0].cmdline();assert base[base.index('-ngl')+1]=='10'
tunnel=[p.pid for p,k in owned if k=='tunnel']
key=(WORK/'local-voice.key').read_text().strip()
sys.path.insert(0,str(ROOT/'outputs/local_voice'));from translation import translate_text
text='明天下午四點半到板橋車站集合，不要去台北車站。請先確認訂單，再通知同事。如果下雨，會議改到室內，但時間不變。這次只需要準備文件和筆電，不要另外購買設備。完成檢查後，請把結果寄給負責人，並保留原本的紀錄。'
state={'synthetic_text':text,'configurations':[],'restored':False,'asr_unloaded_during_comparison':False,'gpu_samples_mib':[]}
token=secrets.token_hex(12);LEASE.write_text(json.dumps({'token':token,'pid':os.getpid(),'created':psutil.Process().create_time()}))
with (WORK/'translation-gpu-layers-watchdog.log').open('w') as log:
 subprocess.Popen([sys.executable,__file__,'--runtime-root',str(ROOT),'--watchdog',token],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
try:
 task("$t=Get-ScheduledTask -TaskName 'DreamType Maintenance' -ErrorAction Stop; if($t.State -ne 'Ready'){throw 'Maintenance is not idle'}; Disable-ScheduledTask -TaskName 'DreamType Maintenance' -ErrorAction Stop | Out-Null")
 control['stop']({'gateway'})
 handles=[]
 for directory in (WORK/'venv/Lib/site-packages/nvidia').glob('*/bin'):
  os.environ['PATH']=str(directory)+os.pathsep+os.environ.get('PATH','');handles.append(os.add_dll_directory(str(directory)))
 from faster_whisper import WhisperModel
 import gc,threading
 resident=WhisperModel(str(WORK/'models/whisper-turbo'),device='cuda',compute_type='int8_float16',cpu_threads=4,num_workers=1,local_files_only=True)
 manifest=json.loads((WORK/'public-speech/manifest.json').read_text(encoding='utf-8'))
 segments,_=resident.transcribe(str(WORK/'public-speech'/manifest[0]['file']),language='zh',beam_size=1,vad_filter=True)
 list(segments);del segments
 stop_sampling=threading.Event()
 def sample():
  while not stop_sampling.is_set():
   try:
    used=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True,creationflags=subprocess.CREATE_NO_WINDOW).strip().splitlines()[0]);state['gpu_samples_mib'].append(used)
   except Exception:pass
   stop_sampling.wait(.5)
 sampler=threading.Thread(target=sample,daemon=True);sampler.start()
 for threads in (10,16,10):
  control['stop']({'translation'})
  if any(k=='translation' for p,k in control['owned_processes']()):raise RuntimeError('Previous model still running')
  args=list(base);args[args.index('-ngl')+1]=str(threads);control['spawn']('translation',args)
  for _ in range(45):
   try:
    if httpx.get('http://127.0.0.1:19873/health',timeout=2).status_code==200:break
   except httpx.HTTPError:pass
   time.sleep(1)
  else:raise RuntimeError('Translation model warm-up pending')
  sample_start=len(state['gpu_samples_mib'])
  async def probe():
   await translate_text('明天下午四點半到板橋。','en',key,'zh-TW')
   rows=[]
   for repeat in range(2):
    for target in ('en','th','ms'):
     start=time.perf_counter();output=await translate_text(text,target,key,'zh-TW');elapsed=time.perf_counter()-start
     row={'repeat':repeat,'target':target,'seconds':round(elapsed,3),'sha256':hashlib.sha256(output.encode()).hexdigest(),'text':output}
     rows.append(row);print(json.dumps({'gpu_layers':threads,'repeat':repeat,'target':target,'seconds':row['seconds']}),flush=True)
   return rows
  state['configurations'].append({'gpu_layers':threads,'results':asyncio.run(probe()),'sample_start':sample_start,'sample_end':len(state['gpu_samples_mib'])});REPORT.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
finally:
 try:
  if 'stop_sampling' in globals():stop_sampling.set();sampler.join(timeout=5)
  if 'resident' in globals():del resident;gc.collect()
  restore();state['restored']=True
  state['tunnel_preserved']=tunnel==[p.pid for p,k in control['owned_processes']() if k=='tunnel']
  LEASE.unlink(missing_ok=True)
 finally:REPORT.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'restored':state['restored']}),flush=True)
