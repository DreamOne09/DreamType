"""Validate and summarize paired offline CUDA ASR reports."""
import argparse
import json
from pathlib import Path
from summarize_asr_comparison import summarize


def compare(reports, hardware):
    if not all(r.get('device') == 'CUDA' and r.get('complete') is True for r in reports):
        raise ValueError('Expected two completed CUDA reports')
    if reports[0]['warmup_index'] != reports[1]['warmup_index']:
        raise ValueError('Warm-up cases differ')
    summary = summarize(*reports)
    for total, report in zip(summary['totals'], reports):
        total['gpu_median_seconds'] = total.pop('cpu_median_seconds')
        total['gpu_total_seconds'] = total.pop('cpu_total_seconds')
        values = sorted(row['seconds'] for row in report['results'])
        total['gpu_p95_seconds'] = values[int((len(values)-1)*.95)]
        total['load_seconds'] = report['load_seconds']
        total['warmup_seconds'] = report['warmup_seconds']
    summary.pop('phone_or_home_gpu_latency_test')
    summary.update(home_gpu_asr_test=True, phone_latency_test=False, production_coload_test=False,
                   hardware=hardware, warmup_policy='first case once before timed corpus')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--hardware', required=True, help='Observed hardware, not inferred from latency')
    args = parser.parse_args()
    reports = [json.loads(path.read_text(encoding='utf-8')) for path in (args.before,args.after)]
    result = compare(reports,args.hardware)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='changed_cases'},ensure_ascii=False))
