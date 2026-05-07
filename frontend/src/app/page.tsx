"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import {
  CATEGORIES,
  PromptCategory,
  getPrompt,
  promptsInCategory,
  randomPromptInCategory,
} from "@/lib/prompts"

const DURATION_OPTIONS: Array<{ label: string; sec: number | null }> = [
  { label: "1m", sec: 60 },
  { label: "3m", sec: 180 },
  { label: "5m", sec: 300 },
  { label: "10m", sec: 600 },
  { label: "Freestyle", sec: null },
]

const DURATION_KEY = "gliss:lastDuration"
const PROMPT_KEY = "gliss:lastPromptId"
const CATEGORY_KEY = "gliss:lastCategory"
const CAMERA_KEY = "gliss:lastCamera"

export default function Home() {
  const [durationSec, setDurationSec] = useState<number | null>(180)
  const [promptId, setPromptId] = useState<string | null>(null)
  const [category, setCategory] = useState<PromptCategory>("Interview")
  const [withCamera, setWithCamera] = useState<boolean>(true)

  useEffect(() => {
    const savedDur = localStorage.getItem(DURATION_KEY)
    if (savedDur !== null) setDurationSec(savedDur === "null" ? null : Number(savedDur))
    const savedPrompt = localStorage.getItem(PROMPT_KEY)
    if (savedPrompt !== null) setPromptId(savedPrompt === "null" ? null : savedPrompt)
    const savedCat = localStorage.getItem(CATEGORY_KEY) as PromptCategory | null
    if (savedCat && CATEGORIES.includes(savedCat)) setCategory(savedCat)
    const savedCam = localStorage.getItem(CAMERA_KEY)
    if (savedCam !== null) setWithCamera(savedCam === "true")
  }, [])

  const chooseDuration = (sec: number | null) => {
    setDurationSec(sec)
    localStorage.setItem(DURATION_KEY, sec === null ? "null" : String(sec))
  }

  const choosePrompt = (id: string | null) => {
    setPromptId(id)
    localStorage.setItem(PROMPT_KEY, id === null ? "null" : id)
  }

  const chooseCategory = (cat: PromptCategory) => {
    setCategory(cat)
    localStorage.setItem(CATEGORY_KEY, cat)
    // Switching to a category implies the user wants a prompt from it.
    // Auto-pick the first one so the prompt list becomes visible.
    if (promptId === null || getPrompt(promptId)?.category !== cat) {
      const first = promptsInCategory(cat)[0]
      if (first) choosePrompt(first.id)
    }
  }

  const surpriseMe = () => {
    const p = randomPromptInCategory(category)
    choosePrompt(p.id)
  }

  const chooseCamera = (on: boolean) => {
    setWithCamera(on)
    localStorage.setItem(CAMERA_KEY, on ? "true" : "false")
  }

  const promptsForCategory = useMemo(() => promptsInCategory(category), [category])
  const selectedPrompt = getPrompt(promptId)

  const isPreset = (sec: number | null) =>
    sec === null || DURATION_OPTIONS.some((o) => o.sec === sec)

  const isCustomSelected = durationSec !== null && !isPreset(durationSec)
  const customMinValue = isCustomSelected && durationSec !== null ? String(Math.round(durationSec / 60)) : ""

  const onCustomChange = (raw: string) => {
    if (raw === "") {
      // Clear custom — fall back to the first preset so a duration is still active.
      chooseDuration(DURATION_OPTIONS[0].sec)
      return
    }
    const n = Number(raw)
    if (!Number.isFinite(n) || n <= 0) return
    const clamped = Math.min(120, Math.max(1, Math.round(n)))
    chooseDuration(clamped * 60)
  }

  const startHref = (() => {
    const params = new URLSearchParams()
    if (durationSec !== null) params.set("duration", String(durationSec))
    if (promptId !== null) params.set("promptId", promptId)
    if (!withCamera) params.set("camera", "off")
    const qs = params.toString()
    return qs ? `/session?${qs}` : "/session"
  })()

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 py-12">
      <div className="text-center max-w-2xl w-full">
        <h1 className="text-7xl font-bold tracking-tight mb-4 bg-gradient-to-br from-white to-gray-400 bg-clip-text text-transparent">
          gliss
        </h1>
        <p className="text-xl text-gray-400 mb-3">Real-time speech coaching powered by AI</p>
        <p className="text-gray-500 mb-10 max-w-md mx-auto leading-relaxed">
          Get live feedback on filler words, pacing, eye contact, and clarity — as you speak.
        </p>

        <div className="mb-8">
          <p className="text-xs uppercase tracking-widest text-gray-500 mb-3">Session length</p>
          <div className="flex flex-wrap justify-center gap-2 mb-3">
            {DURATION_OPTIONS.map((opt) => {
              const selected = opt.sec === durationSec
              return (
                <button
                  key={opt.label}
                  onClick={() => chooseDuration(opt.sec)}
                  className={`px-4 py-2 rounded-full text-sm font-medium border transition-colors ${
                    selected
                      ? "bg-indigo-500/20 border-indigo-400/60 text-indigo-200"
                      : "bg-gray-800/40 border-white/10 text-gray-400 hover:bg-gray-700/50 hover:text-gray-200"
                  }`}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>
          <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
            <span>or custom</span>
            <input
              type="number"
              min={1}
              max={120}
              step={1}
              inputMode="numeric"
              value={customMinValue}
              onChange={(e) => onCustomChange(e.target.value)}
              placeholder="—"
              className={`w-16 px-2 py-1 rounded-lg bg-gray-800/60 border text-center tabular-nums focus:outline-none focus:ring-1 transition-colors ${
                isCustomSelected
                  ? "border-indigo-400/60 text-indigo-200 ring-indigo-400/40"
                  : "border-white/10 text-gray-300 focus:border-indigo-400/40 focus:ring-indigo-400/30"
              }`}
            />
            <span>min</span>
          </div>
        </div>

        <div className="mb-8">
          <p className="text-xs uppercase tracking-widest text-gray-500 mb-3">Camera</p>
          <div className="flex flex-wrap justify-center gap-2">
            {[
              { label: "On", value: true },
              { label: "Audio only", value: false },
            ].map((opt) => {
              const selected = opt.value === withCamera
              return (
                <button
                  key={opt.label}
                  onClick={() => chooseCamera(opt.value)}
                  className={`px-4 py-2 rounded-full text-sm font-medium border transition-colors ${
                    selected
                      ? "bg-indigo-500/20 border-indigo-400/60 text-indigo-200"
                      : "bg-gray-800/40 border-white/10 text-gray-400 hover:bg-gray-700/50 hover:text-gray-200"
                  }`}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>
        </div>

        <div className="mb-10 text-left">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs uppercase tracking-widest text-gray-500">Prompt</p>
            <button
              onClick={surpriseMe}
              className="text-xs text-indigo-300 hover:text-indigo-200 transition-colors"
            >
              Surprise me →
            </button>
          </div>

          <div className="flex flex-wrap gap-2 mb-3">
            <button
              onClick={() => choosePrompt(null)}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                promptId === null
                  ? "bg-gray-700 border-gray-500 text-white"
                  : "bg-gray-800/40 border-white/10 text-gray-400 hover:text-gray-200"
              }`}
            >
              Freestyle
            </button>
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => chooseCategory(cat)}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                  category === cat && promptId !== null
                    ? "bg-indigo-500/20 border-indigo-400/60 text-indigo-200"
                    : "bg-gray-800/40 border-white/10 text-gray-400 hover:text-gray-200"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {promptId !== null && (
            <div className="space-y-1.5">
              {promptsForCategory.map((p) => {
                const selected = p.id === promptId
                return (
                  <button
                    key={p.id}
                    onClick={() => choosePrompt(p.id)}
                    className={`block w-full text-left px-4 py-3 rounded-xl text-sm border transition-colors ${
                      selected
                        ? "bg-indigo-500/15 border-indigo-400/50 text-indigo-100"
                        : "bg-gray-800/40 border-white/10 text-gray-300 hover:bg-gray-700/40"
                    }`}
                  >
                    {p.text}
                  </button>
                )
              })}
            </div>
          )}

          {selectedPrompt && (
            <p className="text-xs text-gray-500 mt-3 italic">
              You&apos;ll see this prompt during your session.
            </p>
          )}
        </div>

        <Link
          href={startHref}
          className="inline-block bg-indigo-500 hover:bg-indigo-600 active:scale-95 text-white px-8 py-4 rounded-2xl font-semibold text-lg transition-all duration-200"
        >
          Start practicing
        </Link>

        <div className="mt-8">
          <Link
            href="/sessions"
            className="text-sm text-gray-500 hover:text-gray-300 transition-colors"
          >
            Past sessions →
          </Link>
        </div>
      </div>
    </main>
  )
}
