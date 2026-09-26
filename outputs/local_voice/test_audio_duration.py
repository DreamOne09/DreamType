"""Real decoded WAV boundaries: billing and the 120-second upload limit."""
import io
import math
import unittest
import wave

from beta_api import audio_duration


def wav(samples, rate=16000):
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(b'\0\0' * samples)
    return stream.getvalue()


class AudioDurationTests(unittest.TestCase):
    def test_exact_seconds_do_not_charge_extra_or_reject_limit(self):
        for rate in (16000, 44100, 48000):
            for seconds in (5, 30, 60, 120):
                with self.subTest(rate=rate, seconds=seconds):
                    actual = audio_duration(wav(rate * seconds, rate))
                    self.assertEqual(actual, seconds)
                    self.assertEqual(math.ceil(actual), seconds)
                    self.assertLessEqual(actual, 120)

    def test_real_fractional_second_still_rounds_up(self):
        actual = audio_duration(wav(5 * 16000 + 1))
        self.assertGreater(actual, 5)
        self.assertEqual(math.ceil(actual), 6)

    def test_one_sample_over_limit_is_rejected(self):
        self.assertGreater(audio_duration(wav(120 * 16000 + 1)), 120)


if __name__ == '__main__':
    unittest.main()
