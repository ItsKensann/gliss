"use client"

import { RefObject, useEffect, useRef, useState } from "react"

const INFERENCE_INTERVAL_MS = 100
const WS_SEND_INTERVAL_MS = 200
const EYE_EMA_ALPHA = 0.3
const HEAD_EMA_ALPHA = 0.25
const HEAD_WINDOW_MS = 2000
const HEAD_RMS_K = 18
const NO_FACE_GRACE_MS = 800
const EYE_HORIZONTAL_FREE = 0.06
const EYE_HORIZONTAL_FAIL = 0.23
const EYE_VERTICAL_FREE = 0.12
const EYE_VERTICAL_FAIL = 0.42
const EYE_DOWN_FREE = 0.08
const EYE_DOWN_FAIL = 0.34
const FACE_TURN_FREE = 0.06
const FACE_TURN_FAIL = 0.22
const FACE_PITCH_BASELINE_ALPHA = 0.08
const FACE_PITCH_FREE = 0.025
const FACE_PITCH_FAIL = 0.12

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
const FACE_TOP = 10
const CHIN = 152
const UPPER_LIP = 13
const LOWER_LIP = 14

type Landmark = { x: number; y: number; z: number }

function clamp01(v: number) {
  return v < 0 ? 0 : v > 1 ? 1 : v
}

function rangeScore(offset: number, free: number, fail: number) {
  if (offset <= free) return 1
  return clamp01(1 - (offset - free) / (fail - free))
}

function eyeGazeScore(lm: Landmark[]): number {
  const score = (
    iris: Landmark,
    inner: Landmark,
    outer: Landmark,
    top: Landmark,
    bot: Landmark,
  ) => {
    const cx = (inner.x + outer.x) / 2
    const cy = (top.y + bot.y) / 2
    const w = Math.hypot(outer.x - inner.x, outer.y - inner.y) || 1e-6
    const h = Math.hypot(top.x - bot.x, top.y - bot.y) || w * 0.25
    const horizontal = rangeScore(Math.abs(iris.x - cx) / w, EYE_HORIZONTAL_FREE, EYE_HORIZONTAL_FAIL)
    const verticalOffset = (iris.y - cy) / h
    const vertical = rangeScore(Math.abs(verticalOffset), EYE_VERTICAL_FREE, EYE_VERTICAL_FAIL)
    const lookingDown = rangeScore(Math.max(0, verticalOffset), EYE_DOWN_FREE, EYE_DOWN_FAIL)

    return horizontal * (vertical * 0.35 + lookingDown * 0.65)
  }

  const right = score(
    lm[RIGHT_IRIS_CENTER],
    lm[RIGHT_EYE_INNER],
    lm[RIGHT_EYE_OUTER],
    lm[RIGHT_EYE_TOP],
    lm[RIGHT_EYE_BOTTOM],
  )
  const left = score(
    lm[LEFT_IRIS_CENTER],
    lm[LEFT_EYE_INNER],
    lm[LEFT_EYE_OUTER],
    lm[LEFT_EYE_TOP],
    lm[LEFT_EYE_BOTTOM],
  )

  return (right + left) / 2
}

function faceTurnScore(lm: Landmark[]): number {
  const nose = lm[NOSE_TIP]
  const rightCheek = lm[RIGHT_CHEEK]
  const leftCheek = lm[LEFT_CHEEK]
  const faceW = Math.hypot(leftCheek.x - rightCheek.x, leftCheek.y - rightCheek.y) || 1e-6
  const faceCenterX = (leftCheek.x + rightCheek.x) / 2

  return rangeScore(Math.abs(nose.x - faceCenterX) / faceW, FACE_TURN_FREE, FACE_TURN_FAIL)
}

function facePitchSignal(lm: Landmark[]): number {
  const top = lm[FACE_TOP]
  const chin = lm[CHIN]
  const nose = lm[NOSE_TIP]
  const upperLip = lm[UPPER_LIP]
  const lowerLip = lm[LOWER_LIP]
  const leftEye = lm[LEFT_EYE_OUTER]
  const rightEye = lm[RIGHT_EYE_OUTER]
  const faceH = Math.hypot(chin.x - top.x, chin.y - top.y) || 1e-6
  const eyeY = (leftEye.y + rightEye.y) / 2
  const mouthY = (upperLip.y + lowerLip.y) / 2

  return ((nose.y - eyeY) * 0.65 + (mouthY - eyeY) * 0.35) / faceH
}

function facePitchScore(signal: number, baseline: number | null): number {
  if (baseline === null) return 1
  return rangeScore(Math.abs(signal - baseline), FACE_PITCH_FREE, FACE_PITCH_FAIL)
}

