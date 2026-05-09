import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.audio_analysis import AudioAnalysisService, localize_fillers


def make_result(words: list[str | tuple[str, float, float]]) -> dict:
    word_entries: list[dict] = []
    for index, item in enumerate(words):
        if isinstance(item, tuple):
            word, start, end = item
        else:
            word = item
            start = index * 0.2
            end = start + 0.12
        word_entries.append({"word": word, "start": start, "end": end})

    text = " ".join(entry["word"] for entry in word_entries)
    audio_duration = max((entry["end"] for entry in word_entries), default=0.0)
    return {
        "text": text,
        "audio_duration": audio_duration,
        "segments": [{
            "start": 0.0,
            "end": audio_duration,
            "text": text,
            "words": word_entries,
        }],
    }


def detected_words(words: list[str | tuple[str, float, float]]) -> list[str]:
    fillers, _, _, _ = AudioAnalysisService().analyze_transcript(make_result(words))
    return [f.word for f in fillers]


class FillerDetectionTest(unittest.TestCase):
    def test_detects_hesitation_variants_as_canonical_fillers(self) -> None:
        words = ["Ummm,", "uhh", "erm", "hmmmm", "ahh"]

        self.assertEqual(
            detected_words(words),
            ["um", "uh", "erm", "hmm", "ah"],
        )

    def test_ignores_common_semantic_uses_of_ambiguous_words(self) -> None:
        words = [
            "So", "that", "I", "like", "the", "right", "answer",
            "actually", "works", "well", "okay", "with", "me",
            "clearly",
        ]

        self.assertEqual(detected_words(words), [])

    def test_detects_contextual_discourse_markers_at_boundaries(self) -> None:
        words = [
            "So,", "actually,", "I", "mean,", "you", "know,",
            "like,", "right,", "okay",
        ]

        self.assertEqual(
            detected_words(words),
            ["so", "actually", "i mean", "you know", "like", "right", "okay"],
        )

    def test_ignores_semantic_uses_of_multi_word_phrases(self) -> None:
        words = [
            "what", "kind", "of", "project",
            "people", "you", "know", "can", "help",
            "what", "I", "mean", "is", "clear",
            "a", "sort", "of", "pattern",
            "You", "know", "the", "answer",
            "I", "mean", "it",
        ]

        self.assertEqual(detected_words(words), [])

    def test_localizes_phrase_filler_that_crosses_final_report_window(self) -> None:
        result = make_result([
            ("said,", 9.2, 9.35),
            ("you", 9.9, 9.98),
            ("know,", 10.05, 10.2),
            ("this", 10.3, 10.45),
        ])
        fillers, _, _, _ = AudioAnalysisService().analyze_transcript(result)

        self.assertEqual(
            [(f.word, f.timestamp, f.count) for f in fillers],
            [("you know", 9.9, 1)],
        )
        self.assertEqual(
            [(f.word, f.timestamp, f.count) for f in localize_fillers(fillers, 0.0, 10.0)],
            [("you know", 9.9, 1)],
        )
        self.assertEqual(localize_fillers(fillers, 10.0, 20.0), [])


if __name__ == "__main__":
    unittest.main()
