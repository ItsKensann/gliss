"use client"

import Link from "next/link"
import { useEffect, useMemo, useRef, useState } from "react"
import {
  CATEGORIES,
  PromptCategory,
  getPrompt,
  promptsInCategory,
  randomPromptInCategory,
} from "@/lib/prompts"

const DURATION_OPTIONS = [
  { value: "60", label: "1 minute" },
  { value: "180", label: "3 minutes" },
  { value: "300", label: "5 minutes" },
  { value: "600", label: "10 minutes" },
  { value: "freestyle", label: "Freestyle (no limit)" },
  { value: "custom", label: "Custom…" },
]

const PRESET_SECONDS = new Set([60, 180, 300, 600])

const DURATION_KEY = "gliss:lastDuration"
const PROMPT_KEY = "gliss:lastPromptId"
const CATEGORY_KEY = "gliss:lastCategory"
const CAMERA_KEY = "gliss:lastCamera"

export default function PracticePage() {
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

  const isCustomDuration = durationSec !== null && !PRESET_SECONDS.has(durationSec)
  const selectValue =
    durationSec === null ? "freestyle" : isCustomDuration ? "custom" : String(durationSec)

  const customMinRef = useRef<HTMLInputElement>(null)

  const onDurationChange = (val: string) => {
    if (val === "freestyle") {
      chooseDuration(null)
    } else if (val === "custom") {
      // Pick a non-preset default so the dropdown stays on "Custom…", then
      // focus the minutes field so the user can type their value immediately.
      if (!isCustomDuration) chooseDuration(90)
      requestAnimationFrame(() => customMinRef.current?.select())
    } else {
      chooseDuration(Number(val))
    }
  }

  const customMin = isCustomDuration && durationSec !== null ? Math.floor(durationSec / 60) : 1
  const customSec = isCustomDuration && durationSec !== null ? durationSec % 60 : 30

  const parseField = (raw: string, max: number) => {
    if (raw === "") return 0
    const n = Number(raw)
    if (!Number.isFinite(n)) return 0
    return Math.max(0, Math.min(max, Math.round(n)))
  }

  const onCustomMinChange = (raw: string) => {
    chooseDuration(parseField(raw, 120) * 60 + customSec)
  }
  const onCustomSecChange = (raw: string) => {
    chooseDuration(customMin * 60 + parseField(raw, 59))
  }

  const isStartDisabled = isCustomDuration && durationSec === 0

  const startHref = (() => {
    const params = new URLSearchParams()
    if (durationSec !== null) params.set("duration", String(durationSec))
    if (promptId !== null) params.set("promptId", promptId)
    if (!withCamera) params.set("camera", "off")
    const qs = params.toString()
    return qs ? `/session?${qs}` : "/session"
  })()

  return (
    <main className="min-h-screen px-4 py-10">
      <div className="max-w-xl mx-auto">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200 transition-colors mb-8"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
            <path fillRule="evenodd" d="M12.79 5.23a.75.75 0 0 1-.02 1.06L8.832 10l3.938 3.71a.75.75 0 1 1-1.04 1.08l-4.5-4.25a.75.75 0 0 1 0-1.08l4.5-4.25a.75.75 0 0 1 1.06.02z" clipRule="evenodd" />
          </svg>
          Back
        </Link>

        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight">New session</h1>
          <p className="text-gray-400 mt-2 text-sm">Configure your run, then start speaking.</p>
        </header>

        <section className="rounded-2xl bg-gray-900/50 ring-1 ring-white/10 divide-y divide-white/5 mb-8">
          <SettingRow
            label="Duration"
            hint="How long the session runs before auto-stop."
          >
            <div className="flex items-center gap-2">
              <div className="relative">
                <select
                  value={selectValue}
                  onChange={(e) => onDurationChange(e.target.value)}
                  className="appearance-none bg-gray-800/80 border border-white/10 rounded-lg pl-3 pr-9 py-2 text-sm text-gray-100 hover:bg-gray-700/80 focus:outline-none focus:ring-2 focus:ring-indigo-400/40 transition-colors cursor-pointer"
                >
                  {DURATION_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">
                  <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.06l3.71-3.83a.75.75 0 1 1 1.08 1.04l-4.25 4.39a.75.75 0 0 1-1.08 0L5.21 8.27a.75.75 0 0 1 .02-1.06z" clipRule="evenodd" />
                </svg>
              </div>
              {isCustomDuration && (
                <div className="flex items-center gap-1 text-sm text-gray-400">
                  <input
                    ref={customMinRef}
                    type="number"
                    min={0}
                    max={120}
                    step={1}
                    inputMode="numeric"
                    value={customMin}
                    onChange={(e) => onCustomMinChange(e.target.value)}
                    className="w-14 px-2 py-2 rounded-lg bg-gray-800/80 border border-white/10 text-center tabular-nums text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-400/40"
                  />
                  <span className="text-xs">min</span>
                  <input
                    type="number"
                    min={0}
                    max={59}
                    step={1}
                    inputMode="numeric"
                    value={customSec}
                    onChange={(e) => onCustomSecChange(e.target.value)}
                    className="w-14 px-2 py-2 rounded-lg bg-gray-800/80 border border-white/10 text-center tabular-nums text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-400/40 ml-1"
                  />
                  <span className="text-xs">sec</span>
                </div>
              )}
            </div>
          </SettingRow>

          <SettingRow
            label="Camera"
            hint="Required for eye-contact tracking."
          >
            <button
              type="button"
              role="switch"
              aria-checked={withCamera}
              onClick={() => chooseCamera(!withCamera)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/40 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-950 ${
                withCamera ? "bg-indigo-500" : "bg-gray-700"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  withCamera ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </SettingRow>
        </section>

        <section className="mb-10">
          <div className="flex items-baseline justify-between mb-3">
            <div>
              <h2 className="text-sm font-medium text-gray-200">Prompt</h2>
              <p className="text-xs text-gray-500 mt-0.5">What you&apos;ll talk about during the session.</p>
            </div>
            <button
              onClick={surpriseMe}
              className="text-xs font-medium text-indigo-300 hover:text-indigo-200 transition-colors"
            >
              Surprise me →
            </button>
          </div>

          <div className="flex flex-wrap gap-1.5 mb-3">
            <CategoryChip
              label="Freestyle"
              active={promptId === null}
              onClick={() => choosePrompt(null)}
            />
            {CATEGORIES.map((cat) => (
              <CategoryChip
                key={cat}
                label={cat}
                active={category === cat && promptId !== null}
                onClick={() => chooseCategory(cat)}
              />
            ))}
          </div>

          {promptId !== null ? (
            <div className="space-y-1.5">
              {promptsForCategory.map((p) => {
                const selected = p.id === promptId
                return (
                  <button
                    key={p.id}
                    onClick={() => choosePrompt(p.id)}
                    className={`flex items-start gap-3 w-full text-left px-4 py-3 rounded-xl text-sm border transition-colors ${
                      selected
                        ? "bg-indigo-500/10 border-indigo-400/50 text-indigo-50"
                        : "bg-gray-900/40 border-white/10 text-gray-300 hover:bg-gray-800/60 hover:border-white/20"
                    }`}
                  >
                    <span
                      className={`mt-0.5 w-4 h-4 rounded-full border flex-shrink-0 flex items-center justify-center transition-colors ${
                        selected ? "border-indigo-300" : "border-gray-600"
                      }`}
                    >
                      {selected && <span className="w-2 h-2 rounded-full bg-indigo-300" />}
                    </span>
                    <span className="flex-1">{p.text}</span>
                  </button>
                )
              })}
            </div>
          ) : (
            <p className="text-xs text-gray-500 italic px-1">No prompt — talk about whatever you want.</p>
          )}
        </section>

        {isStartDisabled ? (
          <button
            type="button"
            disabled
            className="block w-full text-center bg-gray-800 text-gray-500 px-6 py-3.5 rounded-xl font-medium cursor-not-allowed"
          >
            Set a duration to start
          </button>
        ) : (
          <Link
            href={startHref}
            className="block w-full text-center bg-indigo-500 hover:bg-indigo-600 active:scale-[0.99] text-white px-6 py-3.5 rounded-xl font-medium transition-all duration-150 shadow-lg shadow-indigo-500/20"
          >
            Start session
          </Link>
        )}
      </div>
    </main>
  )
}

function SettingRow({
  label,
  hint,
  children,
}: {
  label: string
  hint: string
  children: React.ReactNode
}) {
  return (
    <div className="px-5 py-4 flex items-center gap-4">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-200">{label}</p>
        <p className="text-xs text-gray-500 mt-0.5">{hint}</p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

function CategoryChip({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
        active
          ? "bg-indigo-500/15 border-indigo-400/50 text-indigo-200"
          : "bg-gray-900/40 border-white/10 text-gray-400 hover:bg-gray-800/60 hover:text-gray-200"
      }`}
    >
      {label}
    </button>
  )
}
