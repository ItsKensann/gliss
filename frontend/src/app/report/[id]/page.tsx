"use client"

import { useEffect, useRef, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { SessionReport } from "@/components/report/SessionReport"
import type { SessionReportData } from "@/lib/types"

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
const REPORT_POLL_INTERVAL_MS = 1000
const SLOW_REPORT_ATTEMPTS = 20
const MAX_REPORT_FAILURES = 5

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

export default function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const [report, setReport] = useState<SessionReportData | null>(null)
  const [error, setError] = useState(false)
  const [attempts, setAttempts] = useState(0)
  const failuresRef = useRef(0)

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
        if (data.is_finalized === false) {
          console.debug("[Gliss report] waiting for finalized report", {
            session_id: id,
            attempt: attempts,
          })
          setTimeout(() => setAttempts((n) => n + 1), REPORT_POLL_INTERVAL_MS)
          return
        }
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

  if (error) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center gap-4 text-center">
        <p className="text-gray-400">Could not load session report.</p>
        <Link href="/session" className="text-indigo-400 hover:underline">Start a new session</Link>
      </main>
    )
  }

  if (!report) {
    const isSlowSave = attempts > SLOW_REPORT_ATTEMPTS
    return (
      <main className="min-h-screen flex flex-col items-center justify-center gap-2">
        <div className="flex items-center gap-3 text-gray-400">
          <div className="w-4 h-4 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" />
          {isSlowSave ? "Still processing your session…" : "Generating your report…"}
        </div>
        {isSlowSave && (
          <p className="text-xs text-gray-600">Whisper is finishing transcription, hang tight</p>
        )}
      </main>
    )
  }

  return <SessionReport report={report} />
}
