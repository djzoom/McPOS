/**
 * WebSocket Client
 * 
 * Manages WebSocket connections for real-time updates.
 */
export type WSMessageType = 'status_update' | 'event' | 'pong'

export interface WSMessage {
  type: WSMessageType
  data: any
  timestamp?: string
}

export interface WSOptions {
  url: string
  onMessage?: (message: WSMessage) => void
  onError?: (error: Event) => void
  onOpen?: () => void
  onClose?: () => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export class WSClient {
  private ws: WebSocket | null = null
  private options: WSOptions
  private reconnectAttempts = 0
  private reconnectTimer: NodeJS.Timeout | null = null
  private pingTimer: NodeJS.Timeout | null = null
  private lastVersion = 0  // Track last received version for deduplication

  constructor(options: WSOptions) {
    this.options = {
      reconnectInterval: 2000,  // Start with 2s
      maxReconnectAttempts: 10,
      ...options,
    }
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      this.ws = new WebSocket(this.options.url)

      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        this.options.onOpen?.()
        this.startPing()
        // Request checkpoint on reconnect
        if (this.lastVersion > 0) {
          this.send({ type: 'checkpoint', version: this.lastVersion })
        }
      }

      this.ws.onmessage = (event) => {
        try {
          // Handle plain string "ping" from heartbeat
          if (event.data === 'ping' || event.data === '"ping"') {
            // Send pong response
            if (this.ws?.readyState === WebSocket.OPEN) {
              this.ws.send('pong')
            }
            return
          }

          const message: WSMessage = JSON.parse(event.data)
          
          // Handle pong
          if (message.type === 'pong') {
            return
          }

          // Deduplicate by version if available
          if (message.data?.version !== undefined) {
            const msgVersion = message.data.version
            if (msgVersion <= this.lastVersion) {
              // Skip duplicate message
              return
            }
            this.lastVersion = msgVersion
          }

          this.options.onMessage?.(message)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        this.options.onError?.(error)
      }

      this.ws.onclose = () => {
        this.stopPing()
        this.options.onClose?.()
        this.attemptReconnect()
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      this.attemptReconnect()
    }
  }

  disconnect(): void {
    this.stopPing()
    this.stopReconnect()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  send(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket is not connected')
    }
  }

  private startPing(): void {
    // Send ping every 30 seconds to keep connection alive
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send({ type: 'ping' })
      }
    }, 30000)
  }

  private stopPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= (this.options.maxReconnectAttempts || 10)) {
      console.error('Max reconnect attempts reached')
      return
    }

    this.stopReconnect()
    this.reconnectAttempts++

    // Exponential backoff: 2s → 4s → 8s → 16s → 32s → 60s (max)
    const baseInterval = this.options.reconnectInterval || 2000
    const backoffMs = Math.min(
      baseInterval * Math.pow(2, this.reconnectAttempts - 1),
      60000  // Cap at 60s
    )

    this.reconnectTimer = setTimeout(() => {
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.options.maxReconnectAttempts}) after ${backoffMs}ms...`)
      this.connect()
    }, backoffMs)
  }

  private stopReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  get readyState(): number {
    return this.ws?.readyState ?? WebSocket.CLOSED
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

