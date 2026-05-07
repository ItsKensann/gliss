from fastapi import APIRouter, HTTPException

from app.models.session import SessionListItem, SessionReport
from app.services.session_store import (
    delete_all_sessions,
    delete_session,
    list_sessions,
    load_report,
)

router = APIRouter()


@router.get("/report/{session_id}", response_model=SessionReport)
async def get_report(session_id: str):
    report = load_report(session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return report


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
