import unittest
from pathlib import Path
from speech_profile import speech_model_path


class SpeechProfileTests(unittest.TestCase):
    def test_default_and_candidate_are_fixed_local_paths(self):
        self.assertEqual(speech_model_path(Path('work')),Path('work/models/whisper-turbo'))
        self.assertEqual(speech_model_path(Path('work'),'breeze'),Path('work/models/breeze-asr-25/int8_float16'))

    def test_invalid_profile_does_not_silently_fallback_or_accept_paths(self):
        for profile in ('','unknown','../other','https://example.com/model',True,None):
            with self.subTest(profile=profile),self.assertRaises(ValueError):
                speech_model_path(Path('work'),profile)


if __name__=='__main__':unittest.main()
