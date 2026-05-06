"use client"

import { useCallback, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { GlissWebSocket } from "@/lib/websocket"
import { useMediaStream } from "./useMediaStream"
import { AnalysisResult, SessionState } from "@/lib/types"

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/api/v1/session"
const COUNTDOWN_FROM = 3

export type SessionPhase = "idle" | "preparing" | "countdown" | "recording"

interface ExtendedSessionState extends SessionState {
  aiEnabled: boolean
  phase: SessionPhase
  countdown: number
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
  })

  const wsRef = useRef<GlissWebSocket | null>(null)
  const sessionIdRef = useRef<string | null>(null)
  const cancelledRef = useRef<boolean>(false)
  const { prepare, begin, stop: stopStream, error: streamError, streamRef } = useMediaStream()

  const handleAnalysis = useCallback((result: AnalysisResult) => {
    setState((prev) => ({
      ...prev,
      latestAnalysis: result,
      transcript: (prev.transcript + " " + result.transcript).trim(),
    }))
  }, [])

  const startSession = useCallback(async () => {
    cancelledRef.current = false
    setState((prev) => ({ ...prev, phase: "preparing" }))

    const sessionId = crypto.randomUUID()
    sessionIdRef.current = sessionId

    const ws = new GlissWebSocket(
      handleAnalysis,
      () => setState((prev) => ({ ...prev, isConnected: true })),
      () => setState((prev) => ({ ...prev, isConnected: false }))
    )
    wsRef.current = ws
    ws.connect(`${WS_URL}?session_id=${sessionId}`)

    try {
      await prepare((buffer, sampleRate) => ws.sendAudioChunk(buffer, sampleRate))
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
    setState((prev) => ({ ...prev, phase: "recording", isRecording: true, countdown: 0 }))
  }, [handleAnalysis, prepare, begin])

  const stopSession = useCallback(() => {
    cancelledRef.current = true
    const sessionId = sessionIdRef.current
    const wasRecording = state.phase === "recording"

    wsRef.current?.disconnect()
    wsRef.current = null
    stopStream()
    setState((prev) => ({
      ...prev,
      isRecording: false,
      isConnected: false,
      phase: "idle",
      countdown: 0,
    }))

    // Only navigate to the report if audio actually flowed; cancelling during
    // prep/countdown just resets state.
    if (wasRecording && sessionId) {
      setTimeout(() => router.push(`/report/${sessionId}`), 800)
    }
  }, [stopStream, router, state.phase])

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
