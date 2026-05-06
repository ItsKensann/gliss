"use client"

import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { useSession } from "@/hooks/useSession"
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

export function Recorder() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [eyeContactScore] = useState(1.0)
  const [headStability] = useState(1.0)

  const {
    isRecording,
    isConnected,
    latestAnalysis,
    transcript,
    aiEnabled,
    phase,
    countdown,
    streamRef,
    startSession,
    stopSession,
    toggleAI,
  } = useSession()

  useEffect(() => {
    if (streamRef.current && videoRef.current) {
      videoRef.current.srcObject = streamRef.current
    }
  }, [isRecording, phase, streamRef])

  const statusText =
    phase === "preparing"
      ? "Setting up…"
      : phase === "countdown"
      ? "Get ready"
      : isConnected
      ? "Live"
      : isRecording
      ? "Connecting…"
      : "Ready"

  const statusDotClass =
    phase === "preparing" || phase === "countdown"
      ? "bg-amber-400 animate-pulse"
      : isConnected
      ? "bg-green-400 animate-pulse"
      : isRecording
      ? "bg-yellow-400"
      : "bg-gray-600"

  const buttonLabel =
    phase === "recording" ? "End Session" : phase === "countdown" ? "Cancel" : "Start Session"

  const onButtonClick = phase === "idle" ? startSession : stopSession
  const buttonDisabled = phase === "preparing"

  return (
    <div className="flex flex-col items-center gap-6">
      {/* Video preview */}
      <div className="relative w-full max-w-2xl aspect-video bg-gray-900 rounded-2xl overflow-hidden ring-1 ring-white/5">
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className="w-full h-full object-cover scale-x-[-1]"
        />

        {/* Status indicator */}
        <div className="absolute top-4 left-4 flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full transition-colors ${statusDotClass}`} />
          <span className="text-xs text-white/60 font-medium">{statusText}</span>
        </div>

        {/* Live metrics */}
        {isRecording && latestAnalysis && (
          <div className="absolute top-4 right-4 flex gap-2">
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

        <LiveFeedback
          analysis={latestAnalysis}
          eyeContactScore={eyeContactScore}
          headStability={headStability}
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
