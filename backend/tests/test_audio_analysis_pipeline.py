import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.audio_analysis import AudioAnalysisService


def make_result(
    words: list[str | tuple[str, float, float]],
    *,
    audio_duration: float | None = None,
) -> dict:
    word_entries: list[dict] = []
    for index, item in enumerate(words):
        if isinstance(item, tuple):
            word, start, end = item
        else:
            word = item
            start = index * 0.1
            end = start + 0.05
        word_entries.append({"word": word, "start": start, "end": end})

    text = " ".join(entry["word"] for entry in word_entries)
    duration = (
        audio_duration
        if audio_duration is not None
        else max((entry["end"] for entry in word_entries), default=0.0)
    )
    return {
        "text": text,
        "audio_duration": duration,
        "segments": [{
            "start": 0.0,
            "end": max((entry["end"] for entry in word_entries), default=0.0),
            "text": text,
            "words": word_entries,
        }],
    }


class AudioAnalysisPipelineTest(unittest.TestCase):
    def test_wpm_uses_audio_window_not_compressed_word_timestamps(self) -> None:
        result = make_result([f"word{i}" for i in range(10)], audio_duration=5.0)

        _, speed, _, _ = AudioAnalysisService().analyze_transcript(result)

        self.assertEqual(speed.current_wpm, 120.0)
        self.assertEqual(speed.baseline_wpm, 120.0)
        self.assertFalse(speed.is_spike)

    def test_speed_spike_generates_live_feedback_after_baseline_exists(self) -> None:
        analysis = AudioAnalysisService()
        baseline_result = make_result([f"base{i}" for i in range(8)], audio_duration=4.0)
        for _ in range(3):
            analysis.analyze_transcript(baseline_result)

        spike_result = make_result([f"fast{i}" for i in range(14)], audio_duration=4.0)
        _, speed, pauses, feedback = analysis.analyze_transcript(spike_result)
        breath_advice = analysis.suggest_breath_control(speed, pauses)

        self.assertEqual(speed.current_wpm, 210.0)
        self.assertEqual(speed.baseline_wpm, 120.0)
        self.assertTrue(speed.is_spike)
        self.assertEqual(speed.spike_factor, 1.75)
        self.assertTrue(breath_advice.should_pause)
        self.assertIn("speed", [item.type for item in feedback])

    def test_word_timestamp_gaps_become_pause_events(self) -> None:
        result = make_result(
            [
                ("first", 0.0, 0.2),
                ("second", 1.15, 1.35),
                ("third", 3.8, 4.0),
            ],
            audio_duration=5.0,
        )

        _, _, pauses, feedback = AudioAnalysisService().analyze_transcript(result)

        self.assertEqual(len(pauses), 2)
        self.assertEqual(
            [(pause.start, pause.end, pause.duration) for pause in pauses],
            [(0.2, 1.15, 0.95), (1.35, 3.8, 2.45)],
        )
        self.assertIn("breath", [item.type for item in feedback])


if __name__ == "__main__":
    unittest.main()
