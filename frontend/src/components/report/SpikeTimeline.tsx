"use client"

import type { AnalysisResult, PaceEvent } from "@/lib/types"

interface Props {
  chunks: AnalysisResult[]
  paceEvents: PaceEvent[]
  durationSeconds: number
}

interface Marker {
  lane: "pace" | "filler" | "pause"
  timeSec: number
  title: string
  detail: string
  excerpt: string
  color?: string
  ring?: string
}

function formatTime(sec: number): string {
  const total = Math.max(0, Math.floor(sec))
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${s.toString().padStart(2, "0")}`
}

function buildMarkers(chunks: AnalysisResult[], paceEvents: PaceEvent[]): Marker[] {
  const markers: Marker[] = []
  for (const event of paceEvents) {
    markers.push({
      lane: "pace",
      timeSec: event.start_seconds,
      title: "Pace spike",
      detail: `${Math.round(event.wpm)} WPM, ${Math.round((event.spike_factor - 1) * 100)}% above baseline`,
      excerpt: event.excerpt,
    })
  }

  for (const chunk of chunks) {
    const start = chunk.start_offset_seconds ?? 0
    const excerpt = chunk.transcript.length > 90
      ? `${chunk.transcript.slice(0, 90).trim()}…`
      : chunk.transcript

    if (chunk.filler_words.length >= 3) {
      const counts: Record<string, number> = {}
      for (const fw of chunk.filler_words) counts[fw.word] = (counts[fw.word] ?? 0) + 1
      const summary = Object.entries(counts)
        .map(([w, n]) => `"${w}" ×${n}`)
        .join(", ")
      markers.push({
        lane: "filler",
        timeSec: start,
        title: `${chunk.filler_words.length} filler words`,
        detail: summary,
        excerpt,
      })
    }

    for (const pause of chunk.pauses) {
      if (pause.duration >= 2.0 && pause.duration <= 4.0) {
        markers.push({
          lane: "pause",
          timeSec: start + pause.start,
          title: "Effective pause",
          detail: `${pause.duration.toFixed(1)}s pause for emphasis or reset`,
          excerpt,
          color: "bg-emerald-400",
          ring: "ring-emerald-300/40",
        })
      } else if (pause.duration > 4.0) {
        markers.push({
          lane: "pause",
          timeSec: start + pause.start,
          title: "Long pause",
          detail: `${pause.duration.toFixed(1)}s silence may break flow`,
          excerpt,
        })
      }
    }
  }
  return markers
}

const LANE_META = {
  pace: { label: "Pace", color: "bg-red-500", ring: "ring-red-400/40" },
  filler: { label: "Fillers", color: "bg-amber-400", ring: "ring-amber-300/40" },
  pause: { label: "Pauses", color: "bg-gray-400", ring: "ring-gray-300/40" },
} as const

export function SpikeTimeline({ chunks, paceEvents, durationSeconds }: Props) {
  const hasOffsets = chunks.some((c) => (c.end_offset_seconds ?? 0) > 0) || paceEvents.length > 0

  if (!hasOffsets) {
    return (
      <section className="bg-gray-800/50 rounded-xl p-5 ring-1 ring-white/5">
        <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-2">
          Timeline
        </h2>
        <p className="text-gray-500 text-sm">
          Timeline unavailable for older sessions.
        </p>
      </section>
    )
  }

  const markers = buildMarkers(chunks, paceEvents)
  const total = Math.max(durationSeconds, 1)
  const lanes: Array<keyof typeof LANE_META> = ["pace", "filler", "pause"]

  return (
    <section className="bg-gray-800/50 rounded-xl p-5 ring-1 ring-white/5">
      <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-4">
        Timeline
      </h2>

      <div className="space-y-2">
        {lanes.map((lane) => {
          const meta = LANE_META[lane]
          const laneMarkers = markers.filter((m) => m.lane === lane)
          return (
            <div key={lane} className="flex items-center gap-3">
              <div className="w-16 shrink-0 text-xs text-gray-500 uppercase tracking-wider">
                {meta.label}
              </div>
              <div className="relative flex-1 h-7 bg-gray-900/50 rounded-md ring-1 ring-white/5">
                {laneMarkers.length === 0 && (
                  <div className="absolute inset-0 flex items-center justify-center text-[10px] text-gray-600">
                    no events
                  </div>
                )}
                {laneMarkers.map((m, i) => {
                  const pct = Math.min(100, Math.max(0, (m.timeSec / total) * 100))
                  return (
                    <div
                      key={`${lane}-${i}`}
                      className="group absolute top-1/2 -translate-y-1/2 -translate-x-1/2"
                      style={{ left: `${pct}%` }}
                    >
                      <button
                        type="button"
                        className={`block w-3 h-3 min-w-[10px] rounded-full ${m.color ?? meta.color} ring-2 ${m.ring ?? meta.ring} hover:scale-125 transition-transform`}
                        aria-label={`${m.title} at ${formatTime(m.timeSec)}`}
                      />
                      <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity z-10">
                        <div className="bg-gray-950 border border-white/10 rounded-lg px-3 py-2 shadow-xl">
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="text-xs font-semibold text-white">{m.title}</span>
                            <span className="text-[10px] text-gray-500 tabular-nums">
                              {formatTime(m.timeSec)}
                            </span>
                          </div>
                          <p className="text-xs text-gray-300 mb-1">{m.detail}</p>
                          {m.excerpt && (
                            <p className="text-xs text-gray-500 italic leading-snug">
                              &ldquo;{m.excerpt}&rdquo;
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex justify-between mt-3 ml-[76px] text-[10px] text-gray-500 tabular-nums">
        <span>0:00</span>
        <span>{formatTime(total / 2)}</span>
        <span>{formatTime(total)}</span>
      </div>
    </section>
  )
}
