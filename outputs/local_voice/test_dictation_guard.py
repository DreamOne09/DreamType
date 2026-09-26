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

    def test_numeric_value_sign_decimal_and_scale_cannot_change(self):
        for before,after in [('-1.5','15'),('5%','5'),('12','13'),('負百分之5','百分之5'),('5萬','5'),('1.50','1.5')]:
            with self.subTest(before=before), self.assertRaises(ValueError):
                validate_edit('這次記錄的數值是 '+before+'，請先給我確認。','這次記錄的數值是 '+after+'，請先給我確認。')

    def test_equivalent_numeric_typography_is_allowed(self):
        for before,after in [('１，５００','1,500'),('1500','1,500'),('−1.5','-1.5'),('負100','-100'),('百分之5','5%')]:
            with self.subTest(before=before):
                validate_edit('這次記錄的數值是 '+before+'，請先給我確認。','這次記錄的數值是 '+after+'，請先給我確認。')

    def test_numbered_list_layout_does_not_invent_quantities(self):
        validate_edit('第一，明天拿文件。第二，下午開會。','1. 明天拿文件。\n2. 下午開會。')
        with self.assertRaises(ValueError):validate_edit('第一，有12人。第二，有15人。','1. 有15人。\n2. 有12人。')

    def test_new_numbers_and_precision_changes_are_rejected(self):
        with self.assertRaises(ValueError):validate_edit('請幫我寫明天的計劃。','請幫我寫明天的3個計劃。')
        with self.assertRaises(ValueError):validate_edit('明天測試值是1.5','明天測試值是15')

    def test_spoken_chinese_quantities_can_change_spelling_not_value(self):
        validate_edit('總共1500元，分成3次付款，每次500元。','總共1,500元，分成三次付款，每次500元。')
        validate_edit('一千五百元','1500元')
        validate_edit('比例是百分之五','比例是5%')
        with self.assertRaises(ValueError):validate_edit('總共有十二人出席，請先安排座位。','總共有13人出席，請先安排座位。')
        with self.assertRaises(ValueError):validate_edit('金額是一千五元','金額是1500元')

    def test_ordinary_chinese_words_are_not_numeric_quantities(self):
        validate_edit('千萬不要取消三重的預約','千萬不要取消三重的預約。')
