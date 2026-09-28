"""Opt-in real inference burst probe. Isolated accounts; no transcripts in report."""
import argparse
import asyncio
from contextlib import closing
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
import time

import httpx
from fastapi import FastAPI
from check_mixed_capacity import clips, LocalProvider, install_beta, isolated_audio_duration


async def run(args):
    root = args.runtime_root.resolve()
    with closing(sqlite3.connect((root/'work/beta/accounts.sqlite3').as_uri()+'?mode=ro', uri=True)) as db:
        if db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]:
            raise RuntimeError('Live queue is busy; defer probe')
    audio = clips(args.manifest)[2]
    key = (root/'work/local-voice.key').read_text().strip()
    with tempfile.TemporaryDirectory(prefix='dreamtype-burst-') as temporary:
        app = FastAPI()
        beta = install_beta(app, Path(temporary), LocalProvider('http://127.0.0.1:19870', key), isolated_audio_duration)
        await beta.start()
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://probe') as client:
                accounts = []
                for i in range(12):
                    credentials = {'username':'burst-'+secrets.token_hex(6),'password':secrets.token_urlsafe(24)}
                    created = await client.post('/v2/admin/users', headers={'Authorization':'Bearer '+beta.admin}, json={**credentials,'minutes':3})
                    created.raise_for_status()
                    login = await client.post('/v2/login', json=credentials)
                    login.raise_for_status()
                    accounts.append({'Authorization':'Bearer '+login.json()['token']})

                async def submit(i, recovery=False):
                    if not recovery:
                        await asyncio.sleep(i*args.interval)
                    started = time.perf_counter()
                    jid = ('capacity-recovery-' if recovery else 'capacity-burst-job-')+str(i)
                    headers = {**accounts[i], 'Idempotency-Key':jid, 'X-DreamType-Receipt':'1',
                        'X-DreamType-Mode':'translate','X-DreamType-Source':'zh-TW','X-DreamType-Target':'en'}
                    response = await client.post('/v2/dictations', headers=headers,
                        files={'file':('public.wav', audio, 'audio/wav')})
                    status = response.status_code
                    accepted_seconds = time.perf_counter()-started
                    body = response.json()
                    if status==429 and body.get('error_code') not in ('upload_busy','queue_full'):
                        raise RuntimeError('Unexpected rejection reason')
                    if status!=429:
                        response.raise_for_status()
                        while body['state'] in ('queued','running'):
                            if time.perf_counter()-started>300:
                                raise RuntimeError('Burst job exceeded observation deadline')
                            await asyncio.sleep(.2)
                            response = await client.get('/v2/dictations/'+jid, headers=accounts[i])
                            response.raise_for_status();body=response.json()
                        if body['state']!='done' or not body.get('text','').strip():
                            raise RuntimeError('Accepted job failed')
                        denied = await client.get('/v2/dictations/'+jid, headers=accounts[(i+1)%12])
                        if denied.status_code!=404:raise RuntimeError('Cross-account access')
                        for _ in range(2):
                            receipt = await client.post('/v2/dictations/'+jid+'/receipt',headers=accounts[i],json={})
                            receipt.raise_for_status()
                    me = await client.get('/v2/me',headers=accounts[i]);me.raise_for_status()
                    expected = 0 if status==429 else 60
                    if me.json()['used_seconds']!=expected or me.json()['reserved_seconds']:
                        raise RuntimeError('Incorrect quota after accepted/rejected job')
                    result={'account_index':i,'status':status,'accepted':expected==60,
                        'admission_seconds':round(accepted_seconds,3),
                        'total_seconds':round(time.perf_counter()-started,3),'used_seconds':expected,
                        'reserved_seconds':0,'recovery':recovery,
                        'rejection_code':body.get('error_code') if status==429 else None}
                    print(json.dumps(result),flush=True)
                    return result

                rows = await asyncio.gather(*(submit(i) for i in range(12)),return_exceptions=True)
                if any(isinstance(r,BaseException) for r in rows):
                    print(json.dumps({'failures':[{'type':type(r).__name__,
                        'http_status':r.response.status_code if isinstance(r,httpx.HTTPStatusError) else None}
                        for r in rows if isinstance(r,BaseException)]}),flush=True)
                    raise RuntimeError('Burst failed; all submissions settled before cleanup')
                rejected = [r for r in rows if not r['accepted']]
                if not rejected or not any(r['accepted'] for r in rows):
                    raise RuntimeError('Probe did not exercise both acceptance and overload')
                recovery = await submit(rejected[0]['account_index'],True)
                if not recovery['accepted']:raise RuntimeError('Service did not recover after burst')
        finally:
            await beta.stop()
    return {'accounts':12,'arrival_interval_seconds':args.interval,'audio_seconds':60,
        'mode':'translate','target':'en','database':'isolated temporary SQLite, removed after test',
        'transport':'in-process account ASGI to localhost real inference',
        'quality_evaluated':False,'native_device_test':False,'capacity_guarantee':False,
        'live_queue_locked':False,'results':rows,'recovery':recovery}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--interval',type=float,choices=(0,.3),default=0)
    args=parser.parse_args()
    report=asyncio.run(run(args))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
