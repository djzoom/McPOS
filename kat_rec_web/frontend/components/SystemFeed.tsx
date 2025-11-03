'use client'

import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Trash2, Volume2, VolumeX } from 'lucide-react'
import { useFeedStore, type FeedEvent } from '@/stores/feedSlice'

interface SystemFeedProps {
  isOpen?: boolean
  onClose?: () => void
}

function getLevelColor(level: FeedEvent['level']): string {
  switch (level) {
    case 'INFO':
      return 'text-blue-400'
    case 'SUCCESS':
      return 'text-green-400'
    case 'WARNING':
      return 'text-yellow-400'
    case 'ERROR':
      return 'text-red-400'
    default:
      return 'text-dark-text-secondary'
  }
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function SystemFeed({ isOpen = true, onClose }: SystemFeedProps) {
  const { events, isMuted, clearEvents, toggleMute } = useFeedStore()
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto scroll to bottom when new events arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [events])

  if (!isOpen) return null

  return (
    <motion.div
      className="fixed bottom-4 right-4 w-96 max-h-[500px] bg-dark-bg-secondary border border-dark-border rounded-lg shadow-lg z-50 flex flex-col"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-dark-border">
        <h3 className="font-semibold text-dark-text-primary">System Feed</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleMute}
            className="p-1.5 rounded hover:bg-dark-bg-tertiary transition-colors"
            title={isMuted ? 'Unmute' : 'Mute'}
          >
            {isMuted ? (
              <VolumeX className="w-4 h-4 text-dark-text-muted" />
            ) : (
              <Volume2 className="w-4 h-4 text-dark-text-muted" />
            )}
          </button>
          <button
            onClick={clearEvents}
            className="p-1.5 rounded hover:bg-dark-bg-tertiary transition-colors"
            title="Clear events"
          >
            <Trash2 className="w-4 h-4 text-dark-text-muted" />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 rounded hover:bg-dark-bg-tertiary transition-colors"
              title="Close"
            >
              <X className="w-4 h-4 text-dark-text-muted" />
            </button>
          )}
        </div>
      </div>

      {/* Events List */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-2 space-y-2"
        style={{ maxHeight: '400px' }}
      >
        {events.length === 0 ? (
          <div className="text-center text-dark-text-muted py-8 text-sm">
            暂无事件
          </div>
        ) : (
          <AnimatePresence>
            {events.map((event) => (
              <motion.div
                key={event.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className="text-sm p-2 rounded bg-dark-bg-tertiary/50 hover:bg-dark-bg-tertiary transition-colors"
              >
                <div className="flex items-start gap-2">
                  <span className={`font-mono text-xs ${getLevelColor(event.level)}`}>
                    [{event.level}]
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-dark-text-secondary">{event.message}</div>
                    <div className="flex items-center gap-2 mt-1 text-xs text-dark-text-muted">
                      <span>{formatTimestamp(event.timestamp)}</span>
                      {event.channel_id && (
                        <span className="text-blue-400">{event.channel_id}</span>
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-dark-border text-xs text-dark-text-muted">
        {events.length} 条事件
      </div>
    </motion.div>
  )
}

