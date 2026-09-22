"""Run synthetic text cases against the owner's local gateway; not an ASR test."""
import argparse
import json
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    cases = json.loads((repo / 'tests/quality/taiwan-chinese.json').read_text(encoding='utf-8-sig'))
    key = (args.runtime_root / 'work/local-voice.key').read_text(encoding='ascii').strip()
    rows = []
    with httpx.Client(timeout=90) as client:
        for case in cases:
            start = time.perf_counter()
            response = client.post('http://127.0.0.1:19870/v1/chat/completions',
                headers={'Authorization': 'Bearer ' + key},
                json={'messages': [{'role': 'user', 'content': case['input']}]})
            row = dict(case, status=response.status_code, seconds=round(time.perf_counter()-start, 2))
            if response.status_code == 200:
                row['output'] = response.json()['choices'][0]['message']['content']
            else:
                row['output'] = None
            rows.append(row)
            print(case['id'], response.status_code, flush=True)
    report = {'synthetic_text_only': True, 'speech_recognition_tested': False,
        'automatic_semantic_score': None, 'requires_review': True, 'results': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if all(row['status'] == 200 for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
