/**
 * AudioWorklet processor — captures raw float32 PCM from the microphone
 * and posts ~250ms chunks to the main thread.
 *
 * Runs in the audio thread (not the main thread), so it never blocks the UI.
 */
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this._chunks = []
    this._size = 0
    // Small chunks so the user's first words reach the backend within ~250ms
    // of being spoken — large chunks made the start of a session feel laggy.
    // sampleRate is a global inside AudioWorkletGlobalScope.
    this._targetSize = Math.floor(sampleRate * 0.25)
  }

  process(inputs) {
    const input = inputs[0]
    if (!input?.length) return true

    const frames = input[0].length
    const mono = new Float32Array(frames)
    for (const channel of input) {
      for (let i = 0; i < frames; i++) {
        mono[i] += channel[i] / input.length
      }
    }

    this._chunks.push(mono)
    this._size += mono.length

    if (this._size >= this._targetSize) {
      const merged = new Float32Array(this._size)
      let offset = 0
      for (const c of this._chunks) {
        merged.set(c, offset)
        offset += c.length
      }
      // Transfer ownership — zero-copy send to main thread
      this.port.postMessage({ pcm: merged.buffer, sampleRate }, [merged.buffer])
      this._chunks = []
      this._size = 0
    }

    return true // keep processor alive
  }
}

registerProcessor("pcm-processor", PCMProcessor)
