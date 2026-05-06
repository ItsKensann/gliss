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
  coherence_score?: number
  ai_feedback?: string
}

export interface FaceMetrics {
  type: "metrics"
  eye_contact_score: number
  head_stability: number
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
  avg_coherence: number
  coach_notes: string[]
}

export interface SessionReportData {
  session_id: string
  started_at: string
  ended_at: string
  duration_seconds: number
  full_transcript: string
  chunks: AnalysisResult[]
  summary: SessionSummary
}
