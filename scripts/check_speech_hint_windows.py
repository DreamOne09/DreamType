"""Exercise the installed faster-whisper decoding loop without weights or GPU.

Real window/prompt handling; synthetic decoder output. This proves hint transport,
not audio recognition quality. Run with the local speech runtime dependencies.
"""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from faster_whisper.transcribe import WhisperModel

ROOT=Path(__file__).resolve().parents[1]
HINT='汐止、陳昀霏'
class Tokenizer:
    sot_prev=900
    sot_sequence=[901]
    no_timestamps=902
    timestamp_begin=1000
    def encode(self,text):return [ord(c) for c in text]
    def decode(self,tokens):return '測試語音'

class Probe(WhisperModel):
    def __init__(self):
        self.max_length=448
        self.frames_per_second=100
        self.feature_extractor=SimpleNamespace(time_per_frame=.01,nb_max_frames=3000)
        self.logger=logging.getLogger('window-probe')
        self.prompts=[]
    def encode(self,segment):return None
    def generate_with_fallback(self,encoded,prompt,tokenizer,options):
        self.prompts.append(prompt)
        return SimpleNamespace(sequences_ids=[[12]],no_speech_prob=0),0,0,1
    def _split_segments_by_timestamps(self,**kw):
        return [dict(tokens=[12],start=kw['time_offset'],end=kw['time_offset']+kw['segment_duration'])],kw['seek']+kw['segment_size'],False
    def transcribe(self,audio,**kwargs):
        options=SimpleNamespace(clip_timestamps=[0],initial_prompt=kwargs.get('initial_prompt'),
            condition_on_previous_text=kwargs['condition_on_previous_text'],prompt_reset_on_temperature=.5,
            multilingual=False,without_timestamps=False,prefix=None,hotwords=kwargs.get('hotwords'),
            no_speech_threshold=None,word_timestamps=False)
        return self.generate_segments(np.zeros((80,9001),dtype=np.float32),Tokenizer(),options,False),SimpleNamespace(language='zh')

def contains(prompt):
    tokens=Tokenizer().encode(' '+HINT)
    return any(prompt[i:i+len(tokens)]==tokens for i in range(len(prompt)))

# Reproduce the old configuration through the library's actual three-window loop.
old=Probe();list(old.transcribe(None,condition_on_previous_text=False,initial_prompt=HINT)[0])
assert [contains(p) for p in old.prompts]==[True,False,False]
# Execute the production recognize function without importing server startup/models.
tree=ast.parse((ROOT/'outputs/local_voice/server.py').read_text(encoding='utf-8'))
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='recognize')
current=Probe();scope={'model':current,'converter':SimpleNamespace(convert=lambda value:value)}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'server.recognize','exec'),scope)
text,language=scope['recognize'](None,'zh',HINT)
assert len(current.prompts)==3 and all(contains(p) for p in current.prompts)
assert current.prompts[0]==current.prompts[1]==current.prompts[2], 'Hints duplicated or previous transcript leaked'
assert text=='測試語音'*3 and language=='zh'
print('PASS: actual faster-whisper loop; old hints [yes,no,no], production hints [yes,yes,yes]; no duplication')
