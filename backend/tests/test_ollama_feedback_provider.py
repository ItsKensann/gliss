import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.session import (
    Focus,
    SessionReport,
    SessionSummary,
)
from app.services import feedback as feedback_module
from app.services.feedback import OllamaFeedbackProvider


def make_report() -> SessionReport:
    return SessionReport(
        session_id="ollama-test",
        started_at="2026-05-11T12:00:00+00:00",
        ended_at="2026-05-11T12:01:00+00:00",
        duration_seconds=60.0,
        full_transcript="I think um this answer needs a clearer structure.",
        chunks=[],
        summary=SessionSummary(
            total_words=100,
            avg_wpm=145.0,
            peak_wpm=160.0,
            filler_counts={"um": 5},
            total_pauses=1,
            avg_eye_contact=0.72,
        ),
        prompt="Tell me about a project you led.",
        target_duration_seconds=180.0,
    )


def make_feedback_payload() -> dict:
    return {
        "overall": "You delivered a clear practice answer with one visible filler pattern.",
        "strengths": [
            "The answer stayed focused on the prompt.",
            "Your pace stayed in a comfortable range.",
        ],
        "priority_focus": Focus(
            area="fillers",
            observation='"um" appeared often enough to become noticeable.',
            why_it_matters="Repeated fillers can make the main point harder to follow.",
            fix='When "um" comes up, pause for one beat before continuing.',
            excerpt="I think um this answer",
        ).model_dump(),
        "secondary_focuses": [
            Focus(
                area="structure",
                observation="The answer would benefit from clearer signposts.",
                why_it_matters="Signposts make the listener's job easier.",
                fix="Open with the result, then explain the process.",
            ).model_dump()
        ],
        "drill_suggestion": "Record the same answer with one planned pause after the first sentence.",
        "encouragement": "Keep the next rep focused on replacing fillers with silence.",
    }


class OllamaFeedbackProviderTest(unittest.IsolatedAsyncioTestCase):
    def test_get_feedback_provider_returns_ollama_provider_from_settings(self) -> None:
        with (
            patch.object(feedback_module.settings, "feedback_provider", "ollama"),
            patch.object(feedback_module.settings, "ollama_base_url", "http://localhost:11434"),
            patch.object(feedback_module.settings, "ollama_model", "llama3:latest"),
        ):
            provider = feedback_module.get_feedback_provider()

        self.assertIsInstance(provider, OllamaFeedbackProvider)

    async def test_ollama_success_path_parses_structured_feedback(self) -> None:
        provider = OllamaFeedbackProvider(
            base_url="http://localhost:11434",
            model="llama3:latest",
        )
        provider._client.chat = AsyncMock(return_value={
            "message": {"content": json.dumps(make_feedback_payload())}
        })

        result = await provider.generate(make_report())

        self.assertIsNotNone(result)
        self.assertEqual(result.generated_by, "ollama:llama3:latest")
        self.assertEqual(result.priority_focus.area, "fillers")
        provider._client.chat.assert_awaited_once()
        _, kwargs = provider._client.chat.call_args
        self.assertEqual(kwargs["model"], "llama3:latest")
        self.assertIn("format", kwargs)
        self.assertNotIn("generated_by", kwargs["format"]["properties"])
        self.assertNotIn("feedback_version", kwargs["format"]["properties"])

    async def test_ollama_failure_falls_back_to_mock_feedback(self) -> None:
        provider = OllamaFeedbackProvider(
            base_url="http://localhost:11434",
            model="llama3:latest",
        )
        provider._client.chat = AsyncMock(side_effect=OSError("ollama unavailable"))

        result = await provider.generate(make_report())

        self.assertIsNotNone(result)
        self.assertEqual(result.generated_by, "mock-fallback")
        self.assertEqual(result.priority_focus.area, "fillers")

    async def test_invalid_ollama_json_falls_back_to_mock_feedback(self) -> None:
        provider = OllamaFeedbackProvider(
            base_url="http://localhost:11434",
            model="llama3:latest",
        )
        provider._client.chat = AsyncMock(return_value={
            "message": {"content": '{"overall": "missing required fields"}'}
        })

        result = await provider.generate(make_report())

        self.assertIsNotNone(result)
        self.assertEqual(result.generated_by, "mock-fallback")


if __name__ == "__main__":
    unittest.main()
