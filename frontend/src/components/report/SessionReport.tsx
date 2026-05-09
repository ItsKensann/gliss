"use client"

import Link from "next/link"
import type { SessionReportData } from "@/lib/types"
import { SpikeTimeline } from "./SpikeTimeline"

interface Props {
  report: SessionReportData
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function ReportNav() {
  return (
    <nav className="flex items-center gap-5 text-sm text-gray-400 mb-2">
      <Link href="/" className="hover:text-gray-200 transition-colors">
        Home
      </Link>
      <Link href="/session" className="hover:text-gray-200 transition-colors">
        New session
      </Link>
    </nav>
  )
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-gray-800/50 rounded-xl p-5 ring-1 ring-white/5">
      <p className="text-xs text-gray-500 uppercase tracking-widest mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  )
}

export function SessionReport({ report }: Props) {
  const { summary } = report
  const fillerEntries = Object.entries(summary.filler_counts)
  const totalFillers = fillerEntries.reduce((sum, [, n]) => sum + n, 0)
  const maxFillerCount = Math.max(...fillerEntries.map(([, n]) => n), 1)

  // Session ended before any speech was captured (user bailed out early to retry).
  if (report.chunks.length === 0 && summary.total_words === 0) {
    return (
      <main className="min-h-screen py-10 px-4">
        <div className="max-w-3xl mx-auto">
          <ReportNav />
          <div className="flex flex-col items-center justify-center gap-4 text-center mt-16">
            <h1 className="text-xl font-semibold">No audio captured</h1>
            <p className="text-gray-400 text-sm max-w-sm">
              The session ended before we could record anything to analyze. Give it another go.
            </p>
            <Link
              href="/practice"
              className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-sm font-medium transition-colors"
            >
              Practice again
            </Link>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen py-10 px-4">
      <div className="max-w-3xl mx-auto space-y-8">

        <ReportNav />

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Session Report</h1>
            <p className="text-gray-400 mt-1 text-sm">
              {new Date(report.started_at).toLocaleDateString("en-US", {
                weekday: "long", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
              })}
            </p>
            {report.is_finalized === false && (
              <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
                <div className="w-3 h-3 rounded-full border-2 border-indigo-400/50 border-t-transparent animate-spin" />
                <span>Finalizing transcript…</span>
              </div>
            )}
          </div>
          <Link
            href="/practice"
            className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-sm font-medium transition-colors shrink-0"
          >
            Practice again
          </Link>
        </div>

        {/* Prompt */}
        {report.prompt && (
          <blockquote className="border-l-2 border-indigo-400/40 pl-4 py-1">
            <p className="text-xs uppercase tracking-widest text-indigo-300/70 mb-1">Prompt</p>
            <p className="text-indigo-100 italic">{report.prompt}</p>
          </blockquote>
        )}

        {/* Stats grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <StatCard
            label="Duration"
            value={formatDuration(report.duration_seconds)}
            sub={
              report.target_duration_seconds
                ? `Goal: ${formatDuration(report.target_duration_seconds)}`
                : undefined
            }
          />
          <StatCard label="Words spoken" value={summary.total_words.toLocaleString()} />
          <StatCard
            label="Avg pace"
            value={`${summary.avg_wpm} WPM`}
            sub={`Peak ${summary.peak_wpm} WPM`}
          />
          <StatCard
            label="Coherence"
            value={`${Math.round(summary.avg_coherence * 100)}%`}
            sub={summary.avg_coherence >= 0.75 ? "Good focus" : "Needs work"}
          />
          <StatCard
            label="Eye contact"
            value={
              summary.avg_eye_contact != null
                ? `${Math.round(summary.avg_eye_contact * 100)}%`
                : "—"
            }
            sub={
              summary.avg_eye_contact == null
                ? "No camera data"
                : summary.avg_eye_contact >= 0.7
                ? "Strong"
                : "Practice"
            }
          />
        </div>

        {/* Timeline */}
        {report.chunks.length > 0 && (
          <SpikeTimeline chunks={report.chunks} durationSeconds={report.duration_seconds} />
        )}

        {/* Filler words */}
        {fillerEntries.length > 0 && (
          <section className="bg-gray-800/50 rounded-xl p-5 ring-1 ring-white/5">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-4">
              Filler words — {totalFillers} total
            </h2>
            <div className="space-y-2">
              {fillerEntries.map(([word, count]) => (
                <div key={word} className="flex items-center gap-3">
                  <span className="text-sm text-gray-300 w-24 shrink-0">"{word}"</span>
                  <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-amber-500/70 rounded-full"
                      style={{ width: `${(count / maxFillerCount) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-400 w-6 text-right shrink-0">×{count}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Coach notes */}
        {summary.coach_notes.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400">
              Coach feedback
            </h2>
            {summary.coach_notes.map((note, i) => (
              <div
                key={i}
                className="bg-purple-500/10 border border-purple-400/20 rounded-xl px-5 py-4 text-purple-200 text-sm leading-relaxed"
              >
                {note}
              </div>
            ))}
          </section>
        )}

        {/* Transcript */}
        {report.full_transcript && (
          <section className="bg-gray-800/50 rounded-xl p-5 ring-1 ring-white/5">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-3">
              Transcript
            </h2>
            <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">
              {report.full_transcript}
            </p>
          </section>
        )}

      </div>
    </main>
  )
}
