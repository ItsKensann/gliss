"use client"

import { useEffect, useRef } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { useSession } from "@/hooks/useSession"
import { useFaceTracking } from "@/hooks/useFaceTracking"
import { LiveFeedback } from "./LiveFeedback"

function MetricPill({ label, value, highlight }: { label: string; value: string; highlight: boolean }) {
  return (
    <div
      className={`px-3 py-1 rounded-full text-xs font-medium backdrop-blur-sm border transition-colors ${
        highlight
          ? "bg-amber-500/30 border-amber-400/50 text-amber-200"
          : "bg-black/30 border-white/10 text-white/70"
      }`}
    >
      {label}: {value}
    </div>
  )
}

function formatRemaining(ms: number): string {
  const totalSec = Math.max(0, Math.ceil(ms / 1000))
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  return `${m}:${s.toString().padStart(2, "0")}`
}

interface RecorderProps {
  durationSec?: number | null
  prompt?: string
  withCamera?: boolean
}

export function Recorder({ durationSec = null, prompt, withCamera = true }: RecorderProps) {
  const videoRef = useRef<HTMLVideoElement>(null)

  const {
    isRecording,
    isConnected,
    latestAnalysis,
    transcript,
    aiEnabled,
    phase,
    countdown,
    remainingMs,
    streamRef,
    startSession,
    stopSession,
    toggleAI,
    sendFaceMetrics,
  } = useSession()

  const { eyeContactScore, headStability, faceVisible } = useFaceTracking(
    videoRef,
    isRecording && withCamera,
    sendFaceMetrics,
  )

  useEffect(() => {
    if (withCamera && streamRef.current && videoRef.current) {
      videoRef.current.srcObject = streamRef.current
    }
  }, [isRecording, phase, streamRef, withCamera])

  const statusText =
    phase === "preparing"
      ? "Setting up…"
      : phase === "countdown"
      ? "Get ready"
      : phase === "wrapping"
      ? "Wrapping up…"
      : isConnected
      ? "Live"
      : isRecording
      ? "Connecting…"
      : "Ready"

  const statusDotClass =
    phase === "preparing" || phase === "countdown" || phase === "wrapping"
      ? "bg-amber-400 animate-pulse"
      : isConnected
      ? "bg-green-400 animate-pulse"
      : isRecording
      ? "bg-yellow-400"
      : "bg-gray-600"

  const buttonLabel =
    phase === "recording"
      ? "End Session"
      : phase === "countdown"
      ? "Cancel"
      : phase === "wrapping"
      ? "Wrapping up…"
      : "Start Session"

  const onButtonClick =
    phase === "idle" ? () => startSession({ durationSec, prompt, withCamera }) : stopSession
  const buttonDisabled = phase === "preparing" || phase === "wrapping"

  const showTimer = phase === "recording" && remainingMs !== null
  const timerTone =
    remainingMs !== null && remainingMs <= 10_000
      ? "bg-red-500/30 border-red-400/60 text-red-100 animate-pulse"
      : remainingMs !== null && remainingMs <= 30_000
      ? "bg-amber-500/30 border-amber-400/50 text-amber-100 animate-pulse"
      : "bg-black/40 border-white/10 text-white/80"

  return (
    <div className="flex flex-col items-center gap-6">
      {/* Prompt card */}
      {prompt && (
        <div className="w-full max-w-2xl bg-indigo-500/10 border border-indigo-400/20 rounded-xl px-5 py-4">
          <p className="text-xs uppercase tracking-widest text-indigo-300/70 mb-1.5">Prompt</p>
          <p className="text-indigo-100 text-base italic leading-relaxed">{prompt}</p>
        </div>
      )}

      {/* Media surface: video preview or audio-only visual */}
      <div className="relative w-full max-w-2xl aspect-video bg-gray-900 rounded-2xl overflow-hidden ring-1 ring-white/5">
        {withCamera ? (
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            className="w-full h-full object-cover scale-x-[-1]"
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-gradient-to-br from-gray-900 via-gray-950 to-black">
            <div className="relative">
              {isRecording && (
                <>
                  <span className="absolute inset-0 rounded-full bg-indigo-500/20 animate-ping" />
                  <span className="absolute -inset-4 rounded-full bg-indigo-500/10 animate-ping" style={{ animationDelay: "0.5s" }} />
                </>
              )}
              <div className="relative w-24 h-24 rounded-full bg-indigo-500/20 ring-2 ring-indigo-400/40 flex items-center justify-center">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="w-10 h-10 text-indigo-200"
                >
                  <rect x="9" y="3" width="6" height="12" rx="3" />
                  <path d="M5 11a7 7 0 0 0 14 0" />
                  <line x1="12" y1="18" x2="12" y2="22" />
                  <line x1="8" y1="22" x2="16" y2="22" />
                </svg>
              </div>
            </div>
            <p className="mt-6 text-sm text-gray-400 tracking-wide uppercase">Audio only</p>
          </div>
        )}

        {/* Status indicator */}
        <div className="absolute top-4 left-4 flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full transition-colors ${statusDotClass}`} />
          <span className="text-xs text-white/60 font-medium">{statusText}</span>
        </div>

        {/* Timer */}
        {showTimer && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2">
            <div
              className={`px-3 py-1 rounded-full text-sm font-semibold tabular-nums backdrop-blur-sm border transition-colors ${timerTone}`}
            >
              {formatRemaining(remainingMs ?? 0)}
            </div>
          </div>
        )}

        {/* Live metrics */}
        {isRecording && (
          <div className="absolute top-4 right-4 flex gap-2 flex-wrap justify-end">
            {latestAnalysis && (
              <>
                <MetricPill
                  label="WPM"
                  value={latestAnalysis.speed.current_wpm.toFixed(0)}
                  highlight={latestAnalysis.speed.is_spike}
                />
                <MetricPill
                  label="Fillers"
                  value={String(latestAnalysis.filler_words.length)}
                  highlight={latestAnalysis.filler_words.length > 3}
                />
                {latestAnalysis.coherence_score !== undefined && (
                  <MetricPill
                    label="Focus"
                    value={`${Math.round(latestAnalysis.coherence_score * 100)}%`}
                    highlight={latestAnalysis.coherence_score < 0.5}
                  />
                )}
              </>
            )}
            {withCamera && (
              <MetricPill
                label="Eye"
                value={faceVisible ? `${Math.round(eyeContactScore * 100)}%` : "—"}
                highlight={faceVisible && eyeContactScore < 0.5}
              />
            )}
          </div>
        )}

        {/* Countdown overlay */}
        <AnimatePresence>
          {phase === "countdown" && (
            <motion.div
              key="countdown-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 flex flex-col items-center justify-center bg-black/55 backdrop-blur-sm"
            >
              <span className="text-white/70 text-sm font-medium mb-2 tracking-wide uppercase">
                Recording in
              </span>
              <AnimatePresence mode="wait">
                <motion.div
                  key={countdown}
                  initial={{ scale: 0.5, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 1.6, opacity: 0 }}
                  transition={{ duration: 0.4, ease: "easeOut" }}
                  className="text-white text-9xl font-bold tabular-nums"
                >
                  {countdown}
                </motion.div>
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Wrap-up overlay */}
        <AnimatePresence>
          {phase === "wrapping" && (
            <motion.div
              key="wrap-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 flex flex-col items-center justify-center bg-black/55 backdrop-blur-sm"
            >
              <span className="text-white/70 text-sm font-medium mb-3 tracking-wide uppercase">
                Wrapping up
              </span>
              <div className="flex gap-1.5">
                {[0, 1, 2].map((i) => (
                  <motion.span
                    key={i}
                    className="w-2.5 h-2.5 rounded-full bg-amber-300"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
                  />
                ))}
              </div>
              <p className="text-white/50 text-xs mt-4">Capturing your final words…</p>
            </motion.div>
          )}
        </AnimatePresence>

        <LiveFeedback
          analysis={latestAnalysis}
          eyeContactScore={eyeContactScore}
          headStability={headStability}
          faceVisible={faceVisible}
        />
      </div>

      {/* Start / Cancel / End */}
      <button
        onClick={onButtonClick}
        disabled={buttonDisabled}
        className={`px-8 py-4 rounded-2xl font-semibold text-lg transition-all duration-200 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed ${
          phase === "recording"
            ? "bg-red-500 hover:bg-red-600 text-white"
            : phase === "countdown"
            ? "bg-gray-600 hover:bg-gray-700 text-white"
            : "bg-indigo-500 hover:bg-indigo-600 text-white"
        }`}
      >
        {buttonLabel}
      </button>

      {/* AI toggle — visible while recording */}
      {isRecording && (
        <button
          onClick={() => toggleAI(!aiEnabled)}
          className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium border transition-colors ${
            aiEnabled
              ? "bg-purple-500/20 border-purple-400/40 text-purple-300 hover:bg-purple-500/30"
              : "bg-gray-800/60 border-gray-600/40 text-gray-500 hover:bg-gray-700/60"
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${aiEnabled ? "bg-purple-400" : "bg-gray-600"}`} />
          AI Feedback {aiEnabled ? "ON" : "OFF"}
        </button>
      )}

      {/* Rolling transcript */}
      {transcript && (
        <div className="w-full max-w-2xl bg-gray-800/40 rounded-xl p-4 text-gray-300 text-sm leading-relaxed max-h-40 overflow-y-auto ring-1 ring-white/5">
          {transcript}
        </div>
      )}
    </div>
  )
}
