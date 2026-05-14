import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes import session as session_route
from app.models.session import SessionReport, SessionSummary


def make_report() -> SessionReport:
    return SessionReport(
        session_id="finalization-test",
        started_at="2026-05-11T12:00:00+00:00",
        ended_at="2026-05-11T12:01:00+00:00",
        duration_seconds=60.0,
        full_transcript="This is a short transcript for finalization tests.",
        chunks=[],
        summary=SessionSummary(
            total_words=8,
            avg_wpm=120.0,
            peak_wpm=130.0,
            filler_counts={},
            total_pauses=1,
        ),
        is_finalized=True,
    )


class HangingFeedbackProvider:
    async def generate(self, report: SessionReport):
        await asyncio.Event().wait()


class FailingFeedbackProvider:
    async def generate(self, report: SessionReport):
        raise RuntimeError("provider failed")


class SessionFinalizationFeedbackTest(unittest.IsolatedAsyncioTestCase):
    async def test_feedback_generation_timeout_does_not_hang_finalization(self) -> None:
        report = make_report()

        await session_route._attach_structured_feedback(
            session_id=report.session_id,
            report=report,
            feedback_provider=HangingFeedbackProvider(),
            timeout_seconds=0.01,
        )

        self.assertIsNone(report.structured_feedback)

    async def test_finalized_report_can_be_saved_when_feedback_generation_fails(self) -> None:
        report = make_report()

        with (
            patch.object(session_route, "save_report") as save_report,
            patch.object(session_route.progress, "update"),
        ):
            await session_route._save_finalized_report(
                session_id=report.session_id,
                report=report,
                feedback_provider=FailingFeedbackProvider(),
                timeout_seconds=0.01,
            )

        save_report.assert_called_once_with(report)
        saved_report = save_report.call_args.args[0]
        self.assertTrue(saved_report.is_finalized)
        self.assertIsNone(saved_report.structured_feedback)


if __name__ == "__main__":
    unittest.main()
