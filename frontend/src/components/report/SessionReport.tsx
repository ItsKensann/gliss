"use client"

import Link from "next/link"
import type { Focus, FocusArea, SessionReportData, StructuredFeedback } from "@/lib/types"
import { SpikeTimeline } from "./SpikeTimeline"

const FOCUS_AREA_LABEL: Record<FocusArea, string> = {
  fillers: "Filler words",
  pace: "Pace",
  pauses: "Pauses",
  clarity: "Clarity",
  structure: "Structure",
  delivery: "Delivery",
  eye_contact: "Eye contact",
}

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

function FocusCard({ focus, tone }: { focus: Focus; tone: "priority" | "secondary" }) {
  const styles =
    tone === "priority"
      ? "bg-purple-500/10 border-purple-400/30 ring-1 ring-purple-400/20"
      : "bg-gray-800/40 border-white/10"
  return (
    <div className={`rounded-xl border px-5 py-4 ${styles}`}>
      <div className="flex items-center gap-2 mb-2">
        <span
          className={`text-[10px] uppercase tracking-widest font-semibold ${
            tone === "priority" ? "text-purple-300" : "text-gray-400"
          }`}
        >
          {tone === "priority" ? "Priority" : "Also worth working on"}
        </span>
        <span className="text-xs text-gray-500">·</span>
        <span className="text-xs text-gray-400">{FOCUS_AREA_LABEL[focus.area]}</span>
      </div>
      <p className="text-sm text-white leading-relaxed">{focus.observation}</p>
      <p className="text-xs text-gray-400 mt-2 leading-relaxed">{focus.why_it_matters}</p>
      <div className="mt-3 pl-3 border-l-2 border-purple-400/40">
        <p className="text-xs uppercase tracking-widest text-purple-300/70 mb-1">Fix</p>
        <p className="text-sm text-purple-100 leading-relaxed">{focus.fix}</p>
      </div>
      {focus.excerpt && (
        <p className="mt-3 text-xs text-gray-500 italic">"{focus.excerpt}"</p>
      )}
    </div>
  )
}

function CoachFeedback({
  feedback,
  isFinalized,
}: {
  feedback: StructuredFeedback | null
  isFinalized: boolean
}) {
  if (!feedback) {
    if (!isFinalized) {
      return (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400">
            Coach feedback
          </h2>
          <div className="bg-gray-800/40 rounded-xl px-5 py-4 ring-1 ring-white/5 flex items-center gap-3">
            <div className="w-3 h-3 rounded-full border-2 border-purple-400/50 border-t-transparent animate-spin" />
            <p className="text-sm text-gray-400">Generating coach feedback…</p>
          </div>
        </section>
      )
    }
    return (
      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400">
          Coach feedback
        </h2>
        <div className="bg-gray-800/40 rounded-xl px-5 py-4 ring-1 ring-white/5">
          <p className="text-sm text-gray-400">
            Coach feedback is not available for this session.
          </p>
        </div>
      </section>
    )
  }

  return (
    <section className="space-y-4">
      <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400">
        Coach feedback
      </h2>

      <p className="text-base text-gray-200 leading-relaxed">{feedback.overall}</p>

      {feedback.strengths.length > 0 && (
        <div className="bg-emerald-500/5 border border-emerald-400/20 rounded-xl px-5 py-4">
          <p className="text-xs uppercase tracking-widest text-emerald-300/80 mb-2">
            What worked
          </p>
          <ul className="space-y-1.5 text-sm text-emerald-100/90">
            {feedback.strengths.map((s, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-emerald-400">·</span>
                <span className="leading-relaxed">{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <FocusCard focus={feedback.priority_focus} tone="priority" />

      {feedback.secondary_focuses.map((f, i) => (
        <FocusCard key={i} focus={f} tone="secondary" />
      ))}

      <div className="bg-indigo-500/10 border border-indigo-400/30 rounded-xl px-5 py-4">
        <p className="text-xs uppercase tracking-widest text-indigo-300/80 mb-2">
          Try this next
        </p>
        <p className="text-sm text-indigo-100 leading-relaxed">{feedback.drill_suggestion}</p>
      </div>

      <p className="text-sm text-gray-400 italic leading-relaxed">{feedback.encouragement}</p>

      <p className="text-[10px] text-gray-600 uppercase tracking-widest">
        Generated by {feedback.generated_by} · {feedback.feedback_version}
      </p>
    </section>
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
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
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
          <SpikeTimeline
            chunks={report.chunks}
            paceEvents={report.pace_events ?? []}
            durationSeconds={report.duration_seconds}
          />
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

        <CoachFeedback
          feedback={report.structured_feedback ?? null}
          isFinalized={report.is_finalized !== false}
        />

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
