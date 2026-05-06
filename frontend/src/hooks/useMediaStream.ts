"use client"

import { useCallback, useRef, useState } from "react"

export function useMediaStream() {
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const workletRef = useRef<AudioWorkletNode | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const start = useCallback(
    async (onChunk: (buffer: ArrayBuffer, sampleRate: number) => void) => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
          },
          video: { width: 640, height: 480, frameRate: 30 },
        })
        streamRef.current = stream

        // Use the browser's native sample rate — the worklet reports it back
        // so the backend can resample correctly.
        const audioCtx = new AudioContext()
        audioCtxRef.current = audioCtx

        await audioCtx.audioWorklet.addModule("/audio-processor.js")

        const source = audioCtx.createMediaStreamSource(stream)
        const worklet = new AudioWorkletNode(audioCtx, "pcm-processor")
        workletRef.current = worklet

        worklet.port.onmessage = (event: MessageEvent<{ pcm: ArrayBuffer; sampleRate: number }>) => {
          onChunk(event.data.pcm, event.data.sampleRate)
        }

        source.connect(worklet)
        // Worklet does not need to connect to destination — it only reads input.

        setIsStreaming(true)
        setError(null)
        return stream
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to access camera/mic"
        setError(msg)
        throw err
      }
    },
    []
  )

  const stop = useCallback(() => {
    workletRef.current?.disconnect()
    workletRef.current?.port.close()
    audioCtxRef.current?.close()
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    audioCtxRef.current = null
    workletRef.current = null
    setIsStreaming(false)
  }, [])

  return { start, stop, isStreaming, error, streamRef }
}
