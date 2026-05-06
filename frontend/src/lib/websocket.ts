import { AnalysisResult, FaceMetrics } from "./types"

export class GlissWebSocket {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnects = 3
  private url = ""

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
    if (this.ws?.readyState !== WebSocket.OPEN) return
    // Prepend a 4-byte little-endian uint32 sample rate so the backend can resample.
    const packet = new ArrayBuffer(4 + buffer.byteLength)
    new DataView(packet).setUint32(0, sampleRate, true)
    new Uint8Array(packet).set(new Uint8Array(buffer), 4)
    this.ws.send(packet)
  }

  sendConfig(config: { ai_enabled: boolean }): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "config", ...config }))
    }
  }

  sendMetrics(metrics: Omit<FaceMetrics, "type">): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "metrics", ...metrics }))
    }
  }

  disconnect(): void {
    this.maxReconnects = 0
    this.ws?.close()
    this.ws = null
  }
}
