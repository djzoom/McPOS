/**
 * Schedule Store (Zustand)
 * 
 * Single Source of Truth (SSOT) for all schedule board data.
 * Manages channels, events, focus state, and date ranges.
 */
import { create } from 'zustand'
import { normalizeStatus, type ScheduleEventStatus } from '@/lib/designTokens'

/**
 * ScheduleEvent - Unified event model for Schedule Board
 */
export interface ScheduleEvent {
  id: string
  channelId: string
  date: string // ISO date string (YYYY-MM-DD)
  title: string
  durationSec: number
  bpm: number | null
  assets: {
    cover: string | null
    audio: string | null
    description: string | null
    captions: string | null
  }
  status: ScheduleEventStatus
  issues: string[]
  kpis?: {
    successRate?: number
    lastRunAt?: string
  }
}

/**
 * Channel summary
 */
export interface ChannelSummary {
  id: string
  name: string
  isActive: boolean
  eventCount: number
  nextSchedule?: string
}

/**
 * Date range for schedule window
 */
export interface DateRange {
  from: string // ISO date (YYYY-MM-DD)
  to: string // ISO date (YYYY-MM-DD)
}

/**
 * ScheduleStore state interface
 */
interface ScheduleStore {
  // Core data
  channels: string[] // Channel IDs
  events: Record<string, ScheduleEvent[]> // Events grouped by channelId
  selectedChannel: string | null
  focusDate: string | null // ISO date (YYYY-MM-DD)
  dateRange: DateRange
  
  // Derived selectors (computed)
  visibleEvents: (channelId?: string) => ScheduleEvent[]
  channelSummaries: () => ChannelSummary[]
  statusCounts: (channelId?: string) => Record<ScheduleEventStatus, number>
  
  // Actions
  hydrate: (data: {
    channels?: string[]
    events?: ScheduleEvent[]
    dateRange?: DateRange
  }) => void
  setDateRange: (range: DateRange | { days: number }) => void
  setFocus: (channelId: string | null, date: string | null) => void
  setSelectedChannel: (channelId: string | null) => void
  upsertEvents: (channelId: string, events: ScheduleEvent[]) => void
  patchEvent: (eventId: string, updates: Partial<ScheduleEvent>) => void
  markEventStatus: (eventId: string, status: ScheduleEventStatus) => void
}

/**
 * Calculate date range from number of days (from today)
 */
function calculateDateRange(days: number): DateRange {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  
  const to = new Date(today)
  to.setDate(to.getDate() + days - 1)
  
  return {
    from: today.toISOString().split('T')[0],
    to: to.toISOString().split('T')[0],
  }
}

/**
 * Clamp focus date to current date range
 */
function clampFocusDate(focusDate: string | null, dateRange: DateRange): string | null {
  if (!focusDate) return null
  
  if (focusDate < dateRange.from) return dateRange.from
  if (focusDate > dateRange.to) return dateRange.to
  
  return focusDate
}

export const useScheduleStore = create<ScheduleStore>((set, get) => ({
  // Initial state
  channels: [],
  events: {},
  selectedChannel: null,
  focusDate: null,
  dateRange: calculateDateRange(14), // Default: 14 days
  
  // Derived selectors
  visibleEvents: (channelId) => {
    const state = get()
    const range = state.dateRange
    
    // Filter by channel if specified
    const channelEvents = channelId
      ? state.events[channelId] || []
      : Object.values(state.events).flat()
    
    // Filter by date range
    return channelEvents.filter((event) => {
      return event.date >= range.from && event.date <= range.to
    })
  },
  
  channelSummaries: () => {
    const state = get()
    const summaries: ChannelSummary[] = []
    
    for (const channelId of state.channels) {
      const events = state.events[channelId] || []
      const visibleEvents = events.filter(
        (e) => e.date >= state.dateRange.from && e.date <= state.dateRange.to
      )
      
      // Find next scheduled event
      const futureEvents = visibleEvents
        .filter((e) => e.date >= new Date().toISOString().split('T')[0])
        .sort((a, b) => a.date.localeCompare(b.date))
      
      summaries.push({
        id: channelId,
        name: channelId, // TODO: Fetch actual channel name
        isActive: visibleEvents.length > 0,
        eventCount: visibleEvents.length,
        nextSchedule: futureEvents[0]?.date,
      })
    }
    
    return summaries
  },
  
  statusCounts: (channelId) => {
    const state = get()
    const events = state.visibleEvents(channelId)
    const counts: Record<ScheduleEventStatus, number> = {
      draft: 0,
      planned: 0,
      rendering: 0,
      ready: 0,
      uploaded: 0,
      verified: 0,
      failed: 0,
    }
    
    events.forEach((event) => {
      counts[event.status] = (counts[event.status] || 0) + 1
    })
    
    return counts
  },
  
  // Actions
  hydrate: (data) =>
    set((state) => {
      const newState: Partial<ScheduleStore> = {}
      
      if (data.channels) {
        newState.channels = data.channels
      }
      
      if (data.events) {
        // Group events by channelId
        const grouped: Record<string, ScheduleEvent[]> = {}
        data.events.forEach((event) => {
          if (!grouped[event.channelId]) {
            grouped[event.channelId] = []
          }
          grouped[event.channelId].push(event)
        })
        newState.events = { ...state.events, ...grouped }
      }
      
      if (data.dateRange) {
        newState.dateRange = data.dateRange
        // Clamp focus date to new range
        if (state.focusDate) {
          newState.focusDate = clampFocusDate(state.focusDate, data.dateRange)
        }
      }
      
      return { ...state, ...newState }
    }),
  
  setDateRange: (range) =>
    set((state) => {
      const dateRange = 'days' in range ? calculateDateRange(range.days) : range
      const focusDate = clampFocusDate(state.focusDate, dateRange)
      
      return {
        ...state,
        dateRange,
        focusDate,
      }
    }),
  
  setFocus: (channelId, date) =>
    set((state) => {
      const focusDate = date ? clampFocusDate(date, state.dateRange) : null
      return {
        ...state,
        selectedChannel: channelId,
        focusDate,
      }
    }),
  
  setSelectedChannel: (channelId) =>
    set((state) => ({
      ...state,
      selectedChannel: channelId,
    })),
  
  upsertEvents: (channelId, newEvents) =>
    set((state) => {
      const existing = state.events[channelId] || []
      const existingIds = new Set(existing.map((e) => e.id))
      
      // Merge: update existing, add new
      const merged = [...existing]
      newEvents.forEach((event) => {
        const index = merged.findIndex((e) => e.id === event.id)
        if (index >= 0) {
          merged[index] = event
        } else {
          merged.push(event)
        }
      })
      
      return {
        ...state,
        events: {
          ...state.events,
          [channelId]: merged,
        },
      }
    }),
  
  patchEvent: (eventId, updates) =>
    set((state) => {
      const newEvents: Record<string, ScheduleEvent[]> = {}
      
      Object.entries(state.events).forEach(([channelId, events]) => {
        newEvents[channelId] = events.map((event) =>
          event.id === eventId ? { ...event, ...updates } : event
        )
      })
      
      return {
        ...state,
        events: newEvents,
      }
    }),
  
  markEventStatus: (eventId, status) =>
    get().patchEvent(eventId, { status }),
}))
