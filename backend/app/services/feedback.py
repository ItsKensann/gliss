"""Post-session structured coaching feedback.

One call per finalized SessionReport. Pluggable via settings.feedback_provider.
The mock backend uses the report's own heuristic metrics to produce realistic
output during development without spending API credits or running a local model.
"""
from __future__ import annotations

import asyncio
import json
import logging
from time import perf_counter
from typing import Protocol

import httpx
from ollama import AsyncClient, ResponseError
from pydantic import ValidationError

from app.core.config import settings
from app.models.session import Focus, FocusArea, SessionReport, StructuredFeedback

logger = logging.getLogger(__name__)

FEEDBACK_VERSION = "v1"

# Thresholds used by the mock to pick what's worth focusing on. These are
# rough rules of thumb that match the heuristic detectors. When we swap in a
# real LLM, the prompt rubric should mirror these same buckets so output across
# providers stays comparable.
FILLER_RATE_HIGH = 0.04      # >4% of words are fillers
FILLER_RATE_LOW = 0.015      # <1.5% is genuinely clean
PACE_FAST_WPM = 170.0
PACE_SLOW_WPM = 110.0
PAUSE_RATE_LOW = 0.5         # pauses per minute below this = few deliberate resets
EYE_CONTACT_LOW = 0.6
EYE_CONTACT_STRONG = 0.8


class FeedbackProvider(Protocol):
    """Generate end-of-session structured coaching feedback.

    Implementations must be async, must not raise on bad input, and must
    return None on failure so the caller can save the report without it.
    """
    async def generate(self, report: SessionReport) -> StructuredFeedback | None: ...


class MockFeedbackProvider:
    """Deterministic heuristic-driven feedback, no LLM, no cost.

    Picks priority + secondary focuses from real metric thresholds. Useful for
    wiring + UI development, and gives an honest baseline of what coaching
    looks like before paying for a real model.
    """

    async def generate(self, report: SessionReport) -> StructuredFeedback:
        summary = report.summary
        duration_min = max(report.duration_seconds / 60.0, 1 / 60)
        word_count = max(summary.total_words, 1)
        filler_total = sum(summary.filler_counts.values())
        filler_rate = filler_total / word_count
        top_filler = next(iter(summary.filler_counts), None)
        pauses_per_min = summary.total_pauses / duration_min

        focuses = _pick_focuses(
            filler_rate=filler_rate,
            filler_total=filler_total,
            top_filler=top_filler,
            avg_wpm=summary.avg_wpm,
            peak_wpm=summary.peak_wpm,
            pauses_per_min=pauses_per_min,
            eye_contact=summary.avg_eye_contact,
            transcript=report.full_transcript,
        )

        if not focuses:
            focuses = [_default_focus()]

        priority = focuses[0]
        secondary = focuses[1:3]

        strengths = _pick_strengths(
            filler_rate=filler_rate,
            avg_wpm=summary.avg_wpm,
            pauses_per_min=pauses_per_min,
            eye_contact=summary.avg_eye_contact,
            word_count=summary.total_words,
            duration_min=duration_min,
        )

        return StructuredFeedback(
            overall=_overall_summary(
                word_count=summary.total_words,
                duration_min=duration_min,
                avg_wpm=summary.avg_wpm,
                priority_area=priority.area,
            ),
            strengths=strengths,
            priority_focus=priority,
            secondary_focuses=secondary,
            drill_suggestion=_drill_for(priority.area),
            encouragement=(
                "One focused practice point is enough for the next session. "
                "Work the priority focus first, then come back for another rep."
            ),
            feedback_version=FEEDBACK_VERSION,
            generated_by="mock",
        )


_OLLAMA_SYSTEM_PROMPT = (
    "You are a concise speech coach. Return valid JSON only."
)


