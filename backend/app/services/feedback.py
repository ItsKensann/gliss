"""Post-session structured coaching feedback.

One call per finalized SessionReport. Pluggable via settings.feedback_provider —
the mock backend uses the report's own heuristic metrics to produce realistic
output during development without spending API credits or running a local model.
"""
from __future__ import annotations

import logging
from typing import Protocol

from app.core.config import settings
from app.models.session import Focus, FocusArea, SessionReport, StructuredFeedback

logger = logging.getLogger(__name__)

FEEDBACK_VERSION = "v1"

# Thresholds used by the mock to pick what's worth focusing on. These are
# rough rules of thumb that match the heuristic detectors — when we swap in a
# real LLM, the prompt rubric will mirror these same buckets so output across
# providers stays comparable.
FILLER_RATE_HIGH = 0.04      # >4% of words are fillers
FILLER_RATE_LOW = 0.015      # <1.5% is genuinely clean
PACE_FAST_WPM = 170.0
PACE_SLOW_WPM = 110.0
PAUSE_RATE_LOW = 0.5         # pauses per minute below this = monotone
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
                "One run at a time — pick the priority focus, work it for a "
                "session or two, then move on. You're building this."
            ),
            feedback_version=FEEDBACK_VERSION,
            generated_by="mock",
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
                f'"{top_filler}" appeared {filler_total} times — about '
                f"{filler_rate * 100:.0f}% of your words were fillers."
            ),
            why_it_matters=(
                "Fillers leak certainty. Listeners pick up on them faster than you "
                "do, and they make even good ideas sound tentative."
            ),
            fix=(
                f'When you feel "{top_filler}" coming, close your mouth and pause '
                "for a beat instead. The silence reads as confidence."
            ),
            excerpt=_excerpt_around(transcript, top_filler),
        ))

    if avg_wpm >= PACE_FAST_WPM or peak_wpm >= PACE_FAST_WPM + 30:
        focuses.append(Focus(
            area="pace",
            observation=(
                f"Average pace was {avg_wpm:.0f} WPM with peaks up to "
                f"{peak_wpm:.0f} — most listeners absorb best around 140–160."
            ),
            why_it_matters=(
                "Fast pace compresses your ideas. The audience misses the part "
                "you most want them to remember."
            ),
            fix=(
                "Slow your opening sentence by 30%. Once your pace anchors low, "
                "the rest of the talk tends to follow."
            ),
        ))
    elif avg_wpm and avg_wpm < PACE_SLOW_WPM:
        focuses.append(Focus(
            area="pace",
            observation=f"Average pace was {avg_wpm:.0f} WPM — on the slow side of conversational.",
            why_it_matters=(
                "Too slow and you lose momentum; the audience starts predicting "
                "your sentences instead of listening."
            ),
            fix="Lift energy on the verbs. Aim for 130–150 WPM as a comfortable target.",
        ))

    if pauses_per_min < PAUSE_RATE_LOW and avg_wpm and avg_wpm > 100:
        focuses.append(Focus(
            area="pauses",
            observation=(
                f"You paused {pauses_per_min:.1f} times per minute — most strong "
                "speakers land 1–2 deliberate pauses per minute."
            ),
            why_it_matters=(
                "Pauses are where ideas land. Without them everything blurs into "
                "one continuous block."
            ),
            fix=(
                "Mark 2–3 sentences in your prep that deserve a beat after them. "
                "Practice holding the silence for two full seconds."
            ),
        ))

    if eye_contact is not None and eye_contact < EYE_CONTACT_LOW:
        focuses.append(Focus(
            area="eye_contact",
            observation=(
                f"Eye contact landed around {eye_contact * 100:.0f}% — well below "
                "the 70%+ range that reads as engaged."
            ),
            why_it_matters=(
                "Eye contact is the fastest way to build trust on camera. Low "
                "contact makes even strong content feel uncertain."
            ),
            fix=(
                "Place a sticky note next to your camera lens and treat it as a "
                "single audience member you're speaking to."
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
        strengths.append("Filler use was notably low — your speech sounded clean.")
    if 130 <= avg_wpm <= 160:
        strengths.append(f"Pace stayed in the sweet spot ({avg_wpm:.0f} WPM).")
    if pauses_per_min >= 1.0:
        strengths.append("Used pauses deliberately — that gives your ideas room to land.")
    if eye_contact is not None and eye_contact >= EYE_CONTACT_STRONG:
        strengths.append(f"Eye contact was strong ({eye_contact * 100:.0f}%).")
    if duration_min >= 2 and word_count >= 60:
        strengths.append("Sustained continuous speech without bailing — that's the hardest part.")

    if not strengths:
        strengths.append("You showed up and ran a full session — that's the rep that compounds.")
    return strengths[:3]


def _overall_summary(
    *,
    word_count: int,
    duration_min: float,
    avg_wpm: float,
    priority_area: FocusArea,
) -> str:
    area_phrase = {
        "fillers": "filler use is the highest-leverage thing to clean up",
        "pace": "your pace is the biggest lever for the next session",
        "pauses": "adding deliberate pauses will be the biggest unlock",
        "clarity": "clarity is the main thing to sharpen",
        "structure": "structure is what to focus on next",
        "delivery": "delivery is what to push on",
        "eye_contact": "eye contact is the most visible improvement to make",
    }[priority_area]
    return (
        f"You delivered {word_count} words over {duration_min:.1f} minutes "
        f"at {avg_wpm:.0f} WPM. Right now {area_phrase} — see the focus below "
        f"for the specific move."
    )


def _drill_for(area: FocusArea) -> str:
    return {
        "fillers": (
            "Record a 60-second take answering the same prompt. Every time you "
            "feel a filler, freeze for a full second instead. Run this 3 times."
        ),
        "pace": (
            "Read a paragraph aloud at three speeds: 100 WPM, 140 WPM, 180 WPM. "
            "Notice how 140 feels — that's your target."
        ),
        "pauses": (
            "Take your talk script and mark exactly 3 spots with [PAUSE]. "
            "Re-record and hold each one for two full Mississippi-counts."
        ),
        "clarity": (
            "Write the single sentence that captures your point. Open with it. "
            "Close with it. Practice 3 takes."
        ),
        "structure": (
            "Outline your next take as Point → Evidence → Implication. Three "
            "beats, nothing else."
        ),
        "delivery": (
            "Record one take focused only on landing the first and last sentence. "
            "The middle takes care of itself."
        ),
        "eye_contact": (
            "Tape a small mark right above your camera. Practice 90 seconds "
            "where your eyes never drift more than 6 inches from it."
        ),
    }[area]


def _default_focus() -> Focus:
    return Focus(
        area="delivery",
        observation="Metrics look reasonable — no single area is screaming for attention.",
        why_it_matters=(
            "When the basics are in place, the next gain comes from polish: "
            "landing your opener, your closer, and the transitions in between."
        ),
        fix=(
            "Pick the one sentence in your talk you most want the audience to "
            "remember and rehearse just that line three different ways."
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
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(transcript) else ""
    return f"{prefix}{excerpt}{suffix}"


def get_feedback_provider() -> FeedbackProvider:
    """Resolve the configured provider. Add new branches here as we wire them."""
    name = settings.feedback_provider.lower()
    if name == "mock":
        return MockFeedbackProvider()
    raise ValueError(
        f"Unknown feedback_provider: {settings.feedback_provider!r}. "
        f"Supported: mock"
    )
