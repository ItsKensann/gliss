"use client"

import { useEffect, useRef, useState } from "react"

export type FinalizationStage = "wrapping" | "transcribing" | "finalizing" | "done"

interface UseFinalizationProgressInput {
  startedAt: number | null
  recordingDurationMs: number | null
  gotPreliminary: boolean
  gotFinalized: boolean
  backendPercent?: number | null
  backendStage?: FinalizationStage | null
}

interface FinalizationProgressState {
  percent: number
  stage: FinalizationStage
  slow: boolean
}

const WRAP_BUFFER_SEC = 2
const PRELIM_RAMP_SEC = 3
const PRELIM_ANCHOR = 25
const FINALIZED_ANCHOR = 90
const MIN_WHISPER_SEC = 5
const WHISPER_RATIO = 0.3
const SLOW_THRESHOLD_SEC = 15
const FALLBACK_DURATION_MS = 60_000

function computeState(
  input: UseFinalizationProgressInput,
  now: number,
): FinalizationProgressState {
  const {
    startedAt,
    recordingDurationMs,
    gotPreliminary,
    gotFinalized,
    backendPercent,
    backendStage,
  } = input

  if (startedAt === null) {
    return { percent: 0, stage: "wrapping", slow: false }
  }

  const elapsed = Math.max(0, (now - startedAt) / 1000)
  const slow = elapsed > SLOW_THRESHOLD_SEC

  if (gotFinalized) {
    return { percent: 100, stage: "finalizing", slow: false }
  }

  if (backendPercent !== null && backendPercent !== undefined) {
    const stage =
      backendStage ?? (elapsed < WRAP_BUFFER_SEC ? "wrapping" : "transcribing")
    return { percent: backendPercent, stage, slow }
  }

  if (!gotPreliminary) {
    const stage: FinalizationStage = elapsed < WRAP_BUFFER_SEC ? "wrapping" : "transcribing"
    const ramp = Math.min(1, elapsed / PRELIM_RAMP_SEC)
    const eased = 1 - Math.pow(1 - ramp, 2)
    const percent = eased * PRELIM_ANCHOR
    return { percent, stage, slow }
  }

  const durationMs = recordingDurationMs ?? FALLBACK_DURATION_MS
  const estWhisperSec = Math.max(MIN_WHISPER_SEC, (durationMs / 1000) * WHISPER_RATIO)
  const whisperElapsed = Math.max(0, elapsed - PRELIM_RAMP_SEC)
  const ramp = Math.min(1, whisperElapsed / estWhisperSec)
  const eased = 1 - Math.pow(1 - ramp, 2)
  const percent = PRELIM_ANCHOR + eased * (FINALIZED_ANCHOR - PRELIM_ANCHOR)
  return { percent, stage: "transcribing", slow }
}

export function useFinalizationProgress(
  input: UseFinalizationProgressInput,
): FinalizationProgressState {
  const [state, setState] = useState<FinalizationProgressState>(() => computeState(input, Date.now()))
  const inputRef = useRef(input)
  inputRef.current = input

  useEffect(() => {
    setState(computeState(inputRef.current, Date.now()))

    if (input.startedAt === null) return

    const tick = () => setState(computeState(inputRef.current, Date.now()))
    const intervalId = setInterval(tick, 100)
    return () => clearInterval(intervalId)
  }, [
    input.startedAt,
    input.gotPreliminary,
    input.gotFinalized,
    input.backendPercent,
    input.backendStage,
  ])

  return state
}
