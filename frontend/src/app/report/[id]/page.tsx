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
        if (res.status === 404 && attempts < 20) {
          // Backend may still be finishing Whisper + saving — retry for up to 40s
          setTimeout(() => setAttempts((n) => n + 1), 2000)
          return
        }
        if (!res.ok) { setError(true); return }
        setReport(await res.json())
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
    const isSlowSave = attempts > 5
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
