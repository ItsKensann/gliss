"use client"

import Link from "next/link"
import { Suspense } from "react"
import { useSearchParams } from "next/navigation"
import { Recorder } from "@/components/session/Recorder"
import { getPrompt } from "@/lib/prompts"

function SessionPageInner() {
  const searchParams = useSearchParams()
  const durationParam = searchParams.get("duration")
  const durationSec = durationParam ? Number(durationParam) : null
  const validDuration = durationSec !== null && Number.isFinite(durationSec) && durationSec > 0
    ? durationSec
    : null

  const promptId = searchParams.get("promptId")
  const prompt = getPrompt(promptId)?.text

  const withCamera = searchParams.get("camera") !== "off"

  return (
    <main className="min-h-screen py-10 px-4">
      <div className="max-w-3xl mx-auto">
        <Link
          href="/practice"
          className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200 transition-colors mb-6"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
            <path fillRule="evenodd" d="M12.79 5.23a.75.75 0 0 1-.02 1.06L8.832 10l3.938 3.71a.75.75 0 1 1-1.04 1.08l-4.5-4.25a.75.75 0 0 1 0-1.08l4.5-4.25a.75.75 0 0 1 1.06.02z" clipRule="evenodd" />
          </svg>
          Back
        </Link>
        <div className="mb-8">
          <h1 className="text-2xl font-bold">Practice Session</h1>
          <p className="text-gray-400 mt-1">Speak naturally — you&apos;ll get real-time feedback as you go</p>
        </div>
        <Recorder durationSec={validDuration} prompt={prompt} withCamera={withCamera} />
      </div>
    </main>
  )
}

export default function SessionPage() {
  return (
    <Suspense fallback={null}>
      <SessionPageInner />
    </Suspense>
  )
}
