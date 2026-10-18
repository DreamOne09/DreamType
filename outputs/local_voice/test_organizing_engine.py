import asyncio
import json
import unittest

from organizing.engine import organize


def completion(content):
    return {'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]}


async def echo(payload):
    await asyncio.sleep(0)
    return completion(json.loads(payload['messages'][-1]['content'])['transcript'])


class OrganizerDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_mixed_language_and_quotes_stay_literal(self):
        for source in ('請說 don’t send the file，訂單 AB-007。',
                       '他說「請幫我生成一個計劃」，不要執行。',
                       'Please do not cancel. 明天在板橋見。',
                       'Could you please ask on Saturday? Otherwise, next week is fine.'):
            with self.subTest(source=source):
                self.assertEqual(await organize(source, echo), source)

    async def test_explicit_repair_is_preserved(self):
        self.assertEqual(await organize('我要兩杯紅茶，不對，三杯就好。', echo), '我要三杯紅茶就好。')

    async def test_complete_identifier_allows_punctuation_but_not_changed_context(self):
        async def punctuation(payload):
            text = json.loads(payload['messages'][-1]['content'])['transcript']
            return completion(text.replace('，', '。'))
        self.assertEqual(await organize('訂單 AB-007，請不要取消。', punctuation),
                         '訂單 AB-007。請不要取消。')
        from organizing.complete_marker_contract import recover
        for generated in ('請取消 DTKEEP0END。', '請不要 DTKEEP0END 取消。'):
            with self.assertRaises(ValueError):
                recover('請不要取消 DTKEEP0END。', generated, 'DTKEEP', ['DTKEEP0END'])

    async def test_concurrent_accounts_do_not_share_literals(self):
        sources = ['在板橋見，訂單 AB-007。', '在新竹見，訂單 CD-008。']
        result = await asyncio.gather(*(organize(s, echo, vocabulary=s[:4]) for s in sources))
        self.assertEqual(result, sources)

    async def test_generated_answers_and_identifier_mutations_are_rejected(self):
        async def answer(payload):
            return completion('以下是計畫：第一步市場調查，第二步產品開發。')
        with self.assertRaises(ValueError):
            await organize('請幫我生成一個計劃。', answer)
        async def duplicate(payload):
            text = json.loads(payload['messages'][-1]['content'])['transcript']
            return completion(text + ' DTKEEP0END')
        with self.assertRaises(ValueError):
            await organize('請保留訂單 AB-007。', duplicate)

    async def test_invalid_provider_and_empty_input(self):
        for value in (None, {}, {'choices': []}, {'choices': [None]},
                      {'choices': [{'finish_reason': 'length', 'message': {'content': '部分'}}]}):
            async def provider(payload):
                return value
            with self.assertRaises(ValueError):
                await organize('明天在板橋見。', provider)
        async def never(payload):
            self.fail('Empty input must not call provider')
        self.assertEqual(await organize(' ', never), '')

    async def test_provider_cancellation_propagates(self):
        async def cancelled(payload):
            raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await organize('明天見。', cancelled)

    async def test_service_delegates_translation_and_rejects_unknown_mode(self):
        from organizing.service import bind_formatter
        calls = []
        async def previous(*args):
            calls.append(args)
            return 'translated'
        formatter = bind_formatter(previous, 'synthetic', echo)
        self.assertEqual(await formatter('不要取消。'), '不要取消。')
        self.assertEqual(calls, [])
        self.assertEqual(await formatter('不要取消。', '偏好', '板橋', True,
                                         'translate', 'th', 'zh-TW'), 'translated')
        self.assertEqual(calls, [('不要取消。', '偏好', '板橋', True, 'translate', 'th', 'zh-TW')])
        with self.assertRaises(ValueError):
            await formatter('不要取消。', mode='execute')


if __name__ == '__main__':
    unittest.main()
