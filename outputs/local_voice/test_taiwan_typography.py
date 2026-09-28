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


if __name__ == '__main__':
    unittest.main()
