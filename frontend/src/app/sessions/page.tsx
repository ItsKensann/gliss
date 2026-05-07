"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import type { SessionListItem } from "@/lib/types"

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionListItem[] | null>(null)
  const [error, setError] = useState(false)
  const [confirmingClear, setConfirmingClear] = useState(false)

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/v1/sessions`)
      if (!res.ok) {
        setError(true)
        return
      }
      setSessions(await res.json())
    } catch {
      setError(true)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const deleteOne = async (id: string) => {
    setSessions((prev) => prev?.filter((s) => s.session_id !== id) ?? null)
    try {
      await fetch(`${API}/api/v1/sessions/${id}`, { method: "DELETE" })
    } catch {
      load()
    }
  }

  const clearAll = async () => {
    setSessions([])
    setConfirmingClear(false)
    try {
      await fetch(`${API}/api/v1/sessions`, { method: "DELETE" })
    } catch {
      load()
    }
  }

  return (
    <main className="min-h-screen py-12 px-4">
      <div className="max-w-3xl mx-auto space-y-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Past sessions</h1>
            <p className="text-gray-400 mt-1 text-sm">
              {sessions === null
                ? "Loading…"
                : sessions.length === 0
                ? "No saved sessions yet."
                : `${sessions.length} saved session${sessions.length === 1 ? "" : "s"}`}
            </p>
          </div>
          <Link
            href="/"
            className="px-4 py-2 rounded-xl bg-gray-800/70 hover:bg-gray-700/70 text-sm font-medium text-gray-200 transition-colors shrink-0"
          >
            ← Back
          </Link>
        </div>

        {error && (
          <p className="text-sm text-red-400">Could not load sessions.</p>
        )}

        {sessions && sessions.length > 0 && (
          <>
            <div className="space-y-2">
              {sessions.map((s) => (
                <div
                  key={s.session_id}
                  className="flex items-center gap-3 bg-gray-800/50 rounded-xl ring-1 ring-white/5 px-4 py-3"
                >
                  <Link
                    href={`/report/${s.session_id}`}
                    className="flex-1 min-w-0 group"
                  >
                    <div className="flex items-baseline gap-3">
                      <p className="text-sm font-medium text-white group-hover:text-indigo-300 transition-colors">
                        {formatDate(s.started_at)}
                      </p>
                      <p className="text-xs text-gray-500 tabular-nums shrink-0">
                        {formatDuration(s.duration_seconds)} · {s.total_words.toLocaleString()} words
                      </p>
                    </div>
                    {s.prompt && (
                      <p className="text-xs text-gray-400 italic truncate mt-0.5">
                        &ldquo;{s.prompt}&rdquo;
                      </p>
                    )}
                  </Link>
                  <button
                    onClick={() => deleteOne(s.session_id)}
                    className="text-gray-500 hover:text-red-400 transition-colors p-1 shrink-0"
                    aria-label="Delete session"
                    title="Delete session"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="w-4 h-4">
                      <path d="M3 6h18" />
                      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>

            <div className="border-t border-white/10 pt-6 flex items-center justify-end gap-3">
              {confirmingClear ? (
                <>
                  <span className="text-sm text-gray-400">Delete all {sessions.length}?</span>
                  <button
                    onClick={() => setConfirmingClear(false)}
                    className="px-3 py-1.5 rounded-lg text-sm text-gray-300 hover:bg-gray-800 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={clearAll}
                    className="px-3 py-1.5 rounded-lg text-sm font-medium bg-red-500/80 hover:bg-red-500 text-white transition-colors"
                  >
                    Yes, clear all
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setConfirmingClear(true)}
                  className="px-3 py-1.5 rounded-lg text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                >
                  Clear all sessions
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </main>
  )
}
