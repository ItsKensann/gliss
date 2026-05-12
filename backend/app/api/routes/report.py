from fastapi import APIRouter, HTTPException, Response

from app.core import progress
from app.models.session import FinalizationProgress, SessionListItem, SessionReport
from app.services.session_store import (
    delete_all_sessions,
    delete_session,
    list_sessions,
    load_report,
)

router = APIRouter()


@router.get("/report/{session_id}", response_model=SessionReport)
async def get_report(session_id: str, response: Response):
    response.headers["Cache-Control"] = "no-store"
    report = load_report(session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return report


@router.get("/report/{session_id}/progress", response_model=FinalizationProgress)
async def get_report_progress(session_id: str, response: Response):
    response.headers["Cache-Control"] = "no-store"
    entry = progress.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="No finalization in flight")
    return entry


@router.get("/sessions", response_model=list[SessionListItem])
async def get_sessions():
    return list_sessions()


@router.delete("/sessions")
async def clear_sessions():
    count = delete_all_sessions()
    return {"deleted": count}


@router.delete("/sessions/{session_id}")
async def remove_session(session_id: str):
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": 1}
