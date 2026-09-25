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

    def test_request_cue_cannot_be_removed_from_a_long_copied_sentence(self):
        with self.assertRaises(ValueError):
            validate_edit('請幫我寫計劃，明天上午十點先到板橋拿文件，下午四點再到汐止開會。',
                          '明天上午十點先到板橋拿文件，下午四點再到汐止開會。')

    def test_missing_meaningful_clause_is_rejected(self):
        with self.assertRaises(ValueError):validate_edit('明天去板橋拿文件，如果下雨改星期五，千萬不要取消預約。','明天去板橋拿文件。')

    def test_small_negation_and_condition_changes_are_rejected(self):
        cases=[('明天上午先到板橋拿文件，不要取消下午四點半的預約。','明天上午先到板橋拿文件，要取消下午四點半的預約。'),
               ('如果客戶同意，明天才安排出貨，否則先等我通知。','客戶同意，明天安排出貨，先等我通知。'),
               ('我只負責整理資料，確認之後才寄信給客戶。','我負責整理資料，確認之後寄信給客戶。'),
               ('明天下午四點半取消板橋的預約。','明天下午四點半不要取消板橋的預約。'),
               ('確認之前，先通知客戶。','確認之後，先通知客戶。'),
               ('文件不是明天寄出，請先確認地址。','文件不單是明天寄出，請先確認地址。')]
        for source,edited in cases:
            with self.subTest(source=source),self.assertRaises(ValueError):validate_edit(source,edited)

    def test_negation_cannot_move_to_another_clause(self):
        with self.assertRaises(ValueError):
            validate_edit('明天不要取消板橋的預約，下午照常寄出完整文件給客戶確認。',
                          '明天取消板橋的預約，下午不要照常寄出完整文件給客戶確認。')

    def test_punctuation_around_conditions_and_adjacent_spelling_still_work(self):
        validate_edit('如果明天下雨就改星期五但不要取消預約','如果明天下雨，就改星期五，但不要取消預約。')
        validate_edit('請不要取消板喬的預約','請不要取消板橋的預約。')

    def test_self_correction_touching_negation_conservatively_keeps_raw(self):
        with self.assertRaises(ValueError):validate_edit('不要取消，不對，是要取消明天板橋的預約。','要取消明天板橋的預約。')

    def test_adjacent_identical_logic_stutters_can_be_removed(self):
        validate_edit('不要不要取消明天的預約。','不要取消明天的預約。')
        validate_edit('不不不要取消明天的預約。','不要取消明天的預約。')
        validate_edit('如果如果下雨就改星期五。','如果下雨就改星期五。')
        with self.assertRaises(ValueError):
            validate_edit('不要取消明天板橋的預約，也不要寄出尚未確認的文件。',
                          '不要取消明天板橋的預約，也寄出尚未確認的文件。')
