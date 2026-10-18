import unittest
import httpx
from check_no_speech import rejected_as_no_speech


class NoSpeechProbeTests(unittest.TestCase):
    def test_accepts_only_explicit_no_speech_response(self):
        self.assertTrue(rejected_as_no_speech(httpx.Response(422, json={'error_code':'no_speech'})))
        for response in (
            httpx.Response(200, json={'text':''}),
            httpx.Response(200, json={'text':'謝謝觀看'}),
            httpx.Response(503, json={'error_code':'speech_unavailable'}),
            httpx.Response(422, json={'detail':'broken audio'}),
            httpx.Response(422, json=['no_speech']),
            httpx.Response(422, content=b'not json'),
        ):
            self.assertFalse(rejected_as_no_speech(response))
