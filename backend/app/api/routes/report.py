from fastapi import APIRouter, HTTPException

from app.models.session import SessionReport
from app.services.session_store import load_report

router = APIRouter()


@router.get("/report/{session_id}", response_model=SessionReport)
async def get_report(session_id: str):
    report = load_report(session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return report
