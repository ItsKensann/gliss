"use client"

import { useCallback, useRef, useState } from "react"

export function useMediaStream() {
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const workletRef = useRef<AudioWorkletNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Acquire mic/camera and instantiate the worklet, but don't wire the
  // audio source to it yet. This lets the UI run a countdown after permissions
  // are granted but before any audio is actually captured.
  const prepare = useCallback(
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

        const audioCtx = new AudioContext()
        audioCtxRef.current = audioCtx

        await audioCtx.audioWorklet.addModule("/audio-processor.js")

        const source = audioCtx.createMediaStreamSource(stream)
        sourceRef.current = source

        const worklet = new AudioWorkletNode(audioCtx, "pcm-processor")
        workletRef.current = worklet

        worklet.port.onmessage = (event: MessageEvent<{ pcm: ArrayBuffer; sampleRate: number }>) => {
          onChunk(event.data.pcm, event.data.sampleRate)
        }

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

  // Connect source → worklet so audio actually starts flowing to the backend.
  const begin = useCallback(() => {
    if (!sourceRef.current || !workletRef.current) return
    sourceRef.current.connect(workletRef.current)
    setIsStreaming(true)
  }, [])

  const stop = useCallback(() => {
    sourceRef.current?.disconnect()
    workletRef.current?.disconnect()
    workletRef.current?.port.close()
    audioCtxRef.current?.close()
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    audioCtxRef.current = null
    workletRef.current = null
    sourceRef.current = null
    setIsStreaming(false)
  }, [])

  return { prepare, begin, stop, isStreaming, error, streamRef }
}
