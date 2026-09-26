"""Freeze public test rows 36-131 before model comparison, without result selection."""
import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import av
import httpx

ROOT = Path(__file__).resolve().parents[1]
DATASET = 'OpenFormosa/common_voice_25_zh-TW'
MANIFEST = ROOT / 'tests/quality/public-taiwan-speech-extended.json'


def main():
    if MANIFEST.exists():
        raise SystemExit('Manifest already frozen; use compare_public_asr.py --prepare-only to verify it')
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        response = client.get('https://datasets-server.huggingface.co/rows', params={
            'dataset': DATASET, 'config': 'default', 'split': 'test', 'offset': 36, 'length': 96})
        response.raise_for_status()
        rows = response.json()['rows']
        if [r['row_idx'] for r in rows] != list(range(36,132)):
            raise ValueError('Incomplete predetermined corpus')
        destination = ROOT / 'work/asr-comparison/audio'
        destination.mkdir(parents=True, exist_ok=True)

        def freeze(item):
            row = item['row']; index = item['row_idx']
            url = row['audio'][0]['src']; parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname != 'datasets-server.huggingface.co':
                raise ValueError('Unexpected audio origin')
            result = client.get(url); result.raise_for_status(); data = result.content
            with av.open(io.BytesIO(data)) as container:
                seconds = sum(frame.samples / frame.sample_rate for frame in container.decode(audio=0))
            filename = f'sample-{index:03d}.wav'
            (destination / filename).write_bytes(data)
            return {'index': index, 'file': filename, 'reference': row['sentence'],
                    'duration_ms': round(seconds * 1000), 'sha256': hashlib.sha256(data).hexdigest()}

        with ThreadPoolExecutor(max_workers=3) as pool:
            manifest = list(pool.map(freeze, rows))
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'frozen_cases': len(manifest), 'indices': [36,131], 'private_data_used': False}))


if __name__ == '__main__':
    main()
