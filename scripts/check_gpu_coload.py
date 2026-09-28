"""Offline GPU benchmark; run only after production GPU users are stopped."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'scripts'))
sys.path.insert(0,str(REPO/'outputs/local_voice'))
from check_public_speech import normalized,distance
from personalization import speech_hint

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runtime-root',type=Path,required=True,help='Actual running installation containing outputs/local_voice and work/models')
parser.add_argument('--model',choices=['turbo','breeze'],required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--corpus',choices=['regression36','extended96'],default='extended96')
parser.add_argument('--verify-only',action='store_true')
args=parser.parse_args()
ROOT=args.runtime_root.resolve()
models={
 'turbo':('whisper-turbo','mobiuslabsgmbh/faster-whisper-large-v3-turbo','0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf','e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da'),
 'breeze':('breeze-asr-25/int8_float16','shdennlin/breeze-asr-25-ct2','70660216b01a6f6b7b8c5690767a4763df61755f','27f279d2653a6484c680d55182fa7ce8450dddfead77c6288ba90493ae1020a6')}
folder,model_id,revision,digest=models[args.model]
model_path=ROOT/'work/models'/folder
with (model_path/'model.bin').open('rb') as stream:
 if hashlib.file_digest(stream,'sha256').hexdigest()!=digest:raise ValueError('Model hash differs from frozen benchmark revision')
names=['public-taiwan-speech-extended.json'] if args.corpus=='extended96' else ['public-taiwan-speech.json','public-taiwan-speech-holdout.json']
rows=[]
for name in names:rows.extend(json.loads((REPO/'tests/quality'/name).read_text(encoding='utf-8')))
expected=list(range(36,132)) if args.corpus=='extended96' else list(range(36))
if [r['index'] for r in rows]!=expected:raise ValueError('Corpus indices differ')
audio=REPO/'work/asr-comparison/audio'
for row in rows:
 if hashlib.sha256((audio/Path(row['file']).name).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Audio hash differs')
if args.verify_only:
 print(json.dumps({'model':args.model,'verified_audio':len(rows),'weights_verified':True,'gpu_loaded':False}));sys.exit(0)
handles=[]
for directory in (ROOT/'work/venv/Lib/site-packages/nvidia').glob('*/bin'):
 os.environ['PATH']=str(directory)+os.pathsep+os.environ.get('PATH','')
 if hasattr(os,'add_dll_directory'):handles.append(os.add_dll_directory(str(directory)))
os.environ['HF_HUB_OFFLINE']='1'
from faster_whisper import WhisperModel
from opencc import OpenCC
import subprocess,threading,psutil
resource_samples=[]
stop_sampling=threading.Event()
def sample_resources():
 while not stop_sampling.is_set():
  try:
   used=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True,creationflags=subprocess.CREATE_NO_WINDOW).strip().splitlines()[0])
   resource_samples.append({'gpu_used_mib':used,'ram_available_bytes':psutil.virtual_memory().available})
  except Exception:pass
  stop_sampling.wait(.5)
sampler=threading.Thread(target=sample_resources,daemon=True);sampler.start()
started=time.perf_counter()
model=WhisperModel(str(model_path),device='cuda',compute_type='int8_float16',cpu_threads=4,num_workers=1,local_files_only=True)
loaded=time.perf_counter()-started
prompt=speech_hint('以下為台灣繁體中文，可能包含英文專有名詞。',token_count=lambda value:len(model.hf_tokenizer.encode(value,add_special_tokens=False).ids))
converter=OpenCC('s2tw')
def transcribe(row):
 segments,_=model.transcribe(str(audio/Path(row['file']).name),language='zh',beam_size=1,vad_filter=True,vad_parameters={'min_silence_duration_ms':350},condition_on_previous_text=False,initial_prompt=prompt)
 return converter.convert(''.join(segment.text for segment in segments).strip())
started=time.perf_counter();transcribe(rows[0]);warmup=time.perf_counter()-started
report={'model':model_id,'revision':revision,'model_sha256':digest,'device':'CUDA','compute_type':'int8_float16','threads':4,'load_seconds':loaded,'warmup_seconds':warmup,'warmup_index':rows[0]['index'],
 'dataset':'OpenFormosa/common_voice_25_zh-TW','split':'test','license':'CC0-1.0','corpus':args.corpus,'beam_size':1,'vad_min_silence_ms':350,'condition_on_previous_text':False,'prompt':prompt,
 'reference_in_prompt':False,'llm_formatting':False,'private_data_used':False,'phone_latency_test':False,'complete':False,'results':[]}
args.output.parent.mkdir(parents=True,exist_ok=True)
for row in rows:
 started=time.perf_counter();hypothesis=transcribe(row);seconds=time.perf_counter()-started
 reference=normalized(row['reference'])
 report['results'].append({**row,'hypothesis':hypothesis,'reference_chars':len(reference),'errors':distance(reference,normalized(hypothesis)),'seconds':round(seconds,4)})
 args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'model':args.model,'index':row['index'],'seconds':round(seconds,4)}),flush=True)
import asyncio
sys.path.insert(0,str(ROOT/'outputs/local_voice'))
import server
async def probe_pipeline():
 results=[]
 # Public recognized text, with ASR model retained on GPU throughout.
 for row in report['results'][:6]:
  for mode,target in [('organize','en'),('translate','ja'),('translate','en')]:
   began=time.perf_counter()
   try:
    text=await server.format_text(row['hypothesis'],mode=mode,target_language=target,source_language='zh')
    results.append({'index':row['index'],'mode':mode,'target':target,'input':row['hypothesis'],'text':text,'seconds':time.perf_counter()-began,'error':None})
   except Exception as error:
    results.append({'index':row['index'],'mode':mode,'target':target,'input':row['hypothesis'],'seconds':time.perf_counter()-began,'error':type(error).__name__+': '+str(error)})
 return results
report['pipeline_probes']=asyncio.run(probe_pipeline())
report['pipeline_passed']=all(item['error'] is None and item.get('text','').strip() for item in report['pipeline_probes'])
stop_sampling.set();sampler.join(timeout=5)
report['resource_sample_count']=len(resource_samples)
report['observed_peak_gpu_mib']=max((r['gpu_used_mib'] for r in resource_samples),default=None)
report['observed_min_available_ram_bytes']=min((r['ram_available_bytes'] for r in resource_samples),default=None)
report['production_models_resident']=True
report['complete']=True
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Completed offline CUDA benchmark',flush=True)
if not report['pipeline_passed']:raise SystemExit('One or more co-resident pipeline probes failed')
