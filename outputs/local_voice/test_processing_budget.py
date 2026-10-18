import asyncio
import unittest
from unittest.mock import patch
import httpx

from beta_api import LocalProvider
from processing_budget import format_before_deadline


class ProcessingDeadlineTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_translation_stages_share_total_budget(self):
        stages=[]
        async def translate():
            try:
                stages.append('bridge')
                await asyncio.sleep(.15)
                stages.append('target')
                await asyncio.sleep(.25)
                return 'late translation'
            finally:
                stages.append('closed')
        with patch('processing_budget.FORMAT_SECONDS', .3):
            with self.assertRaises(TimeoutError):
                await format_before_deadline(translate)
        self.assertEqual(stages, ['bridge', 'target', 'closed'])

    async def test_client_cancellation_is_not_converted_to_timeout(self):
        entered=asyncio.Event()
        async def wait():
            entered.set()
            await asyncio.Event().wait()
        task=asyncio.create_task(format_before_deadline(wait))
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task

    async def test_dripping_http_body_cannot_extend_provider_deadline(self):
        closed=asyncio.Event()
        class Body(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'{"text":"'
                while True:
                    await asyncio.sleep(.005)
                    yield b'x'
            async def aclose(self):closed.set()
        def response(request):return httpx.Response(200, stream=Body())
        original=httpx.AsyncClient
        def client(**kwargs):return original(transport=httpx.MockTransport(response), **kwargs)
        with patch('beta_api.LOCAL_PROVIDER_SECONDS', .04), patch('beta_api.httpx.AsyncClient', client):
            with self.assertRaises(TimeoutError):
                await LocalProvider('http://test', 'synthetic').transcribe(b'fixture', {})
        self.assertTrue(closed.is_set())
