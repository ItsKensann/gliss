import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.session import PaceEvent
from app.services.audio_analysis import detect_pace_events
from app.services.session_store import build_report


def make_segments(schedule: list[tuple[float, float, float]]) -> list[dict]:
    words: list[dict] = []
    index = 0
    for start, end, wpm in schedule:
        interval = 60.0 / wpm
        timestamp = start
        while timestamp < end:
            words.append({
                "word": f"word{index}",
                "start": round(timestamp, 2),
                "end": round(timestamp + 0.18, 2),
            })
            index += 1
            timestamp += interval
    return [{
        "start": schedule[0][0] if schedule else 0.0,
        "end": schedule[-1][1] if schedule else 0.0,
        "text": " ".join(word["word"] for word in words),
        "words": words,
    }]


class PaceEventTest(unittest.TestCase):
    def test_constant_pace_produces_no_fast_event(self) -> None:
        segments = make_segments([(0.0, 40.0, 150.0)])

        self.assertEqual(detect_pace_events(segments, 40.0), [])

    def test_speed_up_at_twenty_four_seconds_marks_onset(self) -> None:
        segments = make_segments([
            (0.0, 24.0, 100.0),
            (24.0, 42.0, 180.0),
        ])

        events = detect_pace_events(segments, 42.0)

        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0].start_seconds, 24.0, delta=2.0)
        self.assertGreaterEqual(events[0].wpm, events[0].baseline_wpm * 1.35)
        self.assertGreaterEqual(events[0].wpm, 120.0)

    def test_consecutive_fast_windows_collapse_into_one_event(self) -> None:
        segments = make_segments([
            (0.0, 24.0, 100.0),
            (24.0, 36.0, 180.0),
            (36.0, 46.0, 100.0),
        ])

        events = detect_pace_events(segments, 46.0)

        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0].start_seconds, 24.0, delta=2.0)
        self.assertGreater(events[0].end_seconds, events[0].start_seconds)

    def test_short_and_empty_sessions_produce_no_events(self) -> None:
        self.assertEqual(detect_pace_events([], 0.0), [])
        self.assertEqual(detect_pace_events(make_segments([(0.0, 3.0, 180.0)]), 3.0), [])

    def test_report_serialization_includes_pace_events(self) -> None:
        started_at = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
        ended_at = datetime(2026, 5, 11, 12, 1, tzinfo=timezone.utc)
        event = PaceEvent(
            start_seconds=24.0,
            end_seconds=34.0,
            wpm=180.0,
            baseline_wpm=100.0,
            spike_factor=1.8,
            excerpt="word word word",
        )

        report = build_report(
            "session-id",
            started_at,
            ended_at,
            [],
            "word word word",
            pace_events=[event],
        )

        self.assertEqual(report.pace_events, [event])
        self.assertIn('"pace_events"', report.model_dump_json())


if __name__ == "__main__":
    unittest.main()
