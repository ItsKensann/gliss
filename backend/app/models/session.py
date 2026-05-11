from pydantic import BaseModel, Field
from typing import Literal, Optional


class FillerWord(BaseModel):
    word: str
    timestamp: float
    count: int = 1


class Pause(BaseModel):
    start: float
    end: float
    duration: float


class SpeedAnalysis(BaseModel):
    current_wpm: float
    baseline_wpm: float
    is_spike: bool
    spike_factor: float


class PaceEvent(BaseModel):
    type: Literal["fast"] = "fast"
    start_seconds: float
    end_seconds: float
    wpm: float
    baseline_wpm: float
    spike_factor: float
    excerpt: str


class FaceMetrics(BaseModel):
    eye_contact_score: float
    head_stability: float
    face_visible: bool = True
    timestamp: float


class BreathAdvice(BaseModel):
    should_pause: bool
    suggested_pause_location: Optional[str] = None
    reason: Optional[str] = None


class ImmediateFeedback(BaseModel):
    message: str
    type: str
    severity: str


class AnalysisResult(BaseModel):
    transcript: str
    filler_words: list[FillerWord]
    speed: SpeedAnalysis
    pauses: list[Pause]
    breath_advice: Optional[BreathAdvice] = None
    immediate_feedback: list[ImmediateFeedback]
    coherence_score: Optional[float] = None
    ai_feedback: Optional[str] = None
    start_offset_seconds: float = 0.0
    end_offset_seconds: float = 0.0
    # Snapshot of the latest face metrics at the time this chunk was built.
    # None when no face was visible (or camera was off) — distinguishes
    # "absent data" from "zero score" so the report can ignore it.
    avg_eye_contact: Optional[float] = None
    avg_head_stability: Optional[float] = None


class SessionSummary(BaseModel):
    total_words: int
    avg_wpm: float
    peak_wpm: float
    filler_counts: dict[str, int]       # word → total occurrences
    total_pauses: int
    avg_coherence: float
    coach_notes: list[str]              # ai_feedback messages, deduplicated
    avg_eye_contact: Optional[float] = None
    avg_head_stability: Optional[float] = None


class SessionListItem(BaseModel):
    """Brief metadata for the past-sessions list — avoids shipping every chunk."""
    session_id: str
    started_at: str
    duration_seconds: float
    total_words: int
    prompt: Optional[str] = None


class SessionReport(BaseModel):
    session_id: str
    started_at: str                     # ISO-8601
    ended_at: str
    duration_seconds: float
    full_transcript: str
    chunks: list[AnalysisResult]
    pace_events: list[PaceEvent] = Field(default_factory=list)
    summary: SessionSummary
    prompt: Optional[str] = None
    target_duration_seconds: Optional[float] = None
    # False while the backend is still finishing the final transcription
    # cycle that captures trailing audio. The report file is saved twice:
    # once preliminary (is_finalized=False) so the user can see results
    # immediately, then again with is_finalized=True after the trailing
    # cycle completes. Frontend keeps polling until True.
    is_finalized: bool = True
