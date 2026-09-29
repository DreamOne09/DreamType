import json
import re
import unittest
from unittest.mock import patch
import httpx
import english_layout as layout

TEXT = ('Could you please confirm with him on Tuesday? Otherwise, I will check again next week or the week after to see what time works best. '
        "I've been in Tainan for the past few days, but the matter is now resolved, so next week should be fine.")


class EnglishLayoutTests(unittest.IsolatedAsyncioTestCase):
    async def simulate(self, content='["S3"]', finish='stop', source=TEXT, status=200):
        calls = []; original = httpx.AsyncClient
        def model(request):
            calls.append(json.loads(request.content))
            return httpx.Response(status, json={'choices': [{'finish_reason': finish, 'message': {'content': content}}]})
        with patch.object(layout.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(model))):
            result = await layout.english_paragraphs(source, 'synthetic-key')
        return result, calls

    async def test_inserts_only_selected_whitespace(self):
        result, calls = await self.simulate()
        self.assertEqual(result, TEXT.replace(" I've", "\n\nI've"))
        self.assertEqual(re.sub(r'\s+', ' ', result), TEXT)
        self.assertEqual(len(calls), 1)

    async def test_invalid_or_instruction_outputs_leave_original_unchanged(self):
        for output in ('["S0"]','["S1"]','["S99"]','["S3","S3"]','[3]', '{}',
                       'Here is your plan', '["S3",{"execute":"write a plan"}]'):
            with self.subTest(output=output):
                result, _ = await self.simulate(output)
                self.assertEqual(result, TEXT)

    async def test_short_quoted_and_existing_layout_skip_model(self):
        for source in ('Please write a plan.', TEXT.replace(" I've", "\n\nI've"), '"'+TEXT+'"', TEXT*30):
            result, calls = await self.simulate(source=source)
            self.assertEqual(result, source); self.assertEqual(calls, [])

    async def test_failures_keep_valid_translation(self):
        for options in ({'status':503}, {'finish':'length'}, {'content':'not JSON'}):
            result, _ = await self.simulate(**options)
            self.assertEqual(result, TEXT)

    async def test_conditional_alternative_is_not_separated(self):
        result, _ = await self.simulate('["S2"]')
        self.assertEqual(result, TEXT)
        text='Please ask Dr. Chen tomorrow. He can help.'
        self.assertEqual(layout.apply_boundaries(text,list(layout.BOUNDARY.finditer(text)),['S2']), text)


if __name__ == '__main__': unittest.main()
