'use client'

import { useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { type ScheduleEvent } from '@/stores/scheduleStore'
import { getStatusColor, type AssetCompleteness } from '@/lib/designTokens'
import { motion } from 'framer-motion'
import { Calendar, Clock, AlertCircle } from 'lucide-react'

interface ChannelTimelineProps {
  channelId: string
  events: ScheduleEvent[]
  focusDate: string | null
  onEventClick: (eventId: string) => void
  onEventFocus: (eventId: string) => void
}

/**
 * Calculate asset completeness for an event
 */
function calculateCompleteness(event: ScheduleEvent): AssetCompleteness {
  const assets = event.assets
  const count = [
    assets.cover,
    assets.audio,
    assets.description,
    assets.captions,
  ].filter(Boolean).length
  
  if (count === 4) return 'complete'
  if (count === 0) return 'missing'
  return 'partial'
}

/**
 * Format duration
 */
function formatDuration(seconds: number): string {
  if (seconds <= 0) return '—'
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${String(secs).padStart(2, '0')}`
}

/**
 * Format date for display
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    weekday: 'short',
  })
}

export function ChannelTimeline({
  channelId,
  events,
  focusDate,
  onEventClick,
  onEventFocus,
}: ChannelTimelineProps) {
  const router = useRouter()
  const focusedCardRef = useRef<HTMLDivElement>(null)
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  
  // Find focused event index
  const focusedIndex = focusDate
    ? events.findIndex((e) => e.date === focusDate)
    : -1
  
  // Scroll to focused card on mount/update
  useEffect(() => {
    if (focusedCardRef.current && focusedIndex >= 0) {
      focusedCardRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
      setSelectedIndex(focusedIndex)
    }
  }, [focusedIndex])
  
  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (events.length === 0) return
      
      const currentIndex = selectedIndex ?? focusedIndex
      if (currentIndex < 0) return
      
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        const nextIndex = Math.min(currentIndex + 1, events.length - 1)
        const nextEvent = events[nextIndex]
        if (nextEvent) {
          setSelectedIndex(nextIndex)
          router.push(`/mcrb/channel/${channelId}?focus=${nextEvent.date}`, {
            scroll: false,
          })
          onEventFocus(nextEvent.id)
        }
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        const prevIndex = Math.max(currentIndex - 1, 0)
        const prevEvent = events[prevIndex]
        if (prevEvent) {
          setSelectedIndex(prevIndex)
          router.push(`/mcrb/channel/${channelId}?focus=${prevEvent.date}`, {
            scroll: false,
          })
          onEventFocus(prevEvent.id)
        }
      } else if (e.key === 'Enter' && currentIndex >= 0) {
        e.preventDefault()
        const event = events[currentIndex]
        if (event) {
          onEventClick(event.id)
        }
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        router.push('/mcrb/overview')
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [events, selectedIndex, focusedIndex, channelId, router, onEventClick, onEventFocus])
  
  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div className="text-6xl mb-4 opacity-50">📅</div>
        <h2 className="text-xl font-semibold mb-2 text-dark-text-muted">
          暂无排播事件
        </h2>
        <p className="text-sm text-dark-text-muted">
          当前时间窗口内没有排播计划
        </p>
      </div>
    )
  }
  
  return (
    <div className="space-y-4">
      {events.map((event, index) => {
        const completeness = calculateCompleteness(event)
        const color = getStatusColor(event.status, completeness)
        const isFocused = event.date === focusDate
        const isSelected = index === selectedIndex || (selectedIndex === null && isFocused)
        
        return (
          <motion.div
            key={event.id}
            ref={isFocused ? focusedCardRef : null}
            layoutId={isSelected ? `event-${event.id}` : undefined}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="relative"
          >
            <div
              className={`rounded-xl border-2 transition-all cursor-pointer ${
                isSelected
                  ? 'ring-2 ring-primary shadow-lg scale-[1.02]'
                  : 'hover:scale-[1.01] hover:shadow-md'
              }`}
              style={{
                backgroundColor: isSelected ? color.base : 'transparent',
                borderColor: isSelected ? color.border : 'var(--border-color)',
                opacity: isSelected ? color.opacity.bg : 1,
              }}
              onClick={() => {
                setSelectedIndex(index)
                onEventClick(event.id)
              }}
            >
              <div className="p-6">
                {/* Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-dark-text mb-1">
                      {event.title}
                    </h3>
                    <div className="flex items-center gap-4 text-sm text-dark-text-muted">
                      <div className="flex items-center gap-1.5">
                        <Calendar className="w-4 h-4" />
                        <span>{formatDate(event.date)}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-4 h-4" />
                        <span>{formatDuration(event.durationSec)}</span>
                      </div>
                    </div>
                  </div>
                  
                  {/* Status badge */}
                  <div
                    className="px-3 py-1 rounded-lg text-xs font-semibold"
                    style={{
                      backgroundColor: color.base,
                      color: color.text,
                      opacity: color.opacity.bg,
                    }}
                  >
                    {event.status}
                  </div>
                </div>
                
                {/* Assets completeness */}
                <div className="flex items-center gap-2 mb-3">
                  {['cover', 'audio', 'description', 'captions'].map((assetType, i) => {
                    const hasAsset = !!event.assets[assetType as keyof typeof event.assets]
                    return (
                      <div
                        key={assetType}
                        className={`w-2 h-2 rounded-full ${
                          hasAsset ? 'bg-green-500' : 'bg-dark-border'
                        }`}
                        title={assetType}
                      />
                    )
                  })}
                  <span className="text-xs text-dark-text-muted ml-1">
                    {completeness === 'complete'
                      ? '完整'
                      : completeness === 'partial'
                      ? '部分'
                      : '缺失'}
                  </span>
                </div>
                
                {/* Issues */}
                {event.issues.length > 0 && (
                  <div className="flex items-start gap-2 p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                    <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="text-xs text-red-400 font-medium mb-1">
                        {event.issues.length} 个问题
                      </p>
                      {event.issues.slice(0, 2).map((issue, i) => (
                        <p key={i} className="text-xs text-red-300/80">
                          {issue}
                        </p>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* KPIs */}
                {event.kpis && (
                  <div className="mt-3 pt-3 border-t border-dark-border">
                    <div className="flex items-center gap-4 text-xs text-dark-text-muted">
                      {event.kpis.successRate !== undefined && (
                        <span>成功率: {Math.round(event.kpis.successRate * 100)}%</span>
                      )}
                      {event.kpis.lastRunAt && (
                        <span>
                          最后运行:{' '}
                          {new Date(event.kpis.lastRunAt).toLocaleDateString('zh-CN')}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}
