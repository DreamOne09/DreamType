"""Probe the live ASR with synthetic non-speech only; no microphone recording."""
import argparse
from array import array
import io
import json
import math
from pathlib import Path
import random
import sys
import time
import wave
import httpx


def sample(kind):
    rate, duration = 16000, 4
    rng = random.Random(20260922)
    pcm = array('h')
    for index in range(rate*duration):
        value = 0 if kind == 'silence' else rng.randint(-100,100) if kind == 'quiet_noise' else round(650*math.sin(2*math.pi*60*index/rate))
        pcm.append(value)
    if sys.byteorder != 'little':
        pcm.byteswap()
    output = io.BytesIO()
    with wave.open(output,'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(pcm.tobytes())
    return output.getvalue()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--speech-control',type=Path,required=True,help='Known speech clip to check ASR is not rejecting everything')
    args=parser.parse_args()
    key=(args.runtime_root/'work/local-voice.key').read_text().strip()
    results=[]
    with httpx.Client(timeout=60) as client:
        for kind in ('silence','quiet_noise','hum_60hz'):
            start=time.perf_counter()
            response=client.post('http://127.0.0.1:19870/v1/audio/transcriptions',
                headers={'Authorization':'Bearer '+key},files={'file':('synthetic.wav',sample(kind),'audio/wav')},
                data={'model':'local-raw','language':'zh','source_language':'zh-TW'})
            response.raise_for_status()
            text=response.json()['text']
            results.append({'kind':kind,'duration_seconds':4,'text':text,'empty':text=='',
                'processing_seconds':round(time.perf_counter()-start,3)})
        response=client.post('http://127.0.0.1:19870/v1/audio/transcriptions',
            headers={'Authorization':'Bearer '+key},files={'file':('control.m4a',args.speech_control.read_bytes(),'audio/mp4')},
            data={'model':'local-raw','language':'zh','source_language':'zh-TW'})
        response.raise_for_status()
        control_text=response.json()['text']
        control={'nonempty':bool(control_text.strip()),'characters':len(control_text),'content_saved':False}
    report={'speech_control':control,'synthetic_audio_only':False,'native_device_test':False,'real_background_noise_test':False,'results':results}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
    return 0 if control['nonempty'] and all(item['empty'] for item in results) else 1


if __name__=='__main__':
    raise SystemExit(main())
