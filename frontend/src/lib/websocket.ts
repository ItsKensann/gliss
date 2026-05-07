import { AnalysisResult, FaceMetrics } from "./types"

// Cap the pre-open queue so a stuck handshake can't grow it without bound.
// At 16kHz mono float32 + 4-byte header, this is roughly 5-10s of audio.
const MAX_PENDING_PACKETS = 500

export class GlissWebSocket {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnects = 3
  private url = ""
  private pendingPackets: ArrayBuffer[] = []

  constructor(
    private onAnalysis: (result: AnalysisResult) => void,
    private onConnect: () => void,
    private onDisconnect: () => void
  ) {}

  connect(url: string = "ws://localhost:8000/api/v1/session"): void {
    this.url = url
    this.ws = new WebSocket(url)
    this.ws.binaryType = "arraybuffer"

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      // Flush any audio captured during the handshake so the first words aren't lost.
      for (const packet of this.pendingPackets) {
        this.ws?.send(packet)
      }
      this.pendingPackets = []
      this.onConnect()
    }

    this.ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        try {
          const result: AnalysisResult = JSON.parse(event.data)
          this.onAnalysis(result)
        } catch {}
      }
    }

    this.ws.onclose = () => {
      this.onDisconnect()
      if (this.reconnectAttempts < this.maxReconnects) {
        this.reconnectAttempts++
        setTimeout(() => this.connect(this.url), 1500 * this.reconnectAttempts)
      }
    }
  }

  sendAudioChunk(buffer: ArrayBuffer, sampleRate: number): void {
    // Prepend a 4-byte little-endian uint32 sample rate so the backend can resample.
    const packet = new ArrayBuffer(4 + buffer.byteLength)
    new DataView(packet).setUint32(0, sampleRate, true)
    new Uint8Array(packet).set(new Uint8Array(buffer), 4)

    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(packet)
    } else if (this.ws?.readyState === WebSocket.CONNECTING) {
      if (this.pendingPackets.length < MAX_PENDING_PACKETS) {
        this.pendingPackets.push(packet)
      }
    }
  }

  sendConfig(config: {
    ai_enabled?: boolean
    prompt?: string | null
    target_duration_seconds?: number | null
  }): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "config", ...config }))
    }
  }

  sendMetrics(metrics: Omit<FaceMetrics, "type">): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "metrics", ...metrics }))
    }
  }

  sendControl(action: "stop"): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "control", action }))
    }
  }

  disconnect(): void {
    this.maxReconnects = 0
    this.ws?.close()
    this.ws = null
    this.pendingPackets = []
  }
}
