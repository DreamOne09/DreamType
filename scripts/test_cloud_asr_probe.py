import asyncio
import base64
import contextlib
import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import httpx
import cloud_asr_probe as probe


def wav_bytes(frames=1600):
    data = io.BytesIO()
    with wave.open(data, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
        wav.writeframes(b'\0\0' * frames)
    return data.getvalue()


class CloudProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_cloudflare_only_sends_documented_base64_to_fixed_account(self):
        audio = wav_bytes()
        def handle(request):
            self.assertEqual(str(request.url), 'https://api.cloudflare.com/client/v4/accounts/' + 'a'*32 + '/ai/run/@cf/openai/whisper-large-v3-turbo')
            self.assertEqual(request.headers['authorization'], 'Bearer synthetic-key')
            body = json.loads(request.content)
            self.assertEqual(base64.b64decode(body['audio']), audio)
            self.assertEqual(body['task'], 'transcribe')
            self.assertEqual(body['language'], 'zh')
            return httpx.Response(200, json={'success': True, 'result': {'text': '新竹見。'}})
        result = await probe.transcribe('cloudflare', audio, 'synthetic-key', 'a'*32, transport=httpx.MockTransport(handle))
        self.assertEqual(result['text'], '新竹見。')

    async def test_groq_multipart_keeps_audio_and_hides_original_filename(self):
        audio = wav_bytes()
        def handle(request):
            self.assertEqual(str(request.url), 'https://api.groq.com/openai/v1/audio/transcriptions')
            self.assertIn('multipart/form-data', request.headers['content-type'])
            self.assertIn(b'filename="clip.wav"', request.content)
            self.assertIn(audio, request.content)
            self.assertIn(b'whisper-large-v3-turbo', request.content)
            return httpx.Response(200, json={'text': '您好。'})
        result = await probe.transcribe('groq', audio, 'synthetic-key', transport=httpx.MockTransport(handle))
        self.assertFalse(result['empty'])

    async def test_no_redirect_retry_or_remote_error_leak(self):
        for status, code in [(302, 'redirect_refused'), (429, 'quota_or_rate_limit'),
                             (401, 'authentication'), (500, 'provider_http_error')]:
            calls = []
            def handle(request):
                calls.append(request)
                return httpx.Response(status, headers={'location': 'https://untrusted.invalid/'}, text='private transcript or key')
            with self.assertRaises(probe.ProbeError) as error:
                await probe.transcribe('groq', wav_bytes(), 'synthetic-key', transport=httpx.MockTransport(handle))
            self.assertEqual(str(error.exception), code)
            self.assertEqual(len(calls), 1)

    async def test_empty_response_is_not_successful_speech(self):
        result = await probe.transcribe('groq', wav_bytes(), 'synthetic-key',
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'text': '  '})))
        self.assertTrue(result['empty'])

    async def test_bounded_deadline_even_when_transport_never_returns(self):
        async def handle(request):
            await asyncio.Event().wait()
        with self.assertRaises(probe.ProbeError) as error:
            await probe.transcribe('groq', wav_bytes(), 'synthetic-key',
                transport=httpx.MockTransport(handle), deadline=0.01)
        self.assertEqual(str(error.exception), 'timeout')

    async def test_rejects_malformed_and_oversized_responses(self):
        for response, code in [(httpx.Response(200, content=b'{'), 'invalid_response'),
                               (httpx.Response(200, json={'text': 42}), 'invalid_response'),
                               (httpx.Response(200, content=b'x'*(probe.MAX_RESPONSE+1)), 'response_too_large')]:
            with self.assertRaises(probe.ProbeError) as error:
                await probe.transcribe('groq', wav_bytes(), 'synthetic-key',
                    transport=httpx.MockTransport(lambda request: response))
            self.assertEqual(str(error.exception), code)

    async def test_cloudflare_unsuccessful_envelope_is_not_accepted(self):
        with self.assertRaises(probe.ProbeError) as error:
            await probe.transcribe('cloudflare', wav_bytes(), 'synthetic-key', 'a'*32,
                transport=httpx.MockTransport(lambda request: httpx.Response(200,
                    json={'success': False, 'result': {'text': 'unverified'}})))
        self.assertEqual(str(error.exception), 'provider_error')

    async def test_account_path_and_header_injection_rejected_before_network(self):
        with self.assertRaises(ValueError):
            probe.request_options('cloudflare', b'audio', '../other-account')
        with self.assertRaises(ValueError):
            await probe.transcribe('groq', b'audio', 'key\nInjected: value')


class ProbeCliTests(unittest.TestCase):
    def test_default_dry_run_never_requests_credentials_or_connects(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private-name.wav'; path.write_bytes(wav_bytes())
            output = io.StringIO()
            with patch.object(probe.getpass, 'getpass') as password, patch.object(probe, 'transcribe') as remote, contextlib.redirect_stdout(output):
                self.assertEqual(probe.main(['--provider', 'groq', '--audio', str(path)]), 0)
            password.assert_not_called(); remote.assert_not_called()
            report = json.loads(output.getvalue())
            self.assertEqual(report['requests'], 0)
            self.assertEqual(report['audio_seconds'], 0.1)
            self.assertNotIn('private-name', output.getvalue())

    def test_short_or_truncated_wav_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'clip.wav'
            for audio in (wav_bytes(0), wav_bytes()[:-10], b'not audio'):
                path.write_bytes(audio)
                with self.assertRaises((ValueError, EOFError, wave.Error)):
                    probe.read_clip(path)

    def test_upload_report_omits_transcript_by_default(self):
        async def fake(*args, **kwargs):
            return {'text': 'private text', 'empty': False, 'request_seconds': 0.1, 'http_status': 200}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'clip.wav'; path.write_bytes(wav_bytes())
            output = io.StringIO()
            with patch.object(probe.getpass, 'getpass', return_value='synthetic-key'), patch.object(probe, 'transcribe', fake), contextlib.redirect_stdout(output):
                self.assertEqual(probe.main(['--provider', 'groq', '--audio', str(path), '--upload']), 0)
            self.assertNotIn('private text', output.getvalue())
            self.assertNotIn('synthetic-key', output.getvalue())


if __name__ == '__main__':
    unittest.main()
