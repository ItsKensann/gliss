"""Post-session structured coaching feedback.

One call per finalized SessionReport. Pluggable via settings.feedback_provider.
The mock backend uses the report's own heuristic metrics to produce realistic
output during development without spending API credits or running a local model.
"""
from __future__ import annotations

import json
import logging
from typing import Protocol

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
    "You are a friendly, specific speech coach. The user just finished a "
    "practice recording. Produce concise, actionable feedback grounded ONLY "
    "in the transcript and metrics provided — never invent facts the user "
    "did not say. Pick ONE priority_focus and 1-2 secondary_focuses from: "
    "fillers, pace, pauses, clarity, structure, delivery, eye_contact. "
    "Be encouraging but honest. Quote a short transcript excerpt in a focus "
    "when it makes the observation concrete; otherwise omit the excerpt."
)

_OLLAMA_HEURISTIC_REFERENCE = (
    "Reference thresholds (for calibration, not rigid rules): "
    "filler rate >4% is high, <1.5% is clean. "
    "WPM 170+ is fast, <110 is slow, 140-160 is comfortable. "
    "Pauses/min <0.5 is sparse, 1-2 is balanced. "
    "Eye contact <60% is low, >=80% is strong."
)


class OllamaFeedbackProvider:
    """Local-LLM-backed coaching feedback via the Ollama HTTP API.

    Falls back to MockFeedbackProvider on any failure (server down, model
    not pulled, malformed JSON, schema validation error) so the user always
    gets some feedback. The fallback result is tagged "mock-fallback" in
    generated_by so the source is traceable.
    """

    def __init__(self, base_url: str, model: str) -> None:
        self._client = AsyncClient(host=base_url)
        self._model = model
        self._fallback = MockFeedbackProvider()

    async def generate(self, report: SessionReport) -> StructuredFeedback | None:
        try:
            user_msg = self._build_user_message(report)
            schema = StructuredFeedback.model_json_schema()
            resp = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": _OLLAMA_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                format=schema,
                options={"temperature": 0.4},
            )
            raw = resp["message"]["content"]
            feedback = StructuredFeedback.model_validate_json(raw)
            feedback.generated_by = f"ollama:{self._model}"
            return feedback
        except (ResponseError, ValidationError, json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Ollama feedback failed (%s: %s); falling back to mock",
                type(e).__name__, e,
            )
        except Exception:
            logger.exception("Unexpected Ollama failure; falling back to mock")

        fallback = await self._fallback.generate(report)
        if fallback is not None:
            fallback.generated_by = "mock-fallback"
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
            "SESSION METRICS\n"
            f"- Duration: {report.duration_seconds:.0f}s (target: {target})\n"
            f"- Words spoken: {s.total_words}\n"
            f"- Pace: avg {s.avg_wpm:.0f} WPM, peak {s.peak_wpm:.0f} WPM\n"
            f"- Fillers: {filler_list}, total {filler_total} ({filler_rate * 100:.1f}% of words)\n"
            f"- Pauses (>1.5s): {s.total_pauses} ({pauses_per_min:.1f}/min)\n"
            f"- Eye contact: {eye}\n\n"
            f"PROMPT THE USER ANSWERED:\n{prompt_line}\n\n"
            f"FULL TRANSCRIPT:\n{report.full_transcript or '(no speech captured)'}\n\n"
            f"{_OLLAMA_HEURISTIC_REFERENCE}\n\n"
            "Return JSON matching the provided schema. Keep overall to 2-3 sentences, "
            "strengths to 2-3 short items, and each focus's fix to one concrete action."
        )


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
        )
    raise ValueError(
        f"Unknown feedback_provider: {settings.feedback_provider!r}. "
        f"Supported: mock, ollama"
    )
