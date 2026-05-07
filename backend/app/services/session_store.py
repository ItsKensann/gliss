import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.models.session import AnalysisResult, SessionListItem, SessionReport, SessionSummary

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path(__file__).parent.parent.parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)


def build_report(
    session_id: str,
    started_at: datetime,
    ended_at: datetime,
    chunks: list[AnalysisResult],
    full_transcript: str,
    prompt: str | None = None,
    target_duration_seconds: float | None = None,
    is_finalized: bool = True,
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
        prompt=prompt,
        target_duration_seconds=target_duration_seconds,
        is_finalized=is_finalized,
    )


def save_report(report: SessionReport) -> None:
    path = SESSIONS_DIR / f"{report.session_id}.json"
    # Write to a temp file then rename — keeps the visible file always complete,
    # since we save twice (preliminary + finalized) and concurrent GET requests
    # poll throughout.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)
    logger.info("Saved session report: %s (finalized=%s)", path, report.is_finalized)


def load_report(session_id: str) -> SessionReport | None:
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        return SessionReport.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to load report %s: %s", session_id, e)
        return None


def list_sessions() -> list[SessionListItem]:
    """Return brief metadata for every saved session, newest first."""
    items: list[SessionListItem] = []
    for path in SESSIONS_DIR.glob("*.json"):
        report = load_report(path.stem)
        if report is None:
            continue
        items.append(SessionListItem(
            session_id=report.session_id,
            started_at=report.started_at,
            duration_seconds=report.duration_seconds,
            total_words=report.summary.total_words,
            prompt=report.prompt,
        ))
    items.sort(key=lambda x: x.started_at, reverse=True)
    return items


def delete_session(session_id: str) -> bool:
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return False
    path.unlink()
    logger.info("Deleted session %s", session_id)
    return True


def delete_all_sessions() -> int:
    count = 0
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            path.unlink()
            count += 1
        except OSError as e:
            logger.warning("Failed to delete %s: %s", path, e)
    logger.info("Cleared all sessions (%d deleted)", count)
    return count
