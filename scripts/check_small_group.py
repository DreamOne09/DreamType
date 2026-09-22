"""Opt-in local three-account integration probe; not a production capacity benchmark."""
import argparse
import asyncio
import json
from pathlib import Path
import secrets
import sqlite3
import time
import uuid
from contextlib import closing
import httpx


async def run(args):
    root = args.runtime_root
    with closing(sqlite3.connect('file:' + (root/'work/beta/accounts.sqlite3').as_posix() + '?mode=ro', uri=True)) as db:
        if db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]:
            raise RuntimeError('Active jobs exist; probe deferred')
    audio = args.audio.read_bytes()
    if not 0 < len(audio) <= 2*1024*1024:
        raise ValueError('Audio must be between 1 byte and 2 MiB')
    admin = {'Authorization': 'Bearer ' + (root/'work/beta/admin.key').read_text().strip()}
    accounts = []
    async with httpx.AsyncClient(base_url='http://127.0.0.1:19870', timeout=30) as client:
        try:
            for _ in range(3):
                name, password = 'capacity-' + secrets.token_hex(6), secrets.token_urlsafe(24)
                response = await client.post('/v2/admin/users', headers=admin,
                    json={'username':name, 'password':password, 'minutes':2})
                response.raise_for_status()
                # Track credentials immediately so a later login failure does not orphan the account.
                account = {'username':name,'password':password,'id':str(uuid.uuid4())}
                accounts.append(account)
                response = await client.post('/v2/login',json={'username':name,'password':password})
                response.raise_for_status()
                account['headers'] = {'Authorization':'Bearer ' + response.json()['token']}
            async def upload(account):
                started = time.perf_counter()
                headers = dict(account['headers'], **{'Idempotency-Key':account['id'],
                    'X-DreamType-Receipt':'1','X-DreamType-Mode':'organize',
                    'X-DreamType-Target':'zh-TW','X-DreamType-Source':'zh-TW'})
                response = await client.post('/v2/dictations',headers=headers,files={'file':('voice.m4a',audio,'audio/mp4')})
                response.raise_for_status()
                body = response.json()
                queued = body.get('state') == 'queued'
                while body.get('state') in ('queued','running'):
                    if time.perf_counter()-started > 120:
                        raise RuntimeError('Probe exceeded 120 seconds')
                    await asyncio.sleep(0.25)
                    response = await client.get('/v2/dictations/'+account['id'],headers=account['headers'])
                    response.raise_for_status()
                    body = response.json()
                    queued |= body.get('state') == 'queued'
                if body.get('state') != 'done' or not str(body.get('text','')).strip() or body.get('warning'):
                    raise RuntimeError('Dictation did not complete cleanly')
                elapsed = round(time.perf_counter()-started,2)
                for other in accounts:
                    if other is not account:
                        denied = await client.get('/v2/dictations/'+account['id'],headers=other['headers'])
                        if denied.status_code != 404:
                            raise RuntimeError('Cross-account isolation failed')
                for _ in range(2):
                    receipt = await client.post('/v2/dictations/'+account['id']+'/receipt',headers=account['headers'],json={})
                    receipt.raise_for_status()
                    me = await client.get('/v2/me',headers=account['headers'])
                    me.raise_for_status()
                    used = me.json()['used_seconds']
                    if _ == 0: original_used = used
                    elif used != original_used: raise RuntimeError('Duplicate receipt charged twice')
                return {'completed_seconds':elapsed,'observed_queue':queued,'used_seconds':used,
                    'cross_account_denied':True,'duplicate_receipt_no_extra_charge':True}
            results = await asyncio.gather(*(upload(account) for account in accounts),return_exceptions=True)
            if any(isinstance(value,BaseException) for value in results):
                raise RuntimeError('Probe failed; no passing report written')
            return {'simultaneous_accounts':3,'transport':'localhost HTTP','audio_bytes':len(audio),
                'same_test_clip_for_all':True,'native_device_test':False,'capacity_guarantee':False,'results':results}
        finally:
            cleanup_failed = False
            for account in accounts:
                try:
                    login = await client.post('/v2/login',json={'username':account['username'],'password':account['password']})
                    login.raise_for_status()
                    deleted = await client.request('DELETE','/v2/me',headers={'Authorization':'Bearer '+login.json()['token']},json={'password':account['password']})
                    deleted.raise_for_status()
                except Exception:
                    cleanup_failed = True
            if cleanup_failed:
                raise RuntimeError('Synthetic account cleanup needs administrator review')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root',type=Path,required=True)
    parser.add_argument('--audio',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    report = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