class OllamaFeedbackProvider:
    """Local-LLM-backed coaching feedback via the Ollama HTTP API.

    Falls back to MockFeedbackProvider on any failure (server down, model
    not pulled, malformed JSON, schema validation error) so the user always
    gets some feedback. The fallback result is tagged "mock-fallback" in
    generated_by so the source is traceable.
    """

    def __init__(self, base_url: str, model: str, timeout_seconds: float | None = None) -> None:
        self._timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.ollama_timeout_seconds
        )
        self._client = AsyncClient(
            host=base_url,
            timeout=self._timeout_seconds,
        )
        self._base_url = base_url
        self._model = model
        self._fallback = MockFeedbackProvider()

    async def generate(self, report: SessionReport) -> StructuredFeedback | None:
        started = perf_counter()
        logger.info(
            "Ollama feedback started: provider=ollama model=%s base_url=%s timeout_seconds=%.1f transcript_chars=%d words=%d",
            self._model,
            self._base_url,
            self._timeout_seconds,
            len(report.full_transcript or ""),
            report.summary.total_words,
        )
        try:
            user_msg = self._build_user_message(report)
            resp = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": _OLLAMA_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                format=_ollama_feedback_schema(),
                options={"temperature": 0.2, "num_predict": 160},
            )
            raw = resp["message"]["content"]
            payload = json.loads(raw)
            feedback = self._expand_ollama_payload(payload)
            logger.info(
                "Ollama feedback succeeded: provider=ollama model=%s elapsed_ms=%.1f",
                self._model,
                (perf_counter() - started) * 1000,
            )
            return feedback
        except (
            TimeoutError,
            asyncio.TimeoutError,
            httpx.HTTPError,
            ResponseError,
            ValidationError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            OSError,
        ) as e:
            logger.warning(
                "Ollama feedback falling back: provider=ollama model=%s elapsed_ms=%.1f error_type=%s error=%s",
                self._model,
                (perf_counter() - started) * 1000,
                type(e).__name__,
                e,
            )
        except Exception:
            logger.exception(
                "Unexpected Ollama failure; falling back to mock: provider=ollama model=%s elapsed_ms=%.1f",
                self._model,
                (perf_counter() - started) * 1000,
            )

        fallback = await self._fallback.generate(report)
        if fallback is not None:
            fallback.generated_by = "mock-fallback"
            logger.info(
                "Ollama feedback fallback generated: provider=mock-fallback model=%s elapsed_ms=%.1f",
                self._model,
                (perf_counter() - started) * 1000,
            )
        return fallback

    def _build_user_message(self, report: SessionReport) -> str:
        s = report.summary
        duration_min = max(report.duration_seconds / 60.0, 1 / 60)
        filler_total = sum(s.filler_counts.values())
        filler_rate = filler_total / max(s.total_words, 1)
        pauses_per_min = s.total_pauses / duration_min
        eye = f"{s.avg_eye_contact * 100:.0f}%" if s.avg_eye_contact is not None else "n/a"
        filler_list = ", ".join(f'"{w}" ({n})' for w, n in s.filler_counts.items()) or "none"
        prompt_line = report.prompt or "(no prompt — freestyle)"
        target = (
            f"{report.target_duration_seconds:.0f}s"
            if report.target_duration_seconds else "freestyle (no target)"
        )

        return (
            f"Metrics: {report.duration_seconds:.0f}s target {target}. "
            f"{s.total_words} words. Avg {s.avg_wpm:.0f} WPM, peak {s.peak_wpm:.0f}. "
            f"Fillers {filler_list}, total {filler_total} ({filler_rate * 100:.1f}%). "
            f"Pauses {s.total_pauses} ({pauses_per_min:.1f}/min). Eye contact {eye}. "
            f"Prompt: {prompt_line}. "
            f"Transcript: {report.full_transcript or '(no speech captured)'} "
            "Pick priority_area from fillers, pace, pauses, clarity, structure, "
            "delivery, eye_contact. Keep overall under 25 words. Keep observation "
            "and fix under 15 words."
        )

    def _expand_ollama_payload(self, payload: dict) -> StructuredFeedback:
        priority = _ollama_payload_focus(
            area=payload["priority_area"],
            observation=payload["observation"],
            fix=payload["fix"],
        )
        strengths = _clean_string_list(
            [payload.get("strength")],
            fallback="You completed a practice rep, which gives you something concrete to improve.",
            max_items=1,
        )

        return StructuredFeedback.model_validate({
            "overall": _clean_string(
                payload["overall"],
                "This session gives you a clear next practice target.",
            ),
            "strengths": strengths,
            "priority_focus": priority.model_dump(),
            "secondary_focuses": [],
            "drill_suggestion": _drill_for(priority.area),
            "encouragement": (
                "Use the priority focus for one short rep, then review the next recording."
            ),
            "feedback_version": FEEDBACK_VERSION,
            "generated_by": f"ollama:{self._model}",
        })


def _focus_area_schema() -> dict:
    return {
        "type": "string",
        "enum": [
            "fillers",
            "pace",
            "pauses",
            "clarity",
            "structure",
            "delivery",
            "eye_contact",
        ],
    }


