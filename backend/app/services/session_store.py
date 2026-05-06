import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.models.session import AnalysisResult, SessionReport, SessionSummary

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path(__file__).parent.parent.parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)


def build_report(
    session_id: str,
    started_at: datetime,
    ended_at: datetime,
    chunks: list[AnalysisResult],
    full_transcript: str,
) -> SessionReport:
    filler_counts: dict[str, int] = defaultdict(int)
    wpm_values: list[float] = []
    coherence_values: list[float] = []
    coach_notes: list[str] = []
    total_pauses = 0

    for chunk in chunks:
        for fw in chunk.filler_words:
            filler_counts[fw.word] += 1
        wpm_values.append(chunk.speed.current_wpm)
        total_pauses += len(chunk.pauses)
        if chunk.coherence_score is not None:
            coherence_values.append(chunk.coherence_score)
        if chunk.ai_feedback and chunk.ai_feedback not in coach_notes:
            coach_notes.append(chunk.ai_feedback)

    duration = (ended_at - started_at).total_seconds()
    total_words = len(full_transcript.split())

    summary = SessionSummary(
        total_words=total_words,
        avg_wpm=round(sum(wpm_values) / len(wpm_values), 1) if wpm_values else 0.0,
        peak_wpm=round(max(wpm_values), 1) if wpm_values else 0.0,
        filler_counts=dict(sorted(filler_counts.items(), key=lambda x: -x[1])),
        total_pauses=total_pauses,
        avg_coherence=round(sum(coherence_values) / len(coherence_values), 2) if coherence_values else 1.0,
        coach_notes=coach_notes[:5],  # top 5 unique notes
    )

    return SessionReport(
        session_id=session_id,
        started_at=started_at.isoformat(),
        ended_at=ended_at.isoformat(),
        duration_seconds=round(duration, 1),
        full_transcript=full_transcript.strip(),
        chunks=chunks,
        summary=summary,
    )


def save_report(report: SessionReport) -> None:
    path = SESSIONS_DIR / f"{report.session_id}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Saved session report: %s", path)


def load_report(session_id: str) -> SessionReport | None:
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        return SessionReport.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to load report %s: %s", session_id, e)
        return None
