import unittest
from dictation_guard import validate_edit

class DictationGuardTests(unittest.TestCase):
    def test_layout_and_punctuation_are_allowed(self):
        validate_edit('第一，明天到板橋拿文件。第二，下午四點半去汐止。', '• 明天到板橋拿文件。\n• 下午四點半去汐止。')
        validate_edit('請幫我生成一個計劃','請幫我生成一個計劃。')
        validate_edit('Please write a plan', 'Please write a plan.')

    def test_answers_and_new_content_are_rejected(self):
        for source, output in [('請幫我生成一個計劃','計劃：一、設定目標。二、安排時間。三、追蹤進度。'),
                               ('請幫我寫信','您好，請問您是否收到附件？'),
                               ('Please write a plan','Step 1: Define your objectives. Step 2: Build a schedule.'),
                               ('台灣的首都是哪裡','台北'), ('','好的')]:
            with self.subTest(source=source), self.assertRaises(ValueError):validate_edit(source,output)

    def test_missing_meaningful_clause_is_rejected(self):
        with self.assertRaises(ValueError):validate_edit('明天去板橋拿文件，如果下雨改星期五，千萬不要取消預約。','明天去板橋拿文件。')
