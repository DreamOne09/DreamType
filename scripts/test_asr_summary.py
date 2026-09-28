import copy
import json
from pathlib import Path
import unittest
from summarize_asr_comparison import mixed_tokens, summarize


class NaturalCorpusSummaryTests(unittest.TestCase):
    def report(self):
        rows=json.loads((Path(__file__).resolve().parents[1]/'tests/quality/ascend96/manifest.json').read_text(encoding='utf-8'))
        return dict(corpus='ascend96',complete=True,dataset='CAiRE/ASCEND',split='test',
                    dataset_revision='737e9800ae31be9932ba8464c80366559bd28424',device='CUDA',
                    compute_type='int8_float16',threads=4,beam_size=1,vad_min_silence_ms=350,
                    condition_on_previous_text=False,prompt='same',reference_in_prompt=False,
                    llm_formatting=False,private_data_used=False,model='fixture',revision='fixture',
                    results=[dict(row,hypothesis=row['reference'],seconds=.1,errors=999) for row in rows])

    def test_mixed_units_do_not_weight_english_by_word_length(self):
        self.assertEqual(mixed_tokens('臺灣的 PYTHON，版本 １２。'),['台','灣','的','python','版','本','12'])

    def test_recomputes_errors_and_complete_corpus(self):
        report=self.report()
        result=summarize(report,copy.deepcopy(report))
        self.assertEqual(result['totals'][0]['errors'],0)
        self.assertEqual(result['totals'][0]['project_mer'],0)
        self.assertEqual(result['cases'],96)

    def test_matching_tampered_references_still_rejected(self):
        report=self.report(); report['results'][0]['reference']='changed'
        with self.assertRaisesRegex(ValueError,'frozen'):
            summarize(report,copy.deepcopy(report))

    def test_missing_case_rejected(self):
        report=self.report(); report['results'].pop()
        with self.assertRaisesRegex(ValueError,'complete frozen'):
            summarize(report,copy.deepcopy(report))


if __name__=='__main__':unittest.main()
