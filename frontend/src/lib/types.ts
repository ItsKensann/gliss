export interface FillerWord {
  word: string
  timestamp: number
  count: number
}

export interface Pause {
  start: number
  end: number
  duration: number
}

export interface SpeedAnalysis {
  current_wpm: number
  baseline_wpm: number
  is_spike: boolean
  spike_factor: number
}

export interface PaceEvent {
  type: "fast"
  start_seconds: number
  end_seconds: number
  wpm: number
  baseline_wpm: number
  spike_factor: number
  excerpt: string
}

export interface BreathAdvice {
  should_pause: boolean
  suggested_pause_location?: string
  reason?: string
}

export interface ImmediateFeedback {
  message: string
  type: "speed" | "filler" | "posture" | "breath" | "rambling"
  severity: "info" | "warning" | "critical"
}

export interface AnalysisResult {
  transcript: string
  filler_words: FillerWord[]
  speed: SpeedAnalysis
  pauses: Pause[]
  breath_advice?: BreathAdvice
  immediate_feedback: ImmediateFeedback[]
  start_offset_seconds?: number
  end_offset_seconds?: number
  avg_eye_contact?: number | null
  avg_head_stability?: number | null
}

export type FocusArea =
  | "fillers"
  | "pace"
  | "pauses"
  | "clarity"
  | "structure"
  | "delivery"
  | "eye_contact"

export interface Focus {
  area: FocusArea
  observation: string
  why_it_matters: string
  fix: string
  excerpt?: string | null
}

export interface StructuredFeedback {
  overall: string
  strengths: string[]
  priority_focus: Focus
  secondary_focuses: Focus[]
  drill_suggestion: string
  encouragement: string
  feedback_version: string
  generated_by: string
}

export interface FaceMetrics {
  type: "metrics"
  eye_contact_score: number
  head_stability: number
  face_visible: boolean
  timestamp: number
}

export interface SessionState {
  isRecording: boolean
  isConnected: boolean
  latestAnalysis: AnalysisResult | null
  transcript: string
  sessionId: string | null
}

export interface SessionSummary {
  total_words: number
  avg_wpm: number
  peak_wpm: number
  filler_counts: Record<string, number>
  total_pauses: number
  avg_eye_contact?: number | null
  avg_head_stability?: number | null
}

export interface SessionListItem {
  session_id: string
  started_at: string
  duration_seconds: number
  total_words: number
  prompt?: string
}

export interface SessionReportData {
  session_id: string
  started_at: string
  ended_at: string
  duration_seconds: number
  full_transcript: string
  chunks: AnalysisResult[]
  pace_events: PaceEvent[]
  summary: SessionSummary
  prompt?: string
  target_duration_seconds?: number
  is_finalized?: boolean
  structured_feedback?: StructuredFeedback | null
}
