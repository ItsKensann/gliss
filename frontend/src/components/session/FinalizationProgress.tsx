"use client"

import { AnimatePresence, motion } from "framer-motion"
import type { FinalizationStage } from "@/hooks/useFinalizationProgress"

interface FinalizationProgressProps {
  percent: number
  stage: FinalizationStage
  slow?: boolean
  variant?: "overlay" | "page"
}

const STAGE_LABEL: Record<FinalizationStage, string> = {
  wrapping: "Wrapping up",
  transcribing: "Transcribing your speech",
  finalizing: "Finalizing report",
  done: "Done",
}

export function FinalizationProgress({
  percent,
  stage,
  slow = false,
  variant = "page",
}: FinalizationProgressProps) {
  const clamped = Math.max(0, Math.min(100, percent))
  const label = STAGE_LABEL[stage]
  const isOverlay = variant === "overlay"

  return (
    <div className="w-full max-w-sm flex flex-col items-stretch gap-3">
      <div className="flex items-baseline justify-between">
        <AnimatePresence mode="wait">
          <motion.span
            key={label}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.25 }}
            className={`text-sm font-medium tracking-wide ${
              isOverlay ? "text-white/80" : "text-gray-300"
            }`}
          >
            {label}
          </motion.span>
        </AnimatePresence>
        <span
          className={`text-xs tabular-nums ${
            isOverlay ? "text-white/50" : "text-gray-500"
          }`}
        >
          {Math.round(clamped)}%
        </span>
      </div>
      <div
        className={`relative h-2 w-full overflow-hidden rounded-full ring-1 ${
          isOverlay ? "bg-white/10 ring-white/10" : "bg-white/5 ring-white/10"
        }`}
      >
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-indigo-400 shadow-[0_0_12px_rgba(129,140,248,0.5)]"
          initial={false}
          animate={{ width: `${clamped}%` }}
          transition={{ type: "spring", stiffness: 80, damping: 20, mass: 0.6 }}
        />
        <motion.div
          aria-hidden
          className="absolute inset-y-0 w-16 bg-gradient-to-r from-transparent via-white/20 to-transparent"
          animate={{ x: ["-100%", "400%"] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "linear" }}
        />
      </div>
      <AnimatePresence>
        {slow && (
          <motion.p
            key="slow-hint"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className={`text-xs ${isOverlay ? "text-white/50" : "text-gray-600"}`}
          >
            Whisper is finishing up, hang tight…
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  )
}
