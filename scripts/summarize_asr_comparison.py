"""Compare completed public ASR reports without trusting aggregate counters."""
import argparse
import json
from pathlib import Path
import statistics
from check_public_speech import normalized, distance


def summarize(first, second):
    for report in (first, second):
        if report.get('complete') is not True:
            raise ValueError('Incomplete benchmark is not a completed comparison')
        rows=report['results']
        if len(rows)!=36 or {r['index'] for r in rows}!=set(range(36)):
            raise ValueError('Expected the same complete 36-case corpus')
    for field in ('dataset','split','device','compute_type','threads','beam_size','vad_min_silence_ms',
                  'condition_on_previous_text','prompt','reference_in_prompt','llm_formatting'):
        if first[field]!=second[field]:
            raise ValueError('Different comparison setting: '+field)
    for report in (first, second):
        for field in ('reference_in_prompt', 'llm_formatting', 'private_data_used'):
            if report.get(field) is not False:
                raise ValueError('Not an isolated public ASR comparison: '+field)
    before={r['index']:r for r in first['results']}
    after={r['index']:r for r in second['results']}
    cases=[]
    for index in sorted(before):
        left,right=before[index],after[index]
        for field in ('reference','sha256','duration_ms'):
            if left[field]!=right[field]:raise ValueError('Different audio or reference')
        reference=normalized(left['reference'])
        a=distance(reference,normalized(left['hypothesis']))
        b=distance(reference,normalized(right['hypothesis']))
        cases.append({'index':index,'reference':left['reference'],'reference_chars':len(reference),
                      'before':left['hypothesis'],'after':right['hypothesis'],
                      'before_errors':a,'after_errors':b,'error_delta':b-a})
    chars=sum(r['reference_chars'] for r in cases)
    totals=[]
    for label,report in (('before',first),('after',second)):
        errors=sum(r[label+'_errors'] for r in cases)
        totals.append({'model':report['model'],'revision':report['revision'],'errors':errors,
            'reference_chars':chars,'cer':errors/chars,'exact_cases':sum(r[label+'_errors']==0 for r in cases),
            'empty_cases':sum(not r[label].strip() for r in cases),
            'cpu_median_seconds':statistics.median(r['seconds'] for r in report['results']),
            'cpu_total_seconds':sum(r['seconds'] for r in report['results'])})
    return {'same_corpus_and_settings':True,'cases':len(cases),'totals':totals,
            'improved_cases':sum(r['error_delta']<0 for r in cases),
            'regressed_cases':sum(r['error_delta']>0 for r in cases),
            'equal_error_cases':sum(r['error_delta']==0 for r in cases),
            'changed_cases':[r for r in cases if r['before']!=r['after']],
            'phone_or_home_gpu_latency_test':False,'independent_blind_test':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',type=Path,required=True)
    parser.add_argument('--after',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=summarize(json.loads(args.before.read_text(encoding='utf-8')),json.loads(args.after.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='changed_cases'},ensure_ascii=False))
