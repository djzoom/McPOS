'use client'

import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { type ScheduleEvent } from '@/stores/scheduleStore'
import { type DateRange } from '@/stores/scheduleStore'
import { getStatusColor, type AssetCompleteness } from '@/lib/designTokens'
import { CellTooltip } from './CellTooltip'

interface OverviewGridProps {
  channels: string[]
  dateRange: DateRange
  events: ScheduleEvent[]
  onCellClick: (channelId: string, date: string) => void
}

/**
 * Generate date array for the range
 */
function generateDates(dateRange: DateRange): string[] {
  const dates: string[] = []
  const start = new Date(dateRange.from)
  const end = new Date(dateRange.to)
  
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    dates.push(d.toISOString().split('T')[0])
  }
  
  return dates
}

/**
 * Group events by channel and date
 */
function groupEvents(events: ScheduleEvent[]): Record<string, Record<string, ScheduleEvent[]>> {
  const grouped: Record<string, Record<string, ScheduleEvent[]>> = {}
  
  events.forEach((event) => {
    if (!grouped[event.channelId]) {
      grouped[event.channelId] = {}
    }
    if (!grouped[event.channelId][event.date]) {
      grouped[event.channelId][event.date] = []
    }
    grouped[event.channelId][event.date].push(event)
  })
  
  return grouped
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

export function OverviewGrid({
  channels,
  dateRange,
  events,
  onCellClick,
}: OverviewGridProps) {
  const dates = useMemo(() => generateDates(dateRange), [dateRange])
  const groupedEvents = useMemo(() => groupEvents(events), [events])
  
  // Virtual scrolling: render visible columns only (for large date ranges)
  // For now, render all dates (optimize later if needed)
  
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        {/* Header: Dates */}
        <thead className="sticky top-0 z-10 bg-dark-bg-secondary">
          <tr>
            <th className="sticky left-0 z-20 bg-dark-bg-secondary border-r border-dark-border px-4 py-3 text-left text-sm font-semibold text-dark-text-muted min-w-[120px]">
              频道 / 日期
            </th>
            {dates.map((date) => {
              const dateObj = new Date(date)
              const dayOfWeek = dateObj.toLocaleDateString('zh-CN', { weekday: 'short' })
              const day = dateObj.getDate()
              
              return (
                <th
                  key={date}
                  className="px-2 py-3 text-center text-xs font-medium text-dark-text-muted border-r border-dark-border min-w-[60px]"
                >
                  <div>{dayOfWeek}</div>
                  <div className="text-lg font-semibold">{day}</div>
                </th>
              )
            })}
          </tr>
        </thead>
        
        {/* Body: Channels × Dates */}
        <tbody>
          {channels.map((channelId) => {
            const channelEvents = groupedEvents[channelId] || {}
            
            return (
              <tr key={channelId} className="border-b border-dark-border">
                {/* Channel name column (sticky) */}
                <td className="sticky left-0 z-10 bg-dark-bg-secondary border-r border-dark-border px-4 py-3 font-medium text-dark-text">
                  {channelId}
                </td>
                
                {/* Date cells */}
                {dates.map((date) => {
                  const cellEvents = channelEvents[date] || []
                  const primaryEvent = cellEvents[0] // Use first event if multiple
                  
                  if (!primaryEvent) {
                    // Empty cell
                    return (
                      <td
                        key={date}
                        className="h-16 px-1 border-r border-dark-border bg-dark-bg-primary"
                      />
                    )
                  }
                  
                  const completeness = calculateCompleteness(primaryEvent)
                  const color = getStatusColor(primaryEvent.status, completeness)
                  const hasMultiple = cellEvents.length > 1
                  
                  return (
                    <td
                      key={date}
                      className="h-16 px-1 border-r border-dark-border relative group"
                    >
                      <CellTooltip event={primaryEvent} count={cellEvents.length}>
                        <motion.button
                          layoutId={`event-${primaryEvent.id}`}
                          onClick={() => onCellClick(channelId, date)}
                          className="w-full h-full rounded-lg transition-all hover:scale-105 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-primary/50"
                          style={{
                            backgroundColor: color.base,
                            opacity: color.opacity.bg,
                            border: `1px solid ${color.border}`,
                            borderOpacity: color.opacity.border,
                          }}
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.98 }}
                        >
                          <div className="flex flex-col items-center justify-center h-full px-1">
                            {hasMultiple && (
                              <span className="text-xs font-semibold text-white/80 mb-0.5">
                                +{cellEvents.length}
                              </span>
                            )}
                            <div
                              className="w-2 h-2 rounded-full"
                              style={{ backgroundColor: color.text }}
                            />
                          </div>
                        </motion.button>
                      </CellTooltip>
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
