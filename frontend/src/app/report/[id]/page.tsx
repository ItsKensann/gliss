"use client"

import { useEffect, useRef, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { SessionReport } from "@/components/report/SessionReport"
import { FinalizationProgress } from "@/components/session/FinalizationProgress"
import {
  useFinalizationProgress,
  type FinalizationStage,
} from "@/hooks/useFinalizationProgress"
import { finalizationStorageKey, type FinalizationHandoff } from "@/hooks/useSession"
import type { SessionReportData } from "@/lib/types"

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
const REPORT_POLL_INTERVAL_MS = 1000
const PROGRESS_POLL_INTERVAL_MS = 500
const MAX_REPORT_FAILURES = 5

type BackendStage =
  | "analysis_shutdown"
  | "preliminary_save"
  | "live_buffer_pass"
  | "full_pass_whisper"
  | "pause_detection"
  | "chunk_rebuild"
  | "feedback_generation"
  | "finalized_save"
  | "done"

interface BackendProgressPayload {
  stage: BackendStage
  percent: number
  updated_at: string
}

function mapBackendStage(stage: BackendStage): FinalizationStage {
  switch (stage) {
    case "analysis_shutdown":
    case "preliminary_save":
      return "wrapping"
    case "live_buffer_pass":
    case "full_pass_whisper":
    case "pause_detection":
    case "chunk_rebuild":
      return "transcribing"
    case "feedback_generation":
    case "finalized_save":
    case "done":
      return "finalizing"
  }
}

function reportDebugStats(report: SessionReportData) {
  const fillerCounts = report.summary.filler_counts
  return {
    is_finalized: report.is_finalized ?? true,
    chunks: report.chunks.length,
    words: report.summary.total_words,
    filler_counts: fillerCounts,
    total_fillers: Object.values(fillerCounts).reduce((sum, count) => sum + count, 0),
    total_pauses: report.summary.total_pauses,
    avg_wpm: report.summary.avg_wpm,
    peak_wpm: report.summary.peak_wpm,
  }
}

function readHandoff(sessionId: string): FinalizationHandoff | null {
  if (typeof window === "undefined") return null
  try {
    const raw = sessionStorage.getItem(finalizationStorageKey(sessionId))
    if (!raw) return null
    return JSON.parse(raw) as FinalizationHandoff
  } catch {
    return null
  }
}

export default function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const [report, setReport] = useState<SessionReportData | null>(null)
  const [error, setError] = useState(false)
  const [attempts, setAttempts] = useState(0)
  const [gotPreliminary, setGotPreliminary] = useState(false)
  const [gotFinalized, setGotFinalized] = useState(false)
  const [handoff, setHandoff] = useState<FinalizationHandoff | null>(null)
  const [backendProgress, setBackendProgress] = useState<{
    percent: number
    stage: FinalizationStage
  } | null>(null)
  const failuresRef = useRef(0)

  useEffect(() => {
    if (!id) return
    const stored = readHandoff(id)
    setHandoff(stored ?? { startedAt: Date.now(), recordingDurationMs: null })
  }, [id])

  useEffect(() => {
    if (!id) return
    if (!gotFinalized) return
    if (typeof window === "undefined") return
    try {
      sessionStorage.removeItem(finalizationStorageKey(id))
    } catch {
      // ignore
    }
  }, [id, gotFinalized])

  useEffect(() => {
    if (!id) return

    const load = async () => {
      const requestedAt = performance.now()
      console.debug("[Gliss report] fetch start", {
        session_id: id,
        attempt: attempts,
        timestamp: new Date().toISOString(),
      })
      try {
        const res = await fetch(`${API}/api/v1/report/${id}?poll=${Date.now()}`, {
          cache: "no-store",
        })
        console.debug("[Gliss report] fetch response", {
          session_id: id,
          attempt: attempts,
          status: res.status,
          elapsed_ms: Math.round(performance.now() - requestedAt),
        })
        if (res.status === 404) {
          failuresRef.current = 0
          setTimeout(() => setAttempts((n) => n + 1), REPORT_POLL_INTERVAL_MS)
          return
        }
        if (!res.ok) {
          console.debug("[Gliss report] fetch failed", {
            session_id: id,
            attempt: attempts,
            status: res.status,
          })
          failuresRef.current += 1
          if (failuresRef.current >= MAX_REPORT_FAILURES) {
            setError(true)
            return
          }
          setTimeout(() => setAttempts((n) => n + 1), REPORT_POLL_INTERVAL_MS)
          return
        }
        failuresRef.current = 0
        const data: SessionReportData = await res.json()
        console.debug("[Gliss report] payload", {
          session_id: id,
          attempt: attempts,
          elapsed_ms: Math.round(performance.now() - requestedAt),
          stats: reportDebugStats(data),
        })
        setGotPreliminary(true)
        if (data.is_finalized === false) {
          console.debug("[Gliss report] waiting for finalized report", {
            session_id: id,
            attempt: attempts,
          })
          setTimeout(() => setAttempts((n) => n + 1), REPORT_POLL_INTERVAL_MS)
          return
        }
        setGotFinalized(true)
        setReport(data)
      } catch (error) {
        console.debug("[Gliss report] fetch error", {
          session_id: id,
          attempt: attempts,
          error,
        })
        failuresRef.current += 1
        if (failuresRef.current >= MAX_REPORT_FAILURES) {
          setError(true)
          return
        }
        setTimeout(() => setAttempts((n) => n + 1), REPORT_POLL_INTERVAL_MS)
      }
    }

    load()
  }, [id, attempts])

  useEffect(() => {
    if (!id) return
    if (gotFinalized) return

    let cancelled = false
    let timeoutId: ReturnType<typeof setTimeout> | null = null

    const tick = async () => {
      if (cancelled) return
      try {
        const res = await fetch(
          `${API}/api/v1/report/${id}/progress?poll=${Date.now()}`,
          { cache: "no-store" },
        )
        if (!cancelled && res.ok) {
          const data = (await res.json()) as BackendProgressPayload
          setBackendProgress({
            percent: data.percent,
            stage: mapBackendStage(data.stage),
          })
        }
      } catch {
        // Network errors during polling are non-fatal; the heuristic
        // fallback covers the gap.
      }
      if (!cancelled) {
        timeoutId = setTimeout(tick, PROGRESS_POLL_INTERVAL_MS)
      }
    }

    tick()
    return () => {
      cancelled = true
      if (timeoutId !== null) clearTimeout(timeoutId)
    }
  }, [id, gotFinalized])

  const progress = useFinalizationProgress({
    startedAt: handoff?.startedAt ?? null,
    recordingDurationMs: handoff?.recordingDurationMs ?? null,
    gotPreliminary,
    gotFinalized,
    backendPercent: backendProgress?.percent ?? null,
    backendStage: backendProgress?.stage ?? null,
  })

  if (error) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center gap-4 text-center">
        <p className="text-gray-400">Could not load session report.</p>
        <Link href="/session" className="text-indigo-400 hover:underline">Start a new session</Link>
      </main>
    )
  }

  if (!report) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center px-6">
        <FinalizationProgress
          percent={progress.percent}
          stage={progress.stage}
          slow={progress.slow}
          variant="page"
        />
      </main>
    )
  }

  return <SessionReport report={report} />
}
