"use client"

import { AnimatePresence, motion } from "framer-motion"
import { AnalysisResult, ImmediateFeedback } from "@/lib/types"

interface Props {
  analysis: AnalysisResult | null
  eyeContactScore: number
  headStability: number
}

const severityStyles: Record<ImmediateFeedback["severity"], string> = {
  info: "bg-blue-500/20 border-blue-400/40 text-blue-200",
  warning: "bg-amber-500/20 border-amber-400/40 text-amber-200",
  critical: "bg-red-500/20 border-red-400/40 text-red-200",
}

export function LiveFeedback({ analysis, eyeContactScore, headStability }: Props) {
  const postureFeedback: ImmediateFeedback[] = [
    ...(eyeContactScore < 0.5
      ? [{ message: "Try to maintain eye contact", type: "posture" as const, severity: "warning" as const }]
      : []),
    ...(headStability < 0.4
      ? [{ message: "Keep your head steadier while speaking", type: "posture" as const, severity: "info" as const }]
      : []),
  ]

  const allFeedback = [...(analysis?.immediate_feedback ?? []), ...postureFeedback].slice(0, 3)

  return (
    <div className="absolute bottom-4 left-4 right-4 space-y-2 pointer-events-none">
      <AnimatePresence mode="popLayout">
        {allFeedback.map((fb, i) => (
          <motion.div
            key={`${fb.message}-${i}`}
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.96 }}
            transition={{ duration: 0.2 }}
            className={`px-4 py-2 rounded-xl border backdrop-blur-sm text-sm font-medium ${severityStyles[fb.severity]}`}
          >
            {fb.message}
          </motion.div>
        ))}
      </AnimatePresence>

      <AnimatePresence>
        {analysis?.ai_feedback && (
          <motion.div
            key={analysis.ai_feedback}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="px-4 py-3 rounded-xl border bg-purple-500/20 border-purple-400/40 text-purple-200 text-sm"
          >
            <span className="font-semibold">Coach: </span>
            {analysis.ai_feedback}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
