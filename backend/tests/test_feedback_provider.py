import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.session import SessionReport, SessionSummary
from app.services.feedback import MockFeedbackProvider


def make_report(
    *,
    words: int = 100,
    duration_seconds: float = 60.0,
    avg_wpm: float = 145.0,
    peak_wpm: float = 150.0,
    fillers: dict[str, int] | None = None,
    pauses: int = 1,
    eye_contact: float | None = None,
    transcript: str | None = None,
) -> SessionReport:
    return SessionReport(
        session_id="test-session",
        started_at="2026-05-11T12:00:00+00:00",
        ended_at="2026-05-11T12:01:00+00:00",
        duration_seconds=duration_seconds,
        full_transcript=transcript if transcript is not None else "word " * words,
        chunks=[],
        summary=SessionSummary(
            total_words=words,
            avg_wpm=avg_wpm,
            peak_wpm=peak_wpm,
            filler_counts=fillers or {},
            total_pauses=pauses,
            avg_eye_contact=eye_contact,
        ),
    )


class MockFeedbackProviderTest(unittest.IsolatedAsyncioTestCase):
    async def test_prioritizes_high_filler_rate_with_supportive_language(self) -> None:
        report = make_report(
            words=100,
            fillers={"um": 7},
            transcript="I think um this is the part I want to practice.",
        )

        feedback = await MockFeedbackProvider().generate(report)

        self.assertEqual(feedback.generated_by, "mock")
        self.assertEqual(feedback.priority_focus.area, "fillers")
        self.assertIn("short pause", feedback.overall)
        self.assertIn("um", feedback.priority_focus.observation)
        self.assertIn("um", feedback.priority_focus.excerpt or "")
        combined = " ".join([
            feedback.overall,
            feedback.priority_focus.why_it_matters,
            feedback.encouragement,
        ]).lower()
        self.assertNotIn("leak certainty", combined)
        self.assertNotIn("bailing", combined)
        self.assertNotIn("screaming", combined)

    async def test_prioritizes_fast_pace_when_no_filler_issue(self) -> None:
        report = make_report(words=120, avg_wpm=182.0, peak_wpm=210.0, pauses=2)

        feedback = await MockFeedbackProvider().generate(report)

        self.assertEqual(feedback.priority_focus.area, "pace")
        self.assertIn("140-160 WPM", feedback.priority_focus.observation)
        self.assertIn("articulation", feedback.priority_focus.why_it_matters)

    async def test_prioritizes_slow_pace_with_practice_framing(self) -> None:
        report = make_report(words=60, avg_wpm=96.0, peak_wpm=110.0, pauses=1)

        feedback = await MockFeedbackProvider().generate(report)

        self.assertEqual(feedback.priority_focus.area, "pace")
        self.assertIn("slower side", feedback.priority_focus.observation)
        self.assertIn("connected speech", feedback.priority_focus.why_it_matters)

    async def test_prioritizes_pauses_when_pace_is_steady_but_no_resets(self) -> None:
        report = make_report(words=150, duration_seconds=60.0, avg_wpm=145.0, pauses=0)

        feedback = await MockFeedbackProvider().generate(report)

        self.assertEqual(feedback.priority_focus.area, "pauses")
        self.assertIn("breathing", feedback.priority_focus.why_it_matters)
        self.assertIn("two full seconds", feedback.drill_suggestion)

    async def test_uses_default_delivery_focus_for_steady_session(self) -> None:
        report = make_report(
            words=220,
            duration_seconds=120.0,
            avg_wpm=145.0,
            peak_wpm=155.0,
            pauses=3,
            eye_contact=0.9,
        )

        feedback = await MockFeedbackProvider().generate(report)

        self.assertEqual(feedback.priority_focus.area, "delivery")
        self.assertGreaterEqual(len(feedback.strengths), 2)
        self.assertLessEqual(len(feedback.strengths), 3)

    async def test_missing_eye_contact_does_not_create_eye_contact_focus(self) -> None:
        report = make_report(words=100, avg_wpm=145.0, pauses=0, eye_contact=None)

        feedback = await MockFeedbackProvider().generate(report)

        areas = [feedback.priority_focus.area, *(focus.area for focus in feedback.secondary_focuses)]
        self.assertNotIn("eye_contact", areas)

    async def test_zero_word_report_returns_limited_feedback_without_crashing(self) -> None:
        report = make_report(words=0, duration_seconds=5.0, avg_wpm=0.0, peak_wpm=0.0)

        feedback = await MockFeedbackProvider().generate(report)

        self.assertEqual(feedback.priority_focus.area, "delivery")
        self.assertIn("did not capture enough speech", feedback.overall)


if __name__ == "__main__":
    unittest.main()
