"""Opt-in isolated account queue probe using the running local inference service.

Public audio is concatenated for load testing, not transcription quality scoring.
No live accounts are created; temporary SQLite, keys and results are deleted.
"""
import argparse
import asyncio
from contextlib import closing
import hashlib
import io
import json
import math
from pathlib import Path
import secrets
import sqlite3
import sys
import tempfile
import time
import wave

import httpx
import numpy as np
from fastapi import FastAPI
from faster_whisper.audio import decode_audio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'outputs/local_voice'))
from beta_api import LocalProvider, audio_duration, install_beta


def clips(manifest):
    rows = json.loads(manifest.read_text(encoding='utf-8'))
    parts = []
    for row in rows:
        data = (manifest.parent / row['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Public audio checksum mismatch')
        parts.append(decode_audio(io.BytesIO(data), sampling_rate=16000))
    if not parts or not all(len(p) for p in parts):
        raise ValueError('Manifest needs nonempty audio')
    combined = np.concatenate(parts)
    output = []
    for seconds in (5, 30, 60):
        pcm = np.tile(combined, math.ceil(seconds * 16000 / len(combined)))[:seconds * 16000]
        stream = io.BytesIO()
        with wave.open(stream, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes((np.clip(pcm, -1, 1) * 32767).astype('<i2').tobytes())
        output.append(stream.getvalue())
    return output


class TimedProvider:
    def __init__(self, provider):
        self.provider = provider
        self.events = []

    async def transcribe(self, audio, prefs):
        event = {'started': time.perf_counter(), 'digest': hashlib.sha256(audio).hexdigest()}
        self.events.append(event)
        try:
            return await self.provider.transcribe(audio, prefs)
        finally:
            event['finished'] = time.perf_counter()


async def run(args):
    db_path = args.runtime_root / 'work/beta/accounts.sqlite3'
    with closing(sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]:
            raise RuntimeError('Live queue is busy; defer probe')
    audio = clips(args.manifest)
    key = (args.runtime_root / 'work/local-voice.key').read_text().strip()
    provider = TimedProvider(LocalProvider('http://127.0.0.1:19870', key))
    results = []
    with tempfile.TemporaryDirectory(prefix='dreamtype-capacity-') as directory:
        app = FastAPI()
        beta = install_beta(app, Path(directory), provider, audio_duration)
        await beta.start()
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://probe') as client:
                accounts = []
                for i in range(3):
                    credentials = {'username': 'load-' + secrets.token_hex(6), 'password': secrets.token_urlsafe(24)}
                    response = await client.post('/v2/admin/users', headers={'Authorization': 'Bearer ' + beta.admin},
                                                 json={**credentials, 'minutes': 10})
                    response.raise_for_status()
                    response = await client.post('/v2/login', json=credentials)
                    response.raise_for_status()
                    accounts.append({'Authorization': 'Bearer ' + response.json()['token']})

                async def submit(i, round_number, accepted):
                    mode, target = [('organize', 'zh-TW'), ('translate', 'ja'), ('translate', 'en')][i]
                    jid = f'mixed-capacity-{round_number}-{i}'
                    started = time.perf_counter()
                    try:
                        response = await client.post('/v2/dictations', headers={**accounts[i],
                            'Idempotency-Key': jid, 'X-DreamType-Receipt': '1', 'X-DreamType-Mode': mode,
                            'X-DreamType-Target': target, 'X-DreamType-Source': 'zh-TW'},
                            files={'file': ('load.wav', audio[i], 'audio/wav')})
                        response.raise_for_status()
                    finally:
                        accepted.set()
                    body = response.json()
                    while body['state'] in ('queued', 'running'):
                        if time.perf_counter() - started > 720:
                            raise RuntimeError('Queue probe timed out')
                        await asyncio.sleep(.1)
                        response = await client.get('/v2/dictations/' + jid, headers=accounts[i])
                        response.raise_for_status()
                        body = response.json()
                    elapsed = time.perf_counter() - started
                    event = next(e for e in provider.events if e['digest'] == hashlib.sha256(audio[i]).hexdigest())
                    if body['state'] != 'done' or not body.get('text', '').strip():
                        raise RuntimeError('Real inference failed; no passing report written')
                    for other in accounts:
                        if other is not accounts[i]:
                            denied = await client.get('/v2/dictations/' + jid, headers=other)
                            if denied.status_code != 404:
                                raise RuntimeError('Cross-account result access')
                    for _ in range(2):
                        receipt = await client.post('/v2/dictations/' + jid + '/receipt', headers=accounts[i], json={})
                        receipt.raise_for_status()
                    me = await client.get('/v2/me', headers=accounts[i])
                    me.raise_for_status()
                    expected = (round_number + 1) * [5, 30, 60][i]
                    if me.json()['used_seconds'] != expected or me.json()['reserved_seconds']:
                        raise RuntimeError('Receipt quota mismatch')
                    return {'round': round_number + 1, 'audio_seconds': [5, 30, 60][i], 'mode': mode,
                        'target': target, 'total_seconds': round(elapsed, 3),
                        'wait_before_provider_seconds': round(event['started'] - started, 3),
                        'provider_seconds': round(event['finished'] - event['started'], 3),
                        'provider_order': provider.events.index(event) + 1,
                        'warning_present': bool(body.get('warning')), 'output_chars': len(body['text']),
                        'cross_account_denied': True, 'used_seconds': me.json()['used_seconds'],
                        'duplicate_receipt_no_extra_charge': True}

                for round_number in range(2):
                    provider.events.clear()
                    # Reverse round two so short dictation also waits behind
                    # long translation; short-first alone hides head-of-line delay.
                    order = range(3) if round_number == 0 else reversed(range(3))
                    tasks = []
                    for i in order:
                        accepted = asyncio.Event()
                        tasks.append(asyncio.create_task(submit(i, round_number, accepted)))
                        # Await upload acceptance, not completion: preserve the
                        # intended queue order despite different decode times.
                        await accepted.wait()
                    batch = await asyncio.gather(*tasks, return_exceptions=True)
                    if any(isinstance(row, BaseException) for row in batch):
                        raise RuntimeError('Mixed probe failed; all submissions settled before cleanup')
                    results.extend(batch)
        finally:
            await beta.stop()
    return {'simultaneous_accounts': 3, 'rounds': 2, 'database': 'isolated temporary SQLite, removed after test',
        'transport': 'in-process account ASGI to localhost HTTP inference',
        'audio': 'hash-verified public manifest audio concatenated and cut to 5/30/60 seconds',
        'submission_order_seconds': [[5, 30, 60], [60, 30, 5]],
        'quality_evaluated': False, 'native_device_test': False, 'capacity_guarantee': False,
        'live_queue_locked': False, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
