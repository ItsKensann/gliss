import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.session import (
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
        "strength": "The answer stayed focused on the prompt.",
        "priority_area": "fillers",
        "observation": '"um" appeared often enough to become noticeable.',
        "fix": 'When "um" comes up, pause for one beat before continuing.',
    }


class OllamaFeedbackProviderTest(unittest.IsolatedAsyncioTestCase):
    def test_ollama_provider_passes_timeout_to_async_client(self) -> None:
        with patch.object(feedback_module, "AsyncClient") as client_cls:
            OllamaFeedbackProvider(
                base_url="http://localhost:11434",
                model="llama3:latest",
                timeout_seconds=12.5,
            )

        client_cls.assert_called_once_with(
            host="http://localhost:11434",
            timeout=12.5,
        )

    def test_get_feedback_provider_returns_ollama_provider_from_settings(self) -> None:
        with (
            patch.object(feedback_module.settings, "feedback_provider", "ollama"),
            patch.object(feedback_module.settings, "ollama_base_url", "http://localhost:11434"),
            patch.object(feedback_module.settings, "ollama_model", "llama3:latest"),
            patch.object(feedback_module.settings, "ollama_timeout_seconds", 12.5),
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
        self.assertEqual(
            result.priority_focus.why_it_matters,
            "Fillers can blur the main point when they repeat in key moments.",
        )
        self.assertEqual(
            result.drill_suggestion,
            feedback_module._drill_for(result.priority_focus.area),
        )
        self.assertEqual(result.secondary_focuses, [])
        provider._client.chat.assert_awaited_once()
        _, kwargs = provider._client.chat.call_args
        self.assertEqual(kwargs["model"], "llama3:latest")
        self.assertEqual(kwargs["options"], {"temperature": 0.2, "num_predict": 160})
        self.assertIn("format", kwargs)
        self.assertNotIn("generated_by", kwargs["format"]["properties"])
        self.assertNotIn("feedback_version", kwargs["format"]["properties"])
        self.assertNotIn("drill_suggestion", kwargs["format"]["properties"])
        self.assertNotIn("encouragement", kwargs["format"]["properties"])
        self.assertNotIn("priority_focus", kwargs["format"]["properties"])
        self.assertIn("priority_area", kwargs["format"]["properties"])

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

    async def test_ollama_timeout_falls_back_to_mock_feedback(self) -> None:
        provider = OllamaFeedbackProvider(
            base_url="http://localhost:11434",
            model="llama3:latest",
        )
        provider._client.chat = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await provider.generate(make_report())

        self.assertIsNotNone(result)
        self.assertEqual(result.generated_by, "mock-fallback")

    async def test_invalid_ollama_json_falls_back_to_mock_feedback(self) -> None:
        provider = OllamaFeedbackProvider(
            base_url="http://localhost:11434",
            model="llama3:latest",
        )
        provider._client.chat = AsyncMock(return_value={
            "message": {"content": "not json"}
        })

        result = await provider.generate(make_report())

        self.assertIsNotNone(result)
        self.assertEqual(result.generated_by, "mock-fallback")

    async def test_ollama_schema_validation_error_falls_back_to_mock_feedback(self) -> None:
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
