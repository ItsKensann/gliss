"""In-memory finalization progress store.

Touched from both the asyncio event loop (session handler) and the Whisper
executor thread, so all access is guarded by a single threading.Lock. Lock is
held only around dict access — no I/O, no async — to keep updates effectively
free relative to the Whisper compute they're tracking.
"""

import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from app.models.session import FinalizationProgress, FinalizationStage

logger = logging.getLogger(__name__)

_TTL_SECONDS = 600.0

_lock = Lock()
_store: dict[str, FinalizationProgress] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _purge_stale_locked() -> None:
    if not _store:
        return
    cutoff = _now().timestamp() - _TTL_SECONDS
    stale = [sid for sid, entry in _store.items() if entry.updated_at.timestamp() < cutoff]
    for sid in stale:
        _store.pop(sid, None)


def update(session_id: str, stage: FinalizationStage, percent: float) -> None:
    try:
        clamped = max(0.0, min(100.0, float(percent)))
        entry = FinalizationProgress(stage=stage, percent=clamped, updated_at=_now())
        with _lock:
            _purge_stale_locked()
            _store[session_id] = entry
    except Exception:
        logger.exception("progress.update failed for session %s", session_id)


def complete(session_id: str) -> None:
    update(session_id, "done", 100.0)


def get(session_id: str) -> Optional[FinalizationProgress]:
    with _lock:
        _purge_stale_locked()
        return _store.get(session_id)


def clear(session_id: str) -> None:
    with _lock:
        _store.pop(session_id, None)
