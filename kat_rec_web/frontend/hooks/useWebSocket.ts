/**
 * WebSocket Hook
 * 
 * Manages WebSocket connections for real-time updates.
 */
import { useEffect, useRef } from 'react'
import { WSClient, type WSMessage } from '@/services/wsClient'
import { useChannelStore } from '@/stores/channelSlice'
import { useFeedStore } from '@/stores/feedSlice'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

export function useWebSocket() {
  const statusClientRef = useRef<WSClient | null>(null)
  const eventsClientRef = useRef<WSClient | null>(null)
  const updateChannelStatus = useChannelStore((state) => state.updateChannelStatus)
  const updateChannel = useChannelStore((state) => state.updateChannel)
  const addFeedEvent = useFeedStore((state) => state.addEvent)
  const isMuted = useFeedStore((state) => state.isMuted)

  useEffect(() => {
    // Status WebSocket
    statusClientRef.current = new WSClient({
      url: `${WS_URL}/ws/status`,
      onMessage: (message: WSMessage) => {
        if (message.type === 'status_update' && message.data?.channels) {
          // Update channel statuses
          message.data.channels.forEach((update: any) => {
            updateChannelStatus(
              update.channel_id,
              update.status,
              update.progress
            )
          })
        }
      },
      onError: (error) => {
        console.error('Status WebSocket error:', error)
      },
      onOpen: () => {
        console.log('✅ Status WebSocket connected')
      },
      onClose: () => {
        console.log('👋 Status WebSocket disconnected')
      },
    })

    // Events WebSocket
    eventsClientRef.current = new WSClient({
      url: `${WS_URL}/ws/events`,
      onMessage: (message: WSMessage) => {
        if (message.type === 'event' && message.data && !isMuted) {
          // Add event to feed
          addFeedEvent({
            timestamp: message.data.timestamp || new Date().toISOString(),
            level: message.data.level || 'INFO',
            message: message.data.message || 'Unknown event',
            channel_id: message.data.channel_id,
            stage: message.data.stage,
          })
        }
      },
      onError: (error) => {
        console.error('Events WebSocket error:', error)
      },
      onOpen: () => {
        console.log('✅ Events WebSocket connected')
      },
      onClose: () => {
        console.log('👋 Events WebSocket disconnected')
      },
    })

    // Connect
    statusClientRef.current.connect()
    eventsClientRef.current.connect()

    // Cleanup
    return () => {
      statusClientRef.current?.disconnect()
      eventsClientRef.current?.disconnect()
    }
  }, [updateChannelStatus, updateChannel, addFeedEvent, isMuted])

  return {
    statusClient: statusClientRef.current,
    eventsClient: eventsClientRef.current,
  }
}

