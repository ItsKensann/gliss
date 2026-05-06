/**
 * AudioWorklet processor — captures raw float32 PCM from the microphone
 * and posts chunks to the main thread every ~2 seconds.
 *
 * Runs in the audio thread (not the main thread), so it never blocks the UI.
 */
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this._chunks = []
    this._size = 0
    // sampleRate is a global inside AudioWorkletGlobalScope
    this._targetSize = sampleRate * 2 // 2 seconds of samples
  }

  process(inputs) {
    const channel = inputs[0]?.[0]
    if (!channel) return true

    this._chunks.push(channel.slice())
    this._size += channel.length

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