def _ollama_feedback_schema() -> dict:
    area = _focus_area_schema()
    return {
        "type": "object",
        "properties": {
            "overall": {"type": "string", "maxLength": 160},
            "strength": {"type": "string", "maxLength": 90},
            "priority_area": area,
            "observation": {"type": "string", "maxLength": 120},
            "fix": {"type": "string", "maxLength": 120},
        },
        "required": [
            "overall",
            "strength",
            "priority_area",
            "observation",
            "fix",
        ],
    }


def _ollama_payload_focus(*, area: object, observation: object, fix: object) -> Focus:
    return Focus.model_validate({
        "area": area,
        "observation": _clean_string(
            observation,
            "The session shows one pattern worth practicing next.",
        ),
        "why_it_matters": _why_it_matters_for(area),
        "fix": _clean_string(
            fix,
            "Repeat the answer once while focusing on this single adjustment.",
        ),
    })


def _clean_string(value: object, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    text = value.strip()
    return text or fallback


def _clean_string_list(value: object, *, fallback: str, max_items: int) -> list[str]:
    if not isinstance(value, list):
        return [fallback]
    cleaned = [
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    ]
    return cleaned[:max_items] or [fallback]


def _pick_focuses(
    *,
    filler_rate: float,
    filler_total: int,
    top_filler: str | None,
    avg_wpm: float,
    peak_wpm: float,
    pauses_per_min: float,
    eye_contact: float | None,
    transcript: str,
) -> list[Focus]:
    focuses: list[Focus] = []

    if filler_rate >= FILLER_RATE_HIGH and top_filler:
        focuses.append(Focus(
            area="fillers",
            observation=(
                f'"{top_filler}" appeared {filler_total} times, about '
                f"{filler_rate * 100:.0f}% of your words were fillers."
            ),
            why_it_matters=(
                "Fillers are common, but repeated fillers can make it harder to "
                "hear the main point clearly."
            ),
            fix=(
                f'When you feel "{top_filler}" coming, close your mouth and pause '
                "for one beat instead. A short pause gives you time to choose the "
                "next word."
            ),
            excerpt=_excerpt_around(transcript, top_filler),
        ))

    if avg_wpm >= PACE_FAST_WPM or peak_wpm >= PACE_FAST_WPM + 30:
        focuses.append(Focus(
            area="pace",
            observation=(
                f"Average pace was {avg_wpm:.0f} WPM with peaks up to "
                f"{peak_wpm:.0f}. A comfortable practice target is 140-160 WPM."
            ),
            why_it_matters=(
                "When pace climbs, articulation and breathing usually get harder. "
                "Slowing down gives each phrase more room."
            ),
            fix=(
                "Slow your opening sentence by 30%. Once your pace anchors low, "
                "the rest of the practice usually follows."
            ),
        ))
    elif avg_wpm and avg_wpm < PACE_SLOW_WPM:
        focuses.append(Focus(
            area="pace",
            observation=f"Average pace was {avg_wpm:.0f} WPM, which is on the slower side.",
            why_it_matters=(
                "A very slow pace can make connected speech feel less natural. "
                "The goal is steady, comfortable movement from phrase to phrase."
            ),
            fix="Practice the same answer again with a little more energy on the main verbs.",
        ))

    if pauses_per_min < PAUSE_RATE_LOW and avg_wpm and avg_wpm > 100:
        focuses.append(Focus(
            area="pauses",
            observation=(
                f"You paused {pauses_per_min:.1f} times per minute. Most practice "
                "sessions benefit from 1-2 deliberate pauses per minute."
            ),
            why_it_matters=(
                "Pauses support breathing and give you a clean reset before the "
                "next phrase."
            ),
            fix=(
                "Mark 2-3 sentences in your prep that deserve a beat after them. "
                "Practice holding the silence for two full seconds."
            ),
        ))

    if eye_contact is not None and eye_contact < EYE_CONTACT_LOW:
        focuses.append(Focus(
            area="eye_contact",
            observation=(
                f"Eye contact landed around {eye_contact * 100:.0f}%, below the "
                "70%+ range that reads as engaged on camera."
            ),
            why_it_matters=(
                "Looking near the camera helps the practice feel more connected "
                "and makes it easier to review your delivery."
            ),
            fix=(
                "Place a sticky note next to your camera lens and treat it as a "
                "single point to return to between thoughts."
            ),
        ))

    return focuses


def _pick_strengths(
    *,
    filler_rate: float,
    avg_wpm: float,
    pauses_per_min: float,
    eye_contact: float | None,
    word_count: int,
    duration_min: float,
) -> list[str]:
    strengths: list[str] = []
    if filler_rate <= FILLER_RATE_LOW and word_count > 30:
        strengths.append("Filler use stayed low, which kept the message easy to follow.")
    if 130 <= avg_wpm <= 160:
        strengths.append(f"Pace stayed in a comfortable range ({avg_wpm:.0f} WPM).")
    if pauses_per_min >= 1.0:
        strengths.append("You used pauses regularly, which supports breath control.")
    if eye_contact is not None and eye_contact >= EYE_CONTACT_STRONG:
        strengths.append(f"Eye contact was strong ({eye_contact * 100:.0f}%).")
    if duration_min >= 2 and word_count >= 60:
        strengths.append("You sustained continuous speech for the full practice window.")

    if not strengths:
        strengths.append("You completed a practice rep, which gives you something concrete to improve.")
    return strengths[:3]


def _overall_summary(
    *,
    word_count: int,
    duration_min: float,
    avg_wpm: float,
    priority_area: FocusArea,
) -> str:
    area_phrase = {
        "fillers": "the most useful next step is replacing fillers with short pauses",
        "pace": "the most useful next step is practicing a steadier pace",
        "pauses": "the most useful next step is adding deliberate pauses",
        "clarity": "the most useful next step is making the main point easier to follow",
        "structure": "the most useful next step is organizing the answer into clear beats",
        "delivery": "the most useful next step is polishing how key sentences land",
        "eye_contact": "the most useful next step is returning your eyes toward the camera",
    }[priority_area]
    if word_count == 0:
        return (
            "This session did not capture enough speech for detailed feedback. "
            f"For the next run, {area_phrase}."
        )
    return (
        f"You delivered {word_count} words over {duration_min:.1f} minutes "
        f"at {avg_wpm:.0f} WPM. Right now, {area_phrase}."
    )


def _why_it_matters_for(area: FocusArea) -> str:
    return {
        "fillers": "Fillers can blur the main point when they repeat in key moments.",
        "pace": "Pace shapes how easily listeners can follow and absorb the answer.",
        "pauses": "Pauses give the listener time to process and give you a clean reset.",
        "clarity": "Clear wording makes the answer easier to remember after the session.",
        "structure": "Structure helps the listener track the point, evidence, and takeaway.",
        "delivery": "Delivery affects how confident and intentional the message feels.",
        "eye_contact": "Camera contact makes the delivery feel more direct and connected.",
    }[area]


def _drill_for(area: FocusArea) -> str:
    return {
        "fillers": (
            "Record a 60-second take answering the same prompt. Every time you "
            "feel a filler, freeze for a full second instead. Run this 3 times."
        ),
        "pace": (
            "Read a paragraph aloud at three speeds: 100 WPM, 140 WPM, 180 WPM. "
            "Notice how 140 feels, then use that as your target."
        ),
        "pauses": (
            "Take your talk script and mark exactly 3 spots with [PAUSE]. "
            "Re-record and hold each one for two full seconds."
        ),
        "clarity": (
            "Write the single sentence that captures your point. Open with it. "
            "Close with it. Practice 3 takes."
        ),
        "structure": (
            "Outline your next take as Point, Evidence, Implication. Three "
            "beats, nothing else."
        ),
        "delivery": (
            "Record one take focused only on landing the first and last sentence. "
            "Keep the middle simple and steady."
        ),
        "eye_contact": (
            "Tape a small mark right above your camera. Practice 90 seconds "
            "where your eyes return to that mark between thoughts."
        ),
    }[area]


def _default_focus() -> Focus:
    return Focus(
        area="delivery",
        observation="The core metrics look steady, so no single area needs urgent attention.",
        why_it_matters=(
            "When the basics are in place, the next gain comes from polish: "
            "landing your opener, your closer, and the transitions in between."
        ),
        fix=(
            "Pick the one sentence in your talk you most want someone to remember "
            "and rehearse just that line three different ways."
        ),
    )


def _excerpt_around(transcript: str, target: str) -> str | None:
    if not transcript or not target:
        return None
    lowered = transcript.lower()
    index = lowered.find(target.lower())
    if index == -1:
        return None
    start = max(0, index - 40)
    end = min(len(transcript), index + len(target) + 40)
    excerpt = transcript[start:end].strip()
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(transcript) else ""
    return f"{prefix}{excerpt}{suffix}"


def get_feedback_provider() -> FeedbackProvider:
    """Resolve the configured provider. Add new branches here as we wire them."""
    name = settings.feedback_provider.lower()
    if name == "mock":
        return MockFeedbackProvider()
    if name == "ollama":
        return OllamaFeedbackProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )
    raise ValueError(
        f"Unknown feedback_provider: {settings.feedback_provider!r}. "
        f"Supported: mock, ollama"
    )
