"""Opt-in sequential stage timings using pinned public audio and live models."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time
import httpx
from check_mixed_capacity import clips


def run(args):
    root=args.runtime_root.resolve()
    with closing(sqlite3.connect((root/'work/beta/accounts.sqlite3').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]:
            raise RuntimeError('Live queue is busy; defer probe')
    audio=clips(args.manifest)
    key=(root/'work/local-voice.key').read_text().strip()
    cases=[(0,5,'organize','zh-TW'),(2,60,'organize','zh-TW')]+[(2,60,'translate',t) for t in ('en','ja','th','ms')]
    rows=[]
    with httpx.Client(timeout=120) as client:
        for index,seconds,mode,target in cases:
            started=time.perf_counter()
            response=client.post('http://127.0.0.1:19870/v1/audio/transcriptions',
                headers={'Authorization':'Bearer '+key},files={'file':('public.wav',audio[index],'audio/wav')},
                data={'model':'local-dictation','mode':mode,'source_language':'zh-TW','target_language':target})
            response.raise_for_status();body=response.json()
            if not body.get('text','').strip():
                raise RuntimeError('Empty result; no usable profile')
            timing=body['timings']
            row={'audio_seconds':seconds,'mode':mode,'target':target,
                'speech_seconds':timing['speech_seconds'],'text_seconds':timing['format_seconds'],
                'gateway_total_seconds':timing['total_seconds'],
                'client_seconds':round(time.perf_counter()-started,3),
                'raw_characters':len(body['raw_text']),'output_characters':len(body['text']),
                'formatting_fallback':bool(body.get('warning'))}
            rows.append(row);print(json.dumps(row),flush=True)
    return {'audio':'hash-verified public manifest clips, concatenated/cut to 5 or 60 seconds',
        'transport':'sequential localhost private gateway; no account queue or mobile network',
        'quality_evaluated':False,'live_queue_locked':False,'capacity_guarantee':False,'results':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-root','manifest','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();report=run(args)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
