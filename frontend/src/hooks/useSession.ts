"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { GlissWebSocket } from "@/lib/websocket"
import { useMediaStream } from "./useMediaStream"
import { AnalysisResult, SessionState } from "@/lib/types"

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/api/v1/session"
const COUNTDOWN_FROM = 3
const WRAP_BUFFER_MS = 2000

export type SessionPhase = "idle" | "preparing" | "countdown" | "recording" | "wrapping"

interface ExtendedSessionState extends SessionState {
  aiEnabled: boolean
  phase: SessionPhase
  countdown: number
  durationSec: number | null
  remainingMs: number | null
}

interface StartOptions {
  durationSec?: number | null
  prompt?: string
  withCamera?: boolean
}

export function useSession() {
  const router = useRouter()
  const [state, setState] = useState<ExtendedSessionState>({
    isRecording: false,
    isConnected: false,
    latestAnalysis: null,
    transcript: "",
    sessionId: null,
    aiEnabled: false,
    phase: "idle",
    countdown: 0,
    durationSec: null,
    remainingMs: null,
  })

  const wsRef = useRef<GlissWebSocket | null>(null)
  const sessionIdRef = useRef<string | null>(null)
  const cancelledRef = useRef<boolean>(false)
  const recordingStartedAtRef = useRef<number | null>(null)
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const durationSecRef = useRef<number | null>(null)
  const wrappingRef = useRef<boolean>(false)
  const wrapTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const { prepare, begin, stop: stopStream, error: streamError, streamRef } = useMediaStream()

  const handleAnalysis = useCallback((result: AnalysisResult) => {
    setState((prev) => ({
      ...prev,
      latestAnalysis: result,
      transcript: (prev.transcript + " " + result.transcript).trim(),
    }))
  }, [])

  const clearTimer = useCallback(() => {
    if (timerIntervalRef.current !== null) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }
  }, [])

  const finalizeStop = useCallback((sessionId: string | null, navigate: boolean) => {
    wsRef.current?.disconnect()
    wsRef.current = null
    stopStream()
    wrappingRef.current = false
    setState((prev) => ({
      ...prev,
      isRecording: false,
      isConnected: false,
      phase: "idle",
      countdown: 0,
      remainingMs: null,
    }))
    if (navigate && sessionId) {
      router.push(`/report/${sessionId}`)
    }
  }, [stopStream, router])

  const stopSession = useCallback(() => {
    if (wrappingRef.current) return

    cancelledRef.current = true
    const sessionId = sessionIdRef.current
    const wasRecording = state.phase === "recording"

    clearTimer()
    recordingStartedAtRef.current = null

    if (!wasRecording) {
      // Cancelled during prep/countdown — no audio captured, immediate teardown.
      finalizeStop(sessionId, false)
      return
    }

    // Tell the backend the user signaled end *now*, before audio keeps streaming
    // for the wrap-up buffer. This pins the report's ended_at to the moment of
    // user intent, not to whenever Whisper finishes the final cycle.
    wsRef.current?.sendControl("stop")

    // Keep audio + WS alive for WRAP_BUFFER_MS so trailing words make it into
    // the backend's final transcription cycle.
    wrappingRef.current = true
    setState((prev) => ({
      ...prev,
      phase: "wrapping",
      isRecording: false,
      remainingMs: null,
    }))
    wrapTimeoutRef.current = setTimeout(() => {
      wrapTimeoutRef.current = null
      finalizeStop(sessionId, true)
    }, WRAP_BUFFER_MS)
  }, [state.phase, clearTimer, finalizeStop])

  const stopSessionRef = useRef(stopSession)
  useEffect(() => {
    stopSessionRef.current = stopSession
  }, [stopSession])

  const startSession = useCallback(async (opts: StartOptions = {}) => {
    cancelledRef.current = false
    const durationSec = opts.durationSec ?? null
    const prompt = opts.prompt
    const withCamera = opts.withCamera ?? true
    durationSecRef.current = durationSec
    setState((prev) => ({
      ...prev,
      phase: "preparing",
      durationSec,
      remainingMs: durationSec !== null ? durationSec * 1000 : null,
    }))

    const sessionId = crypto.randomUUID()
    sessionIdRef.current = sessionId

    const ws = new GlissWebSocket(
      handleAnalysis,
      () => {
        setState((prev) => ({ ...prev, isConnected: true }))
        if (durationSec !== null || prompt) {
          ws.sendConfig({
            target_duration_seconds: durationSec ?? undefined,
            prompt: prompt ?? undefined,
          })
        }
      },
      () => setState((prev) => ({ ...prev, isConnected: false }))
    )
    wsRef.current = ws
    ws.connect(`${WS_URL}?session_id=${sessionId}`)

    try {
      await prepare(
        (buffer, sampleRate) => ws.sendAudioChunk(buffer, sampleRate),
        { withCamera },
      )
    } catch {
      cancelledRef.current = true
      setState((prev) => ({ ...prev, phase: "idle", sessionId: null }))
      return
    }

    if (cancelledRef.current) return

    setState((prev) => ({ ...prev, phase: "countdown", countdown: COUNTDOWN_FROM, sessionId }))

    for (let n = COUNTDOWN_FROM; n >= 1; n--) {
      setState((prev) => ({ ...prev, countdown: n }))
      await new Promise((r) => setTimeout(r, 1000))
      if (cancelledRef.current) return
    }

    begin()
    recordingStartedAtRef.current = performance.now()
    setState((prev) => ({ ...prev, phase: "recording", isRecording: true, countdown: 0 }))

    if (durationSec !== null) {
      // Compute remaining from a fixed start time so background-tab throttling
      // can't cause drift — we re-derive on every tick instead of decrementing.
      timerIntervalRef.current = setInterval(() => {
        const start = recordingStartedAtRef.current
        const dur = durationSecRef.current
        if (start === null || dur === null) return
        const remaining = dur * 1000 - (performance.now() - start)
        if (remaining <= 0) {
          setState((prev) => ({ ...prev, remainingMs: 0 }))
          stopSessionRef.current()
        } else {
          setState((prev) => ({ ...prev, remainingMs: remaining }))
        }
      }, 250)
    }
  }, [handleAnalysis, prepare, begin])

  useEffect(() => {
    return () => {
      clearTimer()
      if (wrapTimeoutRef.current !== null) {
        clearTimeout(wrapTimeoutRef.current)
        wrapTimeoutRef.current = null
      }
    }
  }, [clearTimer])

  const toggleAI = useCallback((enabled: boolean) => {
    wsRef.current?.sendConfig({ ai_enabled: enabled })
    setState((prev) => ({ ...prev, aiEnabled: enabled }))
  }, [])

  const sendFaceMetrics = useCallback(
    (eyeContactScore: number, headStability: number) => {
      wsRef.current?.sendMetrics({
        eye_contact_score: eyeContactScore,
        head_stability: headStability,
        timestamp: Date.now(),
      })
    },
    []
  )

  return { ...state, streamError, streamRef, startSession, stopSession, toggleAI, sendFaceMetrics }
}
