"""Isolated CPU ASR comparison on hash-pinned, public CC0 Taiwanese speech.

No service credentials, user audio or production endpoint are used. Reports
contain public reference/hypothesis text; raw audio and models stay in work/.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlparse

import httpx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'outputs/local_voice'))
from personalization import speech_hint
from check_public_speech import normalized, distance

MODELS = {
    'turbo': ('mobiuslabsgmbh/faster-whisper-large-v3-turbo',
              '0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf', ''),
    'breeze': ('shdennlin/breeze-asr-25-ct2',
               '70660216b01a6f6b7b8c5690767a4763df61755f', 'int8_float16'),
}
DATASET = 'OpenFormosa/common_voice_25_zh-TW'


def prepare_audio(destination, corpus='regression36'):
    rows = []
    names = ('public-taiwan-speech.json', 'public-taiwan-speech-holdout.json') if corpus=='regression36' else ('public-taiwan-speech-extended.json',)
    for name in names:
        rows.extend(json.loads((REPO / 'tests/quality' / name).read_text(encoding='utf-8')))
    expected = list(range(36)) if corpus=='regression36' else list(range(36,132))
    if [row['index'] for row in rows]!=expected:raise ValueError('Unexpected corpus indices')
    destination.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        response = client.get('https://datasets-server.huggingface.co/rows', params={
            'dataset': DATASET, 'config': 'default', 'split': 'test', 'offset': expected[0], 'length': len(rows)})
        response.raise_for_status()
        public_rows = {row['row_idx']: row['row'] for row in response.json()['rows']}
        for expected in rows:
            actual = public_rows[expected['index']]
            if actual['sentence'] != expected['reference']:
                raise ValueError('Public row changed; do not silently replace the benchmark')
            path = destination / Path(expected['file']).name
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == expected['sha256']:
                continue
            url = actual['audio'][0]['src']
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname != 'datasets-server.huggingface.co':
                raise ValueError('Unexpected public audio origin')
            response = client.get(url)
            response.raise_for_status()
            if hashlib.sha256(response.content).hexdigest() != expected['sha256']:
                raise ValueError('Public audio hash differs from existing benchmark')
            path.write_bytes(response.content)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=MODELS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--corpus', choices=('regression36','extended96'), default='regression36')
    args = parser.parse_args()
    work = REPO / 'work/asr-comparison'
    rows = prepare_audio(work / 'audio', args.corpus)
    if args.prepare_only:
        print(json.dumps({'audio_files_verified': len(rows), 'private_data_used': False}))
        return
    from huggingface_hub import snapshot_download
    from faster_whisper import WhisperModel
    from opencc import OpenCC
    model_id, revision, subdirectory = MODELS[args.model]
    model_root = work / args.model
    patterns = [subdirectory + '/*'] if subdirectory else ['*.json', '*.txt', 'model.bin']
    snapshot_download(model_id, revision=revision, local_dir=model_root, allow_patterns=patterns)
    threads = min(os.cpu_count() or 1, 4)
    started = time.perf_counter()
    model = WhisperModel(str(model_root / subdirectory), device='cpu', compute_type='int8',
                         cpu_threads=threads, num_workers=1, local_files_only=True)
    load_seconds = time.perf_counter() - started
    prompt = speech_hint('以下為台灣繁體中文，可能包含英文專有名詞。',
                         token_count=lambda value: len(model.hf_tokenizer.encode(value, add_special_tokens=False).ids))
    converter = OpenCC('s2tw')
    results = []
    # Persist each completed public case so a timed-out run remains inspectable.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {'model': model_id, 'revision': revision, 'converted_subdirectory': subdirectory,
        'device': 'CPU', 'compute_type': 'int8', 'threads': threads, 'load_seconds': round(load_seconds, 3),
        'dataset': DATASET, 'license': 'CC0-1.0', 'split': 'test', 'corpus': args.corpus,
        'selection': 'fixed sequential rows '+str(rows[0]['index'])+'-'+str(rows[-1]['index']),
        'beam_size': 1, 'vad_min_silence_ms': 350, 'condition_on_previous_text': False,
        'prompt': prompt, 'reference_in_prompt': False, 'llm_formatting': False,
        'phone_latency_test': False, 'private_data_used': False, 'complete': False, 'results': results}
    for row in rows:
        started = time.perf_counter()
        segments, _ = model.transcribe(str(work / 'audio' / Path(row['file']).name), language='zh',
            beam_size=1, vad_filter=True, vad_parameters={'min_silence_duration_ms': 350},
            condition_on_previous_text=False, initial_prompt=prompt)
        hypothesis = converter.convert(''.join(segment.text for segment in segments).strip())
        reference = normalized(row['reference'])
        results.append({**row, 'hypothesis': hypothesis, 'reference_chars': len(reference),
            'errors': distance(reference, normalized(hypothesis)), 'seconds': round(time.perf_counter()-started, 3)})
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'model': args.model, 'sample': row['index'], 'errors': results[-1]['errors'],
                          'seconds': results[-1]['seconds']}), flush=True)
    report.update(complete=True, errors=sum(r['errors'] for r in results),
                  reference_chars=sum(r['reference_chars'] for r in results),
                  exact_cases=sum(r['errors']==0 for r in results), empty_cases=sum(not r['hypothesis'] for r in results))
    report['cer'] = report['errors'] / report['reference_chars']
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('complete', 'cer', 'errors', 'reference_chars', 'exact_cases', 'empty_cases')}))


if __name__ == '__main__':
    main()