export function useFaceTracking(
  videoRef: RefObject<HTMLVideoElement | null>,
  enabled: boolean,
  onMetrics?: (eye: number, head: number, faceVisible: boolean) => void,
): { eyeContactScore: number; headStability: number; faceVisible: boolean } {
  const [eye, setEye] = useState(1.0)
  const [head, setHead] = useState(1.0)
  const [visible, setVisible] = useState(false)

  const onMetricsRef = useRef(onMetrics)
  useEffect(() => {
    onMetricsRef.current = onMetrics
  }, [onMetrics])

  const eyeRef = useRef(1.0)
  const headRef = useRef(1.0)
  const lastAnchorRef = useRef<{ x: number; y: number; t: number } | null>(null)
  const dispWindowRef = useRef<{ d: number; t: number }[]>([])
  const lastFaceSeenAtRef = useRef<number>(0)
  const lastWsSendRef = useRef<number>(0)
  const visibleRef = useRef(false)
  const pitchBaselineRef = useRef<number | null>(null)

  useEffect(() => {
    if (!enabled) return

    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null
    let busy = false
    let faceMesh: import("@mediapipe/face_mesh").FaceMesh | null = null
    lastFaceSeenAtRef.current = performance.now()

    const sendMetric = (now: number, faceVisible: boolean) => {
      if (now - lastWsSendRef.current < WS_SEND_INTERVAL_MS) return
      lastWsSendRef.current = now
      onMetricsRef.current?.(eyeRef.current, headRef.current, faceVisible)
    }

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
        const lms = results.multiFaceLandmarks?.[0] as Landmark[] | undefined

        if (!lms) {
          if (now - lastFaceSeenAtRef.current > NO_FACE_GRACE_MS) {
            if (visibleRef.current) {
              visibleRef.current = false
              setVisible(false)
              lastAnchorRef.current = null
              dispWindowRef.current = []
            }
            sendMetric(now, false)
          }
          return
        }

        lastFaceSeenAtRef.current = now
        const wasVisible = visibleRef.current
        if (!wasVisible) {
          visibleRef.current = true
          setVisible(true)
        }

        const gazeScore = eyeGazeScore(lms)
        const turnScore = faceTurnScore(lms)
        const pitchSignal = facePitchSignal(lms)
        const pitchScore = facePitchScore(pitchSignal, pitchBaselineRef.current)
        const rawEye = gazeScore * turnScore * pitchScore
        if (gazeScore * turnScore > 0.85 && pitchScore > 0.8) {
          pitchBaselineRef.current =
            pitchBaselineRef.current === null
              ? pitchSignal
              : FACE_PITCH_BASELINE_ALPHA * pitchSignal + (1 - FACE_PITCH_BASELINE_ALPHA) * pitchBaselineRef.current
        }
        const smoothedEye = wasVisible
          ? EYE_EMA_ALPHA * rawEye + (1 - EYE_EMA_ALPHA) * eyeRef.current
          : rawEye
        eyeRef.current = smoothedEye

        const nose = lms[NOSE_TIP]
        const rightCheek = lms[RIGHT_CHEEK]
        const leftCheek = lms[LEFT_CHEEK]
        const faceW = Math.hypot(leftCheek.x - rightCheek.x, leftCheek.y - rightCheek.y) || 1e-6
        const anchorX = (nose.x + rightCheek.x + leftCheek.x) / 3
        const anchorY = (nose.y + rightCheek.y + leftCheek.y) / 3
        const last = lastAnchorRef.current

        if (last) {
          const dt = now - last.t
          if (dt > 0 && dt < 500) {
            const d = Math.hypot(anchorX - last.x, anchorY - last.y) / faceW
            dispWindowRef.current.push({ d, t: now })
          }
        }
        lastAnchorRef.current = { x: anchorX, y: anchorY, t: now }

        const cutoff = now - HEAD_WINDOW_MS
        const win = dispWindowRef.current.filter((s) => s.t >= cutoff)
        dispWindowRef.current = win
        const rms = win.length
          ? Math.sqrt(win.reduce((a, s) => a + s.d * s.d, 0) / win.length)
          : 0
        const rawHeadScore = clamp01(1 - HEAD_RMS_K * rms)
        const headScore = wasVisible
          ? HEAD_EMA_ALPHA * rawHeadScore + (1 - HEAD_EMA_ALPHA) * headRef.current
          : rawHeadScore
        headRef.current = headScore

        setEye(smoothedEye)
        setHead(headScore)
        sendMetric(now, true)
      })

      const tick = async () => {
        if (cancelled) return
        const v = videoRef.current
        const ready = v && v.videoWidth > 0 && v.readyState >= 2 && !v.paused
        if (ready && !busy) {
          busy = true
          try {
            await faceMesh!.send({ image: v })
          } catch {}
          busy = false
        }
        if (!cancelled) timer = setTimeout(tick, INFERENCE_INTERVAL_MS)
      }
      timer = setTimeout(tick, INFERENCE_INTERVAL_MS)
    })()

    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
      void faceMesh?.close()
      eyeRef.current = 1.0
      headRef.current = 1.0
      lastAnchorRef.current = null
      dispWindowRef.current = []
      lastWsSendRef.current = 0
      lastFaceSeenAtRef.current = 0
      visibleRef.current = false
      pitchBaselineRef.current = null
      setEye(1.0)
      setHead(1.0)
      setVisible(false)
    }
  }, [enabled, videoRef])

  return { eyeContactScore: eye, headStability: head, faceVisible: visible }
}
