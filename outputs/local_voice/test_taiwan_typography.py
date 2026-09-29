import unittest
from taiwan_typography import normalize_taiwan_typography as clean


class TaiwanTypographyTests(unittest.TestCase):
    def test_readable_prose_and_list_boundaries_change_whitespace_only(self):
        import re
        from taiwan_typography import readable_layout as layout
        source='社團適合商務人士。\n大家可以交換資源。\n我們是在幫助別人。'
        self.assertEqual(layout(source),source.replace('\n',''))
        source='明天有兩位來賓。\n●　小林做線上課程。\n●　小黃做金融服務。\n他們都希望交流。\n請準時到場。'
        expected='明天有兩位來賓。\n\n●　小林做線上課程。\n●　小黃做金融服務。\n\n他們都希望交流。請準時到場。'
        self.assertEqual(layout(source),expected)
        self.assertEqual(layout(expected),expected)
        self.assertEqual(re.sub(r'\s','',source),re.sub(r'\s','',expected))
        self.assertEqual(layout('報告寄了。\n另外，明天休假。'),'報告寄了。\n\n另外，明天休假。')
        for literal in ('第一段。\n\n第二段。','地址\n臺北市中正區','```\n中文。\n程式。',
                        '他說「第一句。\n第二句。」','●　項目。\n  ●　子項目。','Hello.\nWorld.'):
            self.assertEqual(layout(literal),literal)
        self.assertEqual(layout(source,'每句換行'),source)

    def test_chinese_bullet_presentation_preserves_content_and_code(self):
        from taiwan_typography import chinese_bullet_style as bullets
        self.assertEqual(bullets('• 明天先去銀行。\n  • 不要取消。'), '●　明天先去銀行。\n  ●　不要取消。')
        self.assertEqual(bullets('●　明天先去銀行。'), '●　明天先去銀行。')
        for literal in ('```\n• 中文範例\n```', '`• 中文範例`', '`code`• 行內符號', '```\n• 未完成程式', '正文 • 中間符號', '1. 數字清單。'):
            self.assertEqual(bullets(literal),literal)

    def test_invented_bullets_in_complete_prose(self):
        from taiwan_typography import preserve_prose_layout as layout
        source='會議是下午兩點，不對，改成下午三點。只有小陳可以晚十分鐘，其他人不要遲到。'
        edited='會議是下午三點。\n• 只有小陳可以晚十分鐘，其他人不要遲到。'
        self.assertEqual(layout(source,edited),'會議是下午三點。只有小陳可以晚十分鐘，其他人不要遲到。')
        self.assertEqual(layout(source,edited,'請使用條列'),edited)
        for changed in (edited.replace('不要','要'),edited.replace('小陳','小林'),edited.replace('三點','四點'),edited.replace('不要','都不要')):
            self.assertEqual(layout(source,changed),changed)
        for original in ('明天要買東西。第一買牛奶，第二買雞蛋。',
                         '公司的信寄了。另外，家裡要買牛奶。',
                         '明天開會。\n只有小陳晚到。', '採買清單。牛奶、雞蛋。'):
            candidate=original.replace('。','。\n• ',1)
            self.assertEqual(layout(original,candidate),candidate)

    def test_chinese_punctuation_and_layout(self):
        self.assertEqual(clean('今天開會, 請準時!\r\n\r\n\r\n• 帶文件; 不要取消.\n'),
                         '今天開會，請準時！\n\n• 帶文件；不要取消。')
        self.assertEqual(clean('他說:"明天(週一)見!"'), '他說：「明天（週一）見！」')

    def test_literals_are_preserved(self):
        text = '價格 -1.5 元, 時間 10:30, 寄到 a@example.com, 版本 v1.2.3。'
        self.assertEqual(clean(text), '價格 -1.5 元，時間 10:30，寄到 a@example.com，版本 v1.2.3。')
        text = '網址 https://example.com/a?q=1&x=2 和 `a,b: c!`，程式\n```\na,b: c!\n```'
        self.assertEqual(clean(text), text)

    def test_english_quotes_and_lists(self):
        self.assertEqual(clean('保留 "Hello, world!"，不要改。'), '保留 "Hello, world!"，不要改。')
        self.assertEqual(clean('1. 今天開會.\n2. 明天休息.'), '1. 今天開會。\n2. 明天休息。')
        self.assertEqual(clean('Hello, world!'), 'Hello, world!')
        self.assertEqual(clean('第一段。\n\n第二段。'), '第一段。\n\n第二段。')

    def test_unfinished_code_keeps_literal_punctuation(self):
        for text in ('程式 `中文,a: b!', '程式\n```\n中文,a: b!',
                     '請保留 `中文,a!\n後續仍在程式內,b?'):
            self.assertEqual(clean(text), text)
        self.assertEqual(clean('程式 `中文,a!`，結束後,請確認.'),
                         '程式 `中文,a!`，結束後，請確認。')

    def test_literals_adjacent_to_chinese_without_spaces(self):
        # Chinese and digits both count as Unicode word characters: a regex
        # word boundary would miss these very common dictated spellings.
        self.assertEqual(clean('時間10:30,金額1,000元,日期2026/09/28.'),
                         '時間10:30，金額1,000元，日期2026/09/28。')
        self.assertEqual(clean('比例1:2,版本v1.2.3,不要取消!'),
                         '比例1:2，版本v1.2.3，不要取消！')
        self.assertEqual(clean('路徑C:\\Users\\test.txt 和程式foo.bar。'),
                         '路徑C:\\Users\\test.txt 和程式foo.bar。')

    def test_unquoted_english_sentence_in_chinese(self):
        self.assertEqual(clean('我想傳一句英文：Could you help me draft a plan? 先不要替我寫計畫。'),
                         '我想傳一句英文：Could you help me draft a plan? 先不要替我寫計畫。')
        self.assertEqual(clean('他說 Hello, world! 然後離開.'), '他說 Hello, world! 然後離開。')
        self.assertEqual(clean('你有用ChatGPT?'), '你有用ChatGPT？')

    def test_single_paragraph_style_variants(self):
        from personalization import apply_explicit_layout
        text='第一件事。\n第二件事。'
        self.assertEqual(apply_explicit_layout(text,'不要條列，保留成一段文字。'), '第一件事。 第二件事。')
        self.assertEqual(apply_explicit_layout(text,'不要整理成一段文字。'),text)


if __name__ == '__main__':
    unittest.main()
