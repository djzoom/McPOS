'use client'

import React, { use, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useScheduleStore } from '@/stores/scheduleStore'
import { ChannelTimeline } from '@/components/mcrb/ChannelTimeline'
import { TaskPanel } from '@/components/mcrb/TaskPanel'
import { useScheduleWindow } from '@/hooks/useScheduleWindow'

export default function ChannelPage({
  params,
}: {
  params: Promise<{ channelId: string }>
}) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const resolvedParams = use(params)
  
  const channelId = resolvedParams.channelId
  const focusDate = searchParams.get('focus')
  
  const setFocus = useScheduleStore((state) => state.setFocus)
  const selectedChannel = useScheduleStore((state) => state.selectedChannel)
  const visibleEvents = useScheduleStore((state) => state.visibleEvents(channelId))
  const { dateRange } = useScheduleWindow()
  
  // Set focus from URL on mount/update
  useEffect(() => {
    if (channelId && focusDate) {
      setFocus(channelId, focusDate)
    } else if (channelId) {
      setFocus(channelId, null)
    }
  }, [channelId, focusDate, setFocus])
  
  // Filter events for this channel
  const channelEvents = visibleEvents.filter((e) => e.channelId === channelId)
  
  // Get focused event
  const focusDateStr = focusDate || null
  const focusedEvent = focusDateStr
    ? channelEvents.find((e) => e.date === focusDateStr)
    : null
  
  const [selectedEventId, setSelectedEventId] = useState<string | null>(
    focusedEvent?.id || null
  )
  
  const selectedEvent = selectedEventId
    ? channelEvents.find((e) => e.id === selectedEventId)
    : null
  
  // Update selected event when focus date changes
  useEffect(() => {
    if (focusedEvent) {
      setSelectedEventId(focusedEvent.id)
    }
  }, [focusedEvent])
  
  return (
    <div className="max-w-[1920px] mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">频道看板: {channelId}</h1>
        <p className="text-dark-text-muted">
          {dateRange.from} 至 {dateRange.to}
        </p>
      </div>
      
      {/* Timeline */}
      <div className="grid grid-cols-[1fr_auto] gap-6">
        <ChannelTimeline
          channelId={channelId}
          events={channelEvents}
          focusDate={focusDateStr}
          onEventClick={(eventId) => {
            setSelectedEventId(eventId)
            const event = channelEvents.find((e) => e.id === eventId)
            if (event) {
              router.push(`/mcrb/channel/${channelId}?focus=${event.date}`, {
                scroll: false,
              })
            }
          }}
          onEventFocus={(eventId) => {
            setSelectedEventId(eventId)
          }}
        />
        
        {/* Task Panel (drawer) */}
        {selectedEvent && (
          <TaskPanel
            event={selectedEvent}
            isOpen={!!selectedEvent}
            onClose={() => {
              setSelectedEventId(null)
            }}
          />
        )}
      </div>
    </div>
  )
}
