"use client"

import { useCallback, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { GlissWebSocket } from "@/lib/websocket"
import { useMediaStream } from "./useMediaStream"
import { AnalysisResult, SessionState } from "@/lib/types"

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/api/v1/session"

interface ExtendedSessionState extends SessionState {
  aiEnabled: boolean
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
  })

  const wsRef = useRef<GlissWebSocket | null>(null)
  const sessionIdRef = useRef<string | null>(null)
  const { start: startStream, stop: stopStream, error: streamError, streamRef } = useMediaStream()

  const handleAnalysis = useCallback((result: AnalysisResult) => {
    setState((prev) => ({
      ...prev,
      latestAnalysis: result,
      transcript: (prev.transcript + " " + result.transcript).trim(),
    }))
  }, [])

  const startSession = useCallback(async () => {
    const sessionId = crypto.randomUUID()
    sessionIdRef.current = sessionId

    const ws = new GlissWebSocket(
      handleAnalysis,
      () => setState((prev) => ({ ...prev, isConnected: true })),
      () => setState((prev) => ({ ...prev, isConnected: false }))
    )

    wsRef.current = ws
    ws.connect(`${WS_URL}?session_id=${sessionId}`)

    await startStream((buffer, sampleRate) => ws.sendAudioChunk(buffer, sampleRate))

    setState((prev) => ({ ...prev, isRecording: true, sessionId }))
  }, [handleAnalysis, startStream])

  const stopSession = useCallback(() => {
    const sessionId = sessionIdRef.current
    wsRef.current?.disconnect()
    stopStream()
    setState((prev) => ({ ...prev, isRecording: false, isConnected: false }))
    if (sessionId) {
      setTimeout(() => router.push(`/report/${sessionId}`), 800)
    }
  }, [stopStream, router])

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
