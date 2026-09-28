import unittest
from taiwan_typography import normalize_taiwan_typography as clean


class TaiwanTypographyTests(unittest.TestCase):
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
