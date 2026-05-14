import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.session import (
    AnalysisResult,
    FillerWord,
    ImmediateFeedback,
    PaceEvent,
    Pause,
    SessionReport,
    SpeedAnalysis,
)
from app.services import session_store


def make_chunk(
    *,
    transcript: str,
    wpm: float,
    fillers: list[str],
    pauses: list[Pause],
    start: float,
    end: float,
    eye: float | None = None,
    head: float | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        transcript=transcript,
        filler_words=[
            FillerWord(word=word, timestamp=start + index * 0.2, count=index + 1)
            for index, word in enumerate(fillers)
        ],
        speed=SpeedAnalysis(
            current_wpm=wpm,
            baseline_wpm=120.0,
            is_spike=wpm > 170.0,
            spike_factor=round(wpm / 120.0, 2),
        ),
        pauses=pauses,
        immediate_feedback=[
            ImmediateFeedback(message="test feedback", type="speed", severity="info")
        ],
        start_offset_seconds=start,
        end_offset_seconds=end,
        avg_eye_contact=eye,
        avg_head_stability=head,
    )


class SessionReportSerializationTest(unittest.TestCase):
    def test_build_report_derives_summary_from_analysis_chunks(self) -> None:
        started_at = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
        ended_at = datetime(2026, 5, 11, 12, 0, 30, tzinfo=timezone.utc)
        chunks = [
            make_chunk(
                transcript="um opening thought",
                wpm=120.0,
                fillers=["um"],
                pauses=[Pause(start=1.0, end=2.0, duration=1.0)],
                start=0.0,
                end=10.0,
                eye=0.5,
                head=0.9,
            ),
            make_chunk(
                transcript="like follow up um",
                wpm=180.0,
                fillers=["like", "um"],
                pauses=[
                    Pause(start=2.0, end=4.0, duration=2.0),
                    Pause(start=7.0, end=9.0, duration=2.0),
                ],
                start=10.0,
                end=30.0,
                eye=0.8,
                head=0.6,
            ),
        ]
        pace_event = PaceEvent(
            start_seconds=10.0,
            end_seconds=18.0,
            wpm=180.0,
            baseline_wpm=120.0,
            spike_factor=1.5,
            excerpt="like follow up",
        )

        report = session_store.build_report(
            "report-summary",
            started_at,
            ended_at,
            chunks,
            "um opening thought like follow up um",
            prompt="Tell me about a project.",
            target_duration_seconds=60.0,
            is_finalized=False,
            pace_events=[pace_event],
        )

        self.assertEqual(report.duration_seconds, 30.0)
        self.assertEqual(report.summary.total_words, 7)
        self.assertEqual(report.summary.avg_wpm, 150.0)
        self.assertEqual(report.summary.peak_wpm, 180.0)
        self.assertEqual(report.summary.filler_counts, {"um": 2, "like": 1})
        self.assertEqual(report.summary.total_pauses, 3)
        self.assertEqual(report.summary.avg_eye_contact, 0.7)
        self.assertEqual(report.summary.avg_head_stability, 0.7)
        self.assertEqual(report.prompt, "Tell me about a project.")
        self.assertEqual(report.target_duration_seconds, 60.0)
        self.assertFalse(report.is_finalized)
        self.assertEqual(report.pace_events, [pace_event])

    def test_report_json_round_trip_preserves_nested_analysis_contract(self) -> None:
        started_at = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
        ended_at = datetime(2026, 5, 11, 12, 1, tzinfo=timezone.utc)
        report = session_store.build_report(
            "round-trip",
            started_at,
            ended_at,
            [
                make_chunk(
                    transcript="um concise answer",
                    wpm=130.0,
                    fillers=["um"],
                    pauses=[Pause(start=1.0, end=2.1, duration=1.1)],
                    start=0.0,
                    end=10.0,
                )
            ],
            "um concise answer",
        )

        parsed = SessionReport.model_validate_json(report.model_dump_json())

        self.assertEqual(parsed.session_id, "round-trip")
        self.assertEqual(parsed.chunks[0].filler_words[0].word, "um")
        self.assertEqual(parsed.chunks[0].pauses[0].duration, 1.1)
        self.assertEqual(parsed.summary.filler_counts, {"um": 1})

    def test_save_and_load_report_uses_pydantic_json_contract(self) -> None:
        started_at = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
        ended_at = datetime(2026, 5, 11, 12, 0, 10, tzinfo=timezone.utc)
        report = session_store.build_report(
            "persisted-report",
            started_at,
            ended_at,
            [],
            "short transcript",
            is_finalized=True,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.object(session_store, "SESSIONS_DIR", Path(tmp_dir)):
                session_store.save_report(report)
                loaded = session_store.load_report("persisted-report")

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded, report)


if __name__ == "__main__":
    unittest.main()
