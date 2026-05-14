import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.session import Focus, SessionReport, SessionSummary, StructuredFeedback
from app.services.feedback import MockFeedbackProvider


def make_report() -> SessionReport:
    return SessionReport(
        session_id="feedback-schema",
        started_at="2026-05-11T12:00:00+00:00",
        ended_at="2026-05-11T12:01:00+00:00",
        duration_seconds=60.0,
        full_transcript="I think um this answer needs a cleaner pause.",
        chunks=[],
        summary=SessionSummary(
            total_words=100,
            avg_wpm=145.0,
            peak_wpm=150.0,
            filler_counts={"um": 6},
            total_pauses=1,
            avg_eye_contact=0.75,
        ),
    )


class FeedbackSchemaTest(unittest.IsolatedAsyncioTestCase):
    async def test_mock_feedback_output_round_trips_through_pydantic_schema(self) -> None:
        feedback = await MockFeedbackProvider().generate(make_report())

        parsed = StructuredFeedback.model_validate_json(feedback.model_dump_json())

        self.assertEqual(parsed.generated_by, "mock")
        self.assertEqual(parsed.feedback_version, "v1")
        self.assertEqual(parsed.priority_focus.area, "fillers")
        self.assertGreaterEqual(len(parsed.strengths), 1)
        self.assertLessEqual(len(parsed.secondary_focuses), 2)

    async def test_session_report_accepts_serialized_structured_feedback(self) -> None:
        report = make_report()
        report.structured_feedback = await MockFeedbackProvider().generate(report)

        parsed = SessionReport.model_validate_json(report.model_dump_json())

        self.assertIsNotNone(parsed.structured_feedback)
        self.assertEqual(parsed.structured_feedback.generated_by, "mock")
        self.assertEqual(parsed.structured_feedback.priority_focus.area, "fillers")

    def test_feedback_schema_rejects_unknown_focus_area(self) -> None:
        valid_focus = Focus(
            area="delivery",
            observation="The delivery was steady.",
            why_it_matters="Delivery affects how the message lands.",
            fix="Practice the opening line three times.",
        )

        payload = {
            "overall": "Overall summary.",
            "strengths": ["One clear strength."],
            "priority_focus": {
                "area": "volume",
                "observation": "Too quiet.",
                "why_it_matters": "Listeners may miss the point.",
                "fix": "Speak louder.",
            },
            "secondary_focuses": [valid_focus.model_dump()],
            "drill_suggestion": "Practice once.",
            "encouragement": "Keep practicing.",
            "generated_by": "mock",
        }

        with self.assertRaises(ValidationError):
            StructuredFeedback.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
