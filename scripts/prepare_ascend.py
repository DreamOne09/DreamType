"""Extract a fixed spontaneous code-switching sample; never select by ASR result.

Requires pyarrow 19.0.1 and opencc-python-reimplemented. Download the test parquet
from CAiRE/ASCEND at DATASET_REVISION first; no dataset code is executed.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import wave

DATASET_REVISION = '737e9800ae31be9932ba8464c80366559bd28424'
PARQUET_SHA256 = 'a4c81d2b5ed6124f052089a695972808c16e0ce0c365ec9773c5d1a8fcf043a7'


def prepare(source, audio_dir, manifest):
    with source.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != PARQUET_SHA256:
            raise ValueError('Not the frozen ASCEND test parquet')
    import pyarrow.parquet as pq
    from opencc import OpenCC
    converter = OpenCC('s2tw')
    candidates = [(i, row) for i, row in enumerate(pq.read_table(source).to_pylist())
                  if row['language'] == 'mixed']
    if len(candidates) != 373:
        raise ValueError('Unexpected mixed-language population')
    # 96 evenly spaced positions, including both ends, in original test order.
    selected = [candidates[i * (len(candidates)-1) // 95] for i in range(96)]
    audio_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, (source_index, row) in enumerate(selected):
        data = row['audio']['bytes']
        with wave.open(io.BytesIO(data)) as audio:
            duration_ms = round(audio.getnframes() / audio.getframerate() * 1000)
        name = f'ascend-{source_index:05d}.wav'
        (audio_dir / name).write_bytes(data)
        rows.append({'index': index, 'source_index': source_index, 'source_id': row['id'],
                     'file': name, 'sha256': hashlib.sha256(data).hexdigest(),
                     'duration_ms': duration_ms, 'reference': converter.convert(row['transcription']),
                     'original_reference': row['transcription'],
                     'speaker_id': row['original_speaker_id'], 'session_id': row['session_id'],
                     'topic': row['topic']})
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'cases': len(rows), 'total_seconds': sum(r['duration_ms'] for r in rows)/1000,
                      'speakers': sorted({r['speaker_id'] for r in rows})}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parquet', type=Path, required=True)
    parser.add_argument('--audio-dir', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.parquet, args.audio_dir, args.manifest)
