"use client"

import { useEffect, useRef, useState, RefObject } from "react"

const INFERENCE_INTERVAL_MS = 100        // ~10 Hz
const WS_SEND_INTERVAL_MS = 200          // ~5 Hz to backend
const EYE_EMA_ALPHA = 0.3                // 0 = no smoothing, 1 = no memory
const HEAD_WINDOW_MS = 2000              // rolling window for displacement RMS
const EYE_OFFSET_K = 3.5                 // offset → score scaling (tune)
const HEAD_RMS_K = 28                    // displacement RMS → instability scaling (tune)
const NO_FACE_GRACE_MS = 800             // tolerate brief detection dropouts

// Landmark indices (refineLandmarks=true gives 478 points incl. iris)
const RIGHT_EYE_OUTER = 33
const RIGHT_EYE_INNER = 133
const RIGHT_EYE_TOP = 159
const RIGHT_EYE_BOTTOM = 145
const RIGHT_IRIS_CENTER = 468

const LEFT_EYE_OUTER = 263
const LEFT_EYE_INNER = 362
const LEFT_EYE_TOP = 386
const LEFT_EYE_BOTTOM = 374
const LEFT_IRIS_CENTER = 473

const NOSE_TIP = 1
const RIGHT_CHEEK = 234
const LEFT_CHEEK = 454

type Landmark = { x: number; y: number; z: number }

function clamp01(v: number) {
  return v < 0 ? 0 : v > 1 ? 1 : v
}

function eyeContactScore(lm: Landmark[]): number {
  const score = (
    iris: Landmark, inner: Landmark, outer: Landmark, top: Landmark, bot: Landmark,
  ) => {
    const cx = (inner.x + outer.x) / 2
    const cy = (top.y + bot.y) / 2
    const w = Math.hypot(outer.x - inner.x, outer.y - inner.y) || 1e-6
    const dx = (iris.x - cx) / w
    const dy = (iris.y - cy) / w
    const offset = Math.hypot(dx, dy)
    return clamp01(1 - EYE_OFFSET_K * offset)
  }
  const r = score(lm[RIGHT_IRIS_CENTER], lm[RIGHT_EYE_INNER], lm[RIGHT_EYE_OUTER], lm[RIGHT_EYE_TOP], lm[RIGHT_EYE_BOTTOM])
  const l = score(lm[LEFT_IRIS_CENTER], lm[LEFT_EYE_INNER], lm[LEFT_EYE_OUTER], lm[LEFT_EYE_TOP], lm[LEFT_EYE_BOTTOM])
  return (r + l) / 2
}

export function useFaceTracking(
  videoRef: RefObject<HTMLVideoElement | null>,
  enabled: boolean,
  onMetrics?: (eye: number, head: number, faceVisible: boolean) => void,
): { eyeContactScore: number; headStability: number; faceVisible: boolean } {
  const [eye, setEye] = useState(1.0)
  const [head, setHead] = useState(1.0)
  const [visible, setVisible] = useState(true)

  const onMetricsRef = useRef(onMetrics)
  useEffect(() => { onMetricsRef.current = onMetrics }, [onMetrics])

  // Refs avoid re-running the heavy effect on every score update.
  const eyeRef = useRef(1.0)
  const headRef = useRef(1.0)
  const lastNoseRef = useRef<{ x: number; y: number; t: number } | null>(null)
  const dispWindowRef = useRef<{ d: number; t: number }[]>([])
  const lastFaceSeenAtRef = useRef<number>(performance.now())
  const lastWsSendRef = useRef<number>(0)

  useEffect(() => {
    if (!enabled) return

    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null
    let busy = false
    let faceMesh: import("@mediapipe/face_mesh").FaceMesh | null = null

    void (async () => {
      const mod = await import("@mediapipe/face_mesh")
      if (cancelled) return

      faceMesh = new mod.FaceMesh({
        locateFile: (file) =>
          `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh@0.4.1633559619/${file}`,
      })
      faceMesh.setOptions({
        maxNumFaces: 1,
        refineLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5,
      })

      faceMesh.onResults((results) => {
        const now = performance.now()
        const lms = results.multiFaceLandmarks?.[0]
        if (!lms) {
          // Hold last value; only flip visible after a grace period so single
          // dropped frames don't flicker the UI.
          if (now - lastFaceSeenAtRef.current > NO_FACE_GRACE_MS && visible) {
            setVisible(false)
          }
          return
        }
        lastFaceSeenAtRef.current = now
        if (!visible) setVisible(true)

        // Eye contact, smoothed.
        const rawEye = eyeContactScore(lms as Landmark[])
        const smoothedEye = EYE_EMA_ALPHA * rawEye + (1 - EYE_EMA_ALPHA) * eyeRef.current
        eyeRef.current = smoothedEye

        // Head stability via nose-tip displacement, normalized by face width.
        const nose = lms[NOSE_TIP]
        const rc = lms[RIGHT_CHEEK]
        const lc = lms[LEFT_CHEEK]
        const faceW = Math.hypot(lc.x - rc.x, lc.y - rc.y) || 1e-6
        const last = lastNoseRef.current
        if (last) {
          const dt = now - last.t
          if (dt > 0 && dt < 500) {
            const d = Math.hypot(nose.x - last.x, nose.y - last.y) / faceW
            dispWindowRef.current.push({ d, t: now })
          }
        }
        lastNoseRef.current = { x: nose.x, y: nose.y, t: now }

        const cutoff = now - HEAD_WINDOW_MS
        const win = dispWindowRef.current.filter((s) => s.t >= cutoff)
        dispWindowRef.current = win
        const rms = win.length
          ? Math.sqrt(win.reduce((a, s) => a + s.d * s.d, 0) / win.length)
          : 0
        const headScore = clamp01(1 - HEAD_RMS_K * rms)
        headRef.current = headScore

        setEye(smoothedEye)
        setHead(headScore)

        if (now - lastWsSendRef.current >= WS_SEND_INTERVAL_MS) {
          lastWsSendRef.current = now
          onMetricsRef.current?.(smoothedEye, headScore, true)
        }
      })

      // Inference loop — single in-flight at a time.
      const tick = async () => {
        if (cancelled) return
        const v = videoRef.current
        const ready = v && v.videoWidth > 0 && v.readyState >= 2 && !v.paused
        if (ready && !busy) {
          busy = true
          try {
            await faceMesh!.send({ image: v })
          } catch {
            // Swallow — model errors shouldn't kill the loop.
          }
          busy = false
        }
        if (!cancelled) timer = setTimeout(tick, INFERENCE_INTERVAL_MS)
      }
      timer = setTimeout(tick, INFERENCE_INTERVAL_MS)
    })()

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
      // close() is async; fire-and-forget — we've already cancelled the loop.
      void faceMesh?.close()
      // Reset state for the next session so stale values don't bleed across.
      eyeRef.current = 1.0
      headRef.current = 1.0
      lastNoseRef.current = null
      dispWindowRef.current = []
      lastWsSendRef.current = 0
      lastFaceSeenAtRef.current = performance.now()
      setEye(1.0)
      setHead(1.0)
      setVisible(true)
    }
  // `visible` is intentionally excluded — it's read inside but updating it
  // shouldn't tear down the model.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, videoRef])

  return { eyeContactScore: eye, headStability: head, faceVisible: visible }
}
