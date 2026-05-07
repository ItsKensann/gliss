"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { SessionReport } from "@/components/report/SessionReport"
import type { SessionReportData } from "@/lib/types"

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export default function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const [report, setReport] = useState<SessionReportData | null>(null)
  const [error, setError] = useState(false)
  const [attempts, setAttempts] = useState(0)

  useEffect(() => {
    if (!id) return

    const load = async () => {
      try {
        const res = await fetch(`${API}/api/v1/report/${id}`)
        if (res.status === 404 && attempts < 60) {
          // Backend may still be finishing Whisper + saving — retry for up to 30s.
          // Tight 500ms interval so the report renders within ~half a second of
          // the file landing, not up to two seconds later.
          setTimeout(() => setAttempts((n) => n + 1), 500)
          return
        }
        if (!res.ok) { setError(true); return }
        const data: SessionReportData = await res.json()
        setReport(data)
        // Backend writes a preliminary report (is_finalized=false) so the user
        // sees results immediately, then re-saves once the final transcription
        // cycle picks up trailing audio. Keep polling until the finalized
        // version lands so trailing words appear without a manual refresh.
        if (data.is_finalized === false && attempts < 60) {
          setTimeout(() => setAttempts((n) => n + 1), 1500)
        }
      } catch {
        setError(true)
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
    const isSlowSave = attempts > 20
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
