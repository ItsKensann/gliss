import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.session import Pause
from app.services.audio_analysis import detect_audio_pauses, localize_pauses


SAMPLE_RATE = 16_000


def speech(seconds: float, amplitude: float = 0.08) -> np.ndarray:
    return np.full(int(SAMPLE_RATE * seconds), amplitude, dtype=np.float32)


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * seconds), dtype=np.float32)


class PauseDetectionTest(unittest.TestCase):
    def test_detects_intentional_three_five_and_ten_second_pauses(self) -> None:
        audio = np.concatenate([
            speech(1.0),
            silence(3.0),
            speech(1.0),
            silence(5.0),
            speech(1.0),
            silence(10.0),
            speech(1.0),
        ])

        pauses = detect_audio_pauses(audio, SAMPLE_RATE, silence_threshold=0.01)

        self.assertEqual(len(pauses), 3)
        expected = [
            (1.0, 4.0, 3.0),
            (5.0, 10.0, 5.0),
            (11.0, 21.0, 10.0),
        ]
        for pause, (start, end, duration) in zip(pauses, expected):
            with self.subTest(pause=pause):
                self.assertAlmostEqual(pause.start, start, delta=0.06)
                self.assertAlmostEqual(pause.end, end, delta=0.06)
                self.assertAlmostEqual(pause.duration, duration, delta=0.06)

    def test_ignores_leading_trailing_and_short_silence(self) -> None:
        audio = np.concatenate([
            silence(2.0),
            speech(1.0),
            silence(0.5),
            speech(1.0),
            silence(2.0),
        ])

        pauses = detect_audio_pauses(audio, SAMPLE_RATE, silence_threshold=0.01)

        self.assertEqual(pauses, [])

    def test_merges_short_speech_blips_inside_pause(self) -> None:
        audio = np.concatenate([
            speech(1.0),
            silence(1.5),
            speech(0.1),
            silence(1.4),
            speech(1.0),
        ])

        pauses = detect_audio_pauses(audio, SAMPLE_RATE, silence_threshold=0.01)

        self.assertEqual(len(pauses), 1)
        self.assertAlmostEqual(pauses[0].duration, 3.0, delta=0.11)

    def test_localizes_pause_to_chunk_containing_pause_start(self) -> None:
        pauses = [Pause(start=9.0, end=12.5, duration=3.5)]

        first_chunk = localize_pauses(pauses, 0.0, 10.0)
        second_chunk = localize_pauses(pauses, 10.0, 20.0)

        self.assertEqual(first_chunk, [Pause(start=9.0, end=12.5, duration=3.5)])
        self.assertEqual(second_chunk, [])


if __name__ == "__main__":
    unittest.main()
