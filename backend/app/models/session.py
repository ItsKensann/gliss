from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal, Optional


FinalizationStage = Literal[
    "analysis_shutdown",
    "preliminary_save",
    "live_buffer_pass",
    "full_pass_whisper",
    "pause_detection",
    "chunk_rebuild",
    "feedback_generation",
    "finalized_save",
    "done",
]


class FinalizationProgress(BaseModel):
    stage: FinalizationStage
    percent: float
    updated_at: datetime


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
    avg_eye_contact: Optional[float] = None
    avg_head_stability: Optional[float] = None


FocusArea = Literal[
    "fillers", "pace", "pauses", "clarity", "structure", "delivery", "eye_contact"
]


class Focus(BaseModel):
    """One concrete thing to work on, grounded in a metric or excerpt."""
    area: FocusArea
    observation: str            # what the LLM noticed
    why_it_matters: str         # why this hurts the talk
    fix: str                    # one specific action
    excerpt: Optional[str] = None  # transcript quote where it showed up


class StructuredFeedback(BaseModel):
    """End-of-session coaching output. One per finalized report."""
    overall: str                        # 2-3 sentence summary
    strengths: list[str]                # 2-3 concrete strengths
    priority_focus: Focus               # the ONE thing to work on next
    secondary_focuses: list[Focus]      # 1-2 more, lower priority
    drill_suggestion: str               # one concrete practice exercise
    encouragement: str                  # short, personalized close
    feedback_version: str = "v1"        # bump to re-run on old sessions
    generated_by: str                   # "mock", "claude-sonnet-4-6", "ollama:qwen2.5:7b", etc.


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
    # Populated on the finalized save by the configured FeedbackProvider.
    # Preliminary saves leave this None; UI shows a "generating feedback…"
    # placeholder until is_finalized=True arrives.
    structured_feedback: Optional[StructuredFeedback] = None
