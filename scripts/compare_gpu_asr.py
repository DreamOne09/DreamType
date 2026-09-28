"""Offline GPU benchmark; run only after production GPU users are stopped."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'scripts'))
sys.path.insert(0,str(REPO/'outputs/local_voice'))
from check_public_speech import normalized,distance
from personalization import speech_hint

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model',choices=['turbo','breeze'],required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--corpus',choices=['regression36','extended96','ascend96'],default='extended96')
parser.add_argument('--verify-only',action='store_true')
parser.add_argument('--model-dir',type=Path,required=True,help='Directory containing the pinned model.bin and tokenizer files')
parser.add_argument('--audio-dir',type=Path,default=REPO/'work/asr-comparison/audio')
args=parser.parse_args()
models={
 'turbo':('whisper-turbo','mobiuslabsgmbh/faster-whisper-large-v3-turbo','0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf','e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da'),
 'breeze':('breeze-asr-25/int8_float16','shdennlin/breeze-asr-25-ct2','70660216b01a6f6b7b8c5690767a4763df61755f','27f279d2653a6484c680d55182fa7ce8450dddfead77c6288ba90493ae1020a6')}
folder,model_id,revision,digest=models[args.model]
model_path=args.model_dir
with (model_path/'model.bin').open('rb') as stream:
 if hashlib.file_digest(stream,'sha256').hexdigest()!=digest:raise ValueError('Model hash differs from frozen benchmark revision')
names={'extended96':['public-taiwan-speech-extended.json'],
       'regression36':['public-taiwan-speech.json','public-taiwan-speech-holdout.json'],
       'ascend96':['ascend96/manifest.json']}[args.corpus]
rows=[]
for name in names:rows.extend(json.loads((REPO/'tests/quality'/name).read_text(encoding='utf-8')))
expected=list(range(36,132)) if args.corpus=='extended96' else list(range(96 if args.corpus=='ascend96' else 36))
if [r['index'] for r in rows]!=expected:raise ValueError('Corpus indices differ')
audio=args.audio_dir
for row in rows:
 if hashlib.sha256((audio/Path(row['file']).name).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Audio hash differs')
if args.verify_only:
 print(json.dumps({'model':args.model,'verified_audio':len(rows),'weights_verified':True,'gpu_loaded':False}));sys.exit(0)
handles=[]
for directory in (Path(sys.prefix)/'Lib/site-packages/nvidia').glob('*/bin'):
 os.environ['PATH']=str(directory)+os.pathsep+os.environ.get('PATH','')
 if hasattr(os,'add_dll_directory'):handles.append(os.add_dll_directory(str(directory)))
os.environ['HF_HUB_OFFLINE']='1'
from faster_whisper import WhisperModel
from opencc import OpenCC
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
if args.corpus=='ascend96':
 report.update(dataset='CAiRE/ASCEND',dataset_revision='737e9800ae31be9932ba8464c80366559bd28424',
               license='CC-BY-SA-4.0',natural_speech=True,long_form_test=False,
               reference_conversion='OpenCC s2tw; original_reference retained',
               selection='96 evenly spaced positions of 373 mixed test rows, no ASR-based selection')
for row in rows:
 started=time.perf_counter();hypothesis=transcribe(row);seconds=time.perf_counter()-started
 reference=normalized(row['reference'])
 report['results'].append({**row,'hypothesis':hypothesis,'reference_chars':len(reference),'errors':distance(reference,normalized(hypothesis)),'seconds':round(seconds,4)})
 args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'model':args.model,'index':row['index'],'seconds':round(seconds,4)}),flush=True)
report['complete']=True
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Completed offline CUDA benchmark',flush=True)
