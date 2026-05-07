"use client"

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
    <main className="min-h-screen py-12 px-4">
      <div className="max-w-3xl mx-auto">
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
