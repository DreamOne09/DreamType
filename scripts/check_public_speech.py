"""Evaluate local ASR on an explicitly supplied, licensed public speech manifest."""
import argparse
import json
from pathlib import Path
import time
import unicodedata
import httpx


def normalized(text):
    text=unicodedata.normalize('NFKC',text).replace('臺','台').lower()
    return ''.join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith('P'))


def distance(a,b):
    previous=list(range(len(b)+1))
    for i,left in enumerate(a,1):
        current=[i]
        for j,right in enumerate(b,1):
            current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(left!=right)))
        previous=current
    return previous[-1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    rows=json.loads(args.manifest.read_text(encoding='utf-8'))
    key=(args.runtime_root/'work/local-voice.key').read_text().strip()
    results=[]
    with httpx.Client(timeout=90) as client:
        for row in rows:
            audio=(args.manifest.parent/row['file']).read_bytes()
            import hashlib
            if hashlib.sha256(audio).hexdigest()!=row['sha256']:raise ValueError('Audio checksum mismatch')
            start=time.perf_counter()
            response=client.post('http://127.0.0.1:19870/v1/audio/transcriptions',
                headers={'Authorization':'Bearer '+key},files={'file':(row['file'],audio,'audio/wav')},
                data={'model':'local-raw','language':'zh','source_language':'zh-TW','vocabulary':''})
            response.raise_for_status();body=response.json()
            reference=normalized(row['reference']);hypothesis=normalized(body['text'])
            results.append({**row,'hypothesis':body['text'],'errors':distance(reference,hypothesis),
                            'reference_chars':len(reference),'seconds':round(time.perf_counter()-start,3)})
            print('sample',row['index'],'errors',results[-1]['errors'],flush=True)
    denominator=sum(r['reference_chars'] for r in results)
    report={'dataset':'OpenFormosa/common_voice_25_zh-TW','license':'CC0-1.0','split':'test',
            'selection':'supplied manifest order, no selection by result; convenience sample, not representative',
            'model':'existing whisper-turbo local service','custom_vocabulary':'none; no reference supplied to model',
            'metric':'micro CER; NFKC, lowercase, ignore punctuation/whitespace, map 臺 to 台',
            'cer':sum(r['errors'] for r in results)/denominator,'reference_chars':denominator,
            'errors':sum(r['errors'] for r in results),'cases':results}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('cer','reference_chars','errors')}))

if __name__=='__main__':main()
