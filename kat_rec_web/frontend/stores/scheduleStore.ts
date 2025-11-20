/**
 * Schedule Store (Zustand)
 * 
 * Single Source of Truth (SSOT) for all schedule board data.
 * Manages channels, events, focus state, and date ranges.
 */
import { create } from 'zustand'
import { persist, devtools } from 'zustand/middleware'
import type { StageKey, StageStatusMap } from '@/types/stage'
import { EMPTY_STAGE_STATUS, STAGE_KEYS } from '@/types/stage'
import { mapRunbookStageToStageKey } from '@/utils/runbookStageMapper'

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
    cover: string | null  // Generated cover image (_cover.png) - shown in card and drawer
    audio: string | null
    description: string | null
    captions: string | null
    // Extended fields for video and upload status
    timeline_csv?: string | null
    youtube_title?: string | null  // YouTube title file path (different from album title)
    video?: string | null
    video_path?: string | null
    uploaded_at?: string | null
    uploaded?: boolean
    verified_at?: string | null
    verified?: boolean
  }
  image_path?: string | null  // Original source image from library - shown in drawer only
  issues: string[]
  kpis?: {
    successRate?: number
    lastRunAt?: string
  }
  hasOutputFolder?: boolean // STEP 5: Output folder awareness for grid coloring
  playlistPath?: string | null // Playlist file path for progress calculation
  // Asset existence flags (from backend file system checks)
  audio_exists?: boolean
  description_exists?: boolean
  captions_exists?: boolean
  cover_exists?: boolean
  youtube_title_path?: string | null  // YouTube title file path (different from album title)
  youtube_title_exists?: boolean
  gridProgress?: {
    lastStage: string | null // Last known stage (e.g., "playlist", "remix", "render")
    lastStageTimestamp: number // Timestamp of last stage update (for preventing flicker on reconnect)
    stageHistory: Array<{ stage: string; timestamp: number; progress: number; fileProgress?: any }> // Stage history for smooth animations
    fileProgress?: {
      total_files: number
      completed_files: number
      files: Record<string, {
        status: 'pending' | 'generating' | 'completed' | 'failed'
        progress: number
        started_at?: string
        completed_at?: string
        error?: string
      }>
    } | null // File-level progress information
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
 * Batch Generation Status
 */
export interface BatchGenerationStatus {
  runId: string
  channelId: string
  totalEpisodes: number
  completedEpisodes: number
  failedEpisodes: number
  currentEpisode?: string | null
  currentStage?: string | null
  progress: number // 0-100
  status: 'running' | 'completed' | 'failed'
  startedAt?: string
  completedAt?: string
  error?: string
}

/**
 * Minimal runbook state used when calculating stage status selectors.
 */
export interface RunbookStageSnapshot {
  currentStage: string | null
  episodeId: string | null
  failedStage?: string | null
  errorMessage?: string | null
}

/**
 * ScheduleStore state interface
 */
interface ScheduleStore {
  // Core data
  channels: string[] // Channel IDs
  events: Record<string, ScheduleEvent[]> // Events grouped by channelId
  eventsById: Record<string, ScheduleEvent> // Quick lookup by eventId
  eventChannelIndex: Record<string, string> // eventId -> channelId
  selectedChannel: string | null
  focusDate: string | null // ISO date (YYYY-MM-DD)
  dateRange: DateRange
  workCursorDate: Record<string, string | null> // Channel ID -> work cursor date (YYYY-MM-DD)
  
  // Batch generation status
  batchGenerationStatus: BatchGenerationStatus | null
  
  // Channel state tracking (void → in_production)
  channelState: Record<string, 'void' | 'in_production'>
  
  // Last known stages cache for GridProgress resilience
  lastKnownStages: Record<string, { stage: string; timestamp: number }>
  
  // Runbook state cache (merged from runbookStore)
  // Maps episodeId to runbook state snapshot for unified state management
  runbookSnapshots: Record<string, RunbookStageSnapshot>
  
  // Derived selectors (computed)
  visibleEvents: (channelId?: string) => ScheduleEvent[]
  visibleEventIds: (channelId?: string) => string[]
  getEventById: (eventId: string) => ScheduleEvent | undefined
  channelSummaries: () => ChannelSummary[]
  
  // Unified selector: Get event with runbook state
  getEventWithRunbook: (eventId: string) => (ScheduleEvent & { runbook: RunbookStageSnapshot | null }) | undefined
  
  // Actions
  hydrate: (data: {
    channels?: string[]
    events?: ScheduleEvent[]
    dateRange?: DateRange
  }) => void
  reset: (channelId?: string) => void // Reset store (optionally for specific channel)
  setDateRange: (range: DateRange | { days: number }) => void
  setFocus: (channelId: string | null, date: string | null) => void
  setSelectedChannel: (channelId: string | null) => void
  upsertEvents: (channelId: string, events: ScheduleEvent[]) => void
  patchEvent: (eventId: string, updates: Partial<ScheduleEvent>) => void
  
  // Batch generation actions
  setBatchGenerationStatus: (status: BatchGenerationStatus | null) => void
  updateBatchGenerationProgress: (updates: Partial<BatchGenerationStatus>) => void
  
  // Channel state actions
  setChannelState: (channelId: string, state: 'void' | 'in_production') => void
  
  // Last known stages actions
  setLastKnownStage: (eventId: string, stage: string) => void
  getLastKnownStage: (eventId: string) => { stage: string; timestamp: number } | null
  
  // Runbook snapshot actions (merged from runbookStore)
  setRunbookSnapshot: (episodeId: string, snapshot: RunbookStageSnapshot) => void
  clearRunbookSnapshot: (episodeId: string) => void
  getRunbookSnapshot: (episodeId: string) => RunbookStageSnapshot | null
  
  // Work cursor actions
  setWorkCursorDate: (channelId: string, cursorDate: string | null) => void
  getWorkCursorDate: (channelId: string) => string | null
}

/**
 * Calculate date range from number of days (from today)
 * Always starts from today, never includes past dates
 */
function calculateDateRange(days: number): DateRange {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  
  // Ensure we use local date, not UTC, to avoid timezone issues
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  const fromDate = `${year}-${month}-${day}`
  
  const to = new Date(today)
  to.setDate(to.getDate() + days - 1)
  const toYear = to.getFullYear()
  const toMonth = String(to.getMonth() + 1).padStart(2, '0')
  const toDay = String(to.getDate()).padStart(2, '0')
  const toDate = `${toYear}-${toMonth}-${toDay}`
  
  return {
    from: fromDate,
    to: toDate,
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

function buildEventIndexes(eventsMap: Record<string, ScheduleEvent[]>): {
  eventsById: Record<string, ScheduleEvent>
  eventChannelIndex: Record<string, string>
} {
  const eventsById: Record<string, ScheduleEvent> = {}
  const eventChannelIndex: Record<string, string> = {}
  
  Object.entries(eventsMap).forEach(([channelId, channelEvents]) => {
    channelEvents.forEach((event) => {
      eventsById[event.id] = event
      eventChannelIndex[event.id] = channelId
    })
  })
  
  return { eventsById, eventChannelIndex }
}

function mergeEventData(
  event: ScheduleEvent,
  updates: Partial<ScheduleEvent>
): ScheduleEvent {
  if (!updates) return event
  
  if (updates.assets && event.assets) {
    return {
      ...event,
      ...updates,
      assets: {
        ...event.assets,
        ...updates.assets,
      },
    }
  }
  
  return { ...event, ...updates }
}

export const useScheduleStore = create<ScheduleStore>()(
  devtools(
    persist(
      (set, get) => ({
  // Initial state
  channels: [],
  events: {},
  eventsById: {},
  eventChannelIndex: {},
  selectedChannel: null,
  focusDate: null,
    dateRange: calculateDateRange(365), // Default: 365 days (1 year)
  batchGenerationStatus: null,
  channelState: {},
  lastKnownStages: {},
  runbookSnapshots: {}, // Runbook state cache (merged from runbookStore)
  workCursorDate: {}, // Channel ID -> work cursor date (YYYY-MM-DD)
  
  // Derived selectors (optimized with memoization)
  visibleEvents: (channelId) => {
    const ids = get().visibleEventIds(channelId)
    return ids
      .map((id) => get().eventsById[id])
      .filter((event): event is ScheduleEvent => Boolean(event))
  },
  visibleEventIds: (channelId) => {
    const state = get()
    const range = state.dateRange
    const sourceLists = channelId
      ? [state.events[channelId] || []]
      : Object.values(state.events)
    
    // Get work cursor date for filtering
    const cursorDate = channelId 
      ? state.workCursorDate[channelId] 
      : (Object.values(state.workCursorDate)[0] || null)
    
    const ids: string[] = []
    sourceLists.forEach((list) => {
      list.forEach((event) => {
        // Filter by date range
        if (event.date < range.from || event.date > range.to) {
          return
        }
        
        // Filter by work cursor date: only show events from cursor date onwards
        if (cursorDate && event.date < cursorDate) {
          return
        }
        
        ids.push(event.id)
      })
    })
    return ids
  },
  getEventById: (eventId) => get().eventsById[eventId],
  
  // Unified selector: Get event with runbook state
  getEventWithRunbook: (eventId) => {
    const event = get().eventsById[eventId]
    if (!event) return undefined
    const runbook = get().runbookSnapshots[eventId] || null
    return {
      ...event,
      runbook,
    }
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
  
  // Actions
  hydrate: (data) =>
    set((state) => {
      const newState: Partial<ScheduleStore> = {}
      let shouldReindex = false
      
      if (data.channels) {
        newState.channels = data.channels
      }
      
      if (data.events !== undefined) {
        shouldReindex = true
        // Group events by channelId
        const grouped: Record<string, ScheduleEvent[]> = {}
        data.events.forEach((event) => {
          if (!grouped[event.channelId]) {
            grouped[event.channelId] = []
          }
          grouped[event.channelId].push(event)
        })
        
        // If events array is empty, replace (not merge) to ensure clean state
        // If events array has data, merge with existing to preserve WebSocket updates
        const channelsToUpdate = data.channels && data.channels.length > 0
          ? data.channels
          : Object.keys(grouped)

        const mergedEvents = { ...state.events }

        // Merge events instead of replacing to preserve WebSocket incremental updates
        // This ensures that WebSocket updates (via patchEvent) are not lost when React Query refetches
        channelsToUpdate.forEach((channelId) => {
          const existingEvents = mergedEvents[channelId] || []
          const newEvents = grouped[channelId] || []
          
          // Create a map of existing events by ID for efficient lookup
          const existingMap = new Map(existingEvents.map(e => [e.id, e]))
          
          // Update existing events and add new ones
          const merged: ScheduleEvent[] = []
          const processedIds = new Set<string>()
          
          // First, add/update events from new data (from API)
          newEvents.forEach((newEvent) => {
            const existing = existingMap.get(newEvent.id)
            if (existing) {
              // Merge: preserve WebSocket updates (gridProgress, runbook snapshots, etc.)
              // but update with latest API data (assets, paths, etc.)
              merged.push({
                ...existing,
                ...newEvent,
                // Preserve WebSocket-specific updates that may not be in API response
                gridProgress: existing.gridProgress || newEvent.gridProgress,
                kpis: existing.kpis || newEvent.kpis,
              })
            } else {
              merged.push(newEvent)
            }
            processedIds.add(newEvent.id)
          })
          
          // IMPORTANT: Do NOT preserve existing events that aren't in new data
          // This ensures deleted events are removed from the store
          // If backend deleted an event, it won't be in newEvents, so we should remove it
          // This fixes the "+2" display issue where deleted events were still showing
          
          mergedEvents[channelId] = merged
        })

        newState.events = mergedEvents
        
        // Debug logging
        if (process.env.NODE_ENV === 'development') {
          // Import logger dynamically to avoid circular dependencies
          import('@/lib/logger').then(({ logger }) => {
            logger.debug('[ScheduleStore] hydrate events:', {
              inputEventsCount: data.events?.length || 0,
              groupedChannels: Object.keys(grouped),
              groupedEventCounts: Object.fromEntries(
                Object.entries(grouped).map(([ch, evs]) => [ch, evs.length])
              ),
              finalEvents: Object.fromEntries(
                Object.entries(newState.events || state.events).map(([ch, evs]) => [ch, evs.length])
              ),
            })
          }).catch(() => {
            // Fallback if logger not available
          })
        }
      }
      
      if (data.dateRange) {
        newState.dateRange = data.dateRange
        // Clamp focus date to new range
        if (state.focusDate) {
          newState.focusDate = clampFocusDate(state.focusDate, data.dateRange)
        }
      }
      
      const mergedState = { ...state, ...newState }
      if (shouldReindex) {
        const { eventsById, eventChannelIndex } = buildEventIndexes(mergedState.events)
        mergedState.eventsById = eventsById
        mergedState.eventChannelIndex = eventChannelIndex
      }
      return mergedState
    }),
  
  reset: (channelId) =>
    set((state) => {
      if (channelId) {
        // Reset specific channel
        const newEvents = { ...state.events }
        delete newEvents[channelId]
        const newChannelState = { ...state.channelState }
        newChannelState[channelId] = 'void' // Explicitly set to void
        
        // Clear runbook snapshots for events in this channel
        const newRunbookSnapshots = { ...state.runbookSnapshots }
        const channelEvents = state.events[channelId] || []
        channelEvents.forEach((event) => {
          delete newRunbookSnapshots[event.id]
        })
        
        const { eventsById, eventChannelIndex } = buildEventIndexes(newEvents)
        return {
          ...state,
          events: newEvents,
          eventsById,
          eventChannelIndex,
          channelState: newChannelState,
          runbookSnapshots: newRunbookSnapshots,
        }
      } else {
        // Reset all channels
        return {
          ...state,
          events: {},
          eventsById: {},
          eventChannelIndex: {},
          channels: [],
          selectedChannel: null,
          focusDate: null,
          channelState: {},
          runbookSnapshots: {}, // Reset runbook snapshots on reset
        }
      }
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
      // Merge: update existing, add new
      const merged = [...existing]
      const indexById = new Map(existing.map((event, idx) => [event.id, idx]))
      newEvents.forEach((event) => {
        const index = indexById.get(event.id)
        if (index !== undefined && index >= 0) {
          merged[index] = event
        } else {
          merged.push(event)
          indexById.set(event.id, merged.length - 1)
        }
      })
      
      const eventsById = { ...state.eventsById }
      const eventChannelIndex = { ...state.eventChannelIndex }
      newEvents.forEach((event) => {
        eventsById[event.id] = event
        eventChannelIndex[event.id] = channelId
      })
      
      return {
        ...state,
        events: {
          ...state.events,
          [channelId]: merged,
        },
        eventsById,
        eventChannelIndex,
      }
    }),
  
  patchEvent: (eventId, updates) =>
    set((state) => {
      const isDev = process.env.NODE_ENV === 'development' || (typeof window !== 'undefined' && window.location.search.includes('debug=true'))
      
      // ✅ 添加监控：状态一致性检查（高优先级，仅开发环境）
      const beforeState = state.eventsById[eventId]
      
      const channelId = state.eventChannelIndex[eventId]
      if (!channelId) {
        // If event not found in index, try to find it in eventsById
        const existingEvent = state.eventsById[eventId]
        if (existingEvent) {
          // Event exists but index is missing - rebuild index for this event
          const updatedEvent = mergeEventData(existingEvent, updates)
          const inferredChannelId = existingEvent.channelId
          if (inferredChannelId) {
            const channelEvents = state.events[inferredChannelId] || []
            const updatedChannelEvents = channelEvents.map((event) =>
              event.id === eventId ? updatedEvent : event
            )
            
            // ✅ 状态一致性检查
            if (isDev && beforeState) {
              const inconsistencies: string[] = []
              
              // 检查 assets 是否丢失
              if (beforeState.assets && !updatedEvent.assets) {
                inconsistencies.push('assets lost')
              }
              
              // 检查 gridProgress 是否倒退
              const beforeProgress = beforeState.gridProgress?.lastStageTimestamp || 0
              const afterProgress = updatedEvent.gridProgress?.lastStageTimestamp || 0
              if (afterProgress < beforeProgress) {
                inconsistencies.push(`gridProgress timestamp regressed: ${beforeProgress} -> ${afterProgress}`)
              }
              
              if (inconsistencies.length > 0) {
                console.warn('[StateUpdate] State inconsistency detected:', {
                  eventId,
                  inconsistencies,
                  before: beforeState,
                  after: updatedEvent,
                })
              }
            }
            
            return {
              ...state,
              events: {
                ...state.events,
                [inferredChannelId]: updatedChannelEvents,
              },
              eventsById: {
                ...state.eventsById,
                [eventId]: updatedEvent,
              },
              eventChannelIndex: {
                ...state.eventChannelIndex,
                [eventId]: inferredChannelId,
              },
            }
          }
        }
        return state
      }
      
      const channelEvents = state.events[channelId] || []
      let updatedEvent: ScheduleEvent | null = null
      const updatedChannelEvents = channelEvents.map((event) => {
        if (event.id !== eventId) return event
        updatedEvent = mergeEventData(event, updates)
        return updatedEvent
      })
      
      if (!updatedEvent) {
        return state
      }
      
      // ✅ 状态一致性检查
      if (isDev && beforeState) {
        const inconsistencies: string[] = []
        
        // 检查 assets 是否丢失
        if (beforeState.assets && !updatedEvent.assets) {
          inconsistencies.push('assets lost')
        }
        
        // 检查 gridProgress 是否倒退
        const beforeProgress = beforeState.gridProgress?.lastStageTimestamp || 0
        const afterProgress = updatedEvent.gridProgress?.lastStageTimestamp || 0
        if (afterProgress < beforeProgress) {
          inconsistencies.push(`gridProgress timestamp regressed: ${beforeProgress} -> ${afterProgress}`)
        }
        
        // 检查关键资产字段是否丢失
        if (beforeState.assets?.audio && !updatedEvent.assets?.audio) {
          inconsistencies.push('audio asset lost')
        }
        if (beforeState.assets?.video && !updatedEvent.assets?.video) {
          inconsistencies.push('video asset lost')
        }
        if (beforeState.assets?.timeline_csv && !updatedEvent.assets?.timeline_csv) {
          inconsistencies.push('timeline_csv asset lost')
        }
        
        if (inconsistencies.length > 0) {
          console.warn('[StateUpdate] State inconsistency detected:', {
            eventId,
            inconsistencies,
            before: beforeState,
            after: updatedEvent,
          })
        }
      }
      
      // Update lastKnownStages if stage-related updates are present
      // Check if updates contain assets that indicate stage progression
      let lastKnownStages = { ...state.lastKnownStages }
      const now = Date.now()
      
      // Detect stage from asset updates
      if (updates.assets) {
        if (updates.assets.audio && !state.lastKnownStages[eventId]) {
          // New remix stage detected
          lastKnownStages[eventId] = { stage: 'remix', timestamp: now }
        } else if (updates.assets.video && state.lastKnownStages[eventId]?.stage !== 'render') {
          // Render stage detected
          lastKnownStages[eventId] = { stage: 'render', timestamp: now }
        } else if (updates.assets.verified && state.lastKnownStages[eventId]?.stage !== 'verify') {
          // Verify stage detected
          lastKnownStages[eventId] = { stage: 'verify', timestamp: now }
        }
      }
      
      return {
        ...state,
        events: {
          ...state.events,
          [channelId]: updatedChannelEvents,
        },
        eventsById: {
          ...state.eventsById,
          [eventId]: updatedEvent,
        },
        // Ensure eventChannelIndex is maintained
        eventChannelIndex: {
          ...state.eventChannelIndex,
          [eventId]: channelId,
        },
        lastKnownStages,
      }
    }),
  
  // Batch generation actions
  setBatchGenerationStatus: (status) =>
    set((state) => ({
      ...state,
      batchGenerationStatus: status,
    })),
  
  updateBatchGenerationProgress: (updates) =>
    set((state) => {
      if (!state.batchGenerationStatus) {
        return state
      }
      
      return {
        ...state,
        batchGenerationStatus: {
          ...state.batchGenerationStatus,
          ...updates,
        },
      }
    }),
  
  // Channel state actions
  setChannelState: (channelId, state) =>
    set((currentState) => ({
      ...currentState,
      channelState: {
        ...currentState.channelState,
        [channelId]: state,
      },
    })),
  
  // Last known stages actions
  setLastKnownStage: (eventId, stage) =>
    set((state) => ({
      ...state,
      lastKnownStages: {
        ...state.lastKnownStages,
        [eventId]: {
          stage,
          timestamp: Date.now(),
        },
      },
    })),
  
  getLastKnownStage: (eventId) => {
    const state = get()
    return state.lastKnownStages[eventId] || null
  },
  
  // Runbook snapshot actions (merged from runbookStore)
  setRunbookSnapshot: (episodeId, snapshot) =>
    set((state) => ({
      ...state,
      runbookSnapshots: {
        ...state.runbookSnapshots,
        [episodeId]: snapshot,
      },
    })),
  
  clearRunbookSnapshot: (episodeId) =>
    set((state) => {
      const newSnapshots = { ...state.runbookSnapshots }
      delete newSnapshots[episodeId]
      return {
        ...state,
        runbookSnapshots: newSnapshots,
      }
    }),
  
  getRunbookSnapshot: (episodeId) => {
    const state = get()
    return state.runbookSnapshots[episodeId] || null
  },
  
  // Work cursor actions
  setWorkCursorDate: (channelId, cursorDate) =>
    set((state) => ({
      ...state,
      workCursorDate: {
        ...state.workCursorDate,
        [channelId]: cursorDate,
      },
    })),
  
  getWorkCursorDate: (channelId) => {
    return get().workCursorDate[channelId] || null
  },
      }),
      {
        name: 'schedule-store', // localStorage key
        // 只持久化用户偏好，不持久化数据（events 等）
        partialize: (state) => ({
          dateRange: state.dateRange,
          selectedChannel: state.selectedChannel,
          focusDate: state.focusDate,
        }),
      }
    ),
    { name: 'ScheduleStore' } // Redux DevTools 名称
  )
)

export const createEventSelector =
  (eventId?: string | null) =>
  (state: ScheduleStore): ScheduleEvent | undefined =>
    eventId ? state.eventsById[eventId] : undefined

/**
 * Optimized selector for visible event IDs with memoization support
 * Use with Zustand's shallow comparison for best performance
 */
export const createVisibleEventIdsSelector =
  (channelId?: string) =>
  (state: ScheduleStore): string[] => {
    // Use the store's built-in visibleEventIds which already filters by dateRange
    return state.visibleEventIds(channelId)
  }

/**
 * Selector factory for channel-specific visible event IDs
 * Returns a stable selector function that can be memoized
 */
export const createChannelVisibleEventIdsSelector =
  (channelId: string) =>
  (state: ScheduleStore): string[] => {
    return state.visibleEventIds(channelId)
  }

export const areIdArraysEqual = (a?: string[], b?: string[]): boolean => {
  if (a === b) return true
  if (!a || !b) return false
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return false
  }
  return true
}

export const areStageStatusesEqual = (
  a: StageStatusMap,
  b: StageStatusMap
): boolean => {
  if (a === b) return true
  return STAGE_KEYS.every(
    (key) =>
      a[key].done === b[key].done &&
      a[key].inProgress === b[key].inProgress &&
      a[key].failed === b[key].failed
  )
}

/**
 * Optimized selector for stage status with memoization support
 * Use with areStageStatusesEqual for shallow comparison
 * 
 * @param eventId - Event ID to get status for
 * @param runbookState - Optional runbook state snapshot for real-time progress
 * @returns A selector function that returns StageStatusMap
 */
export const createStageStatusSelector =
  (eventId?: string | null, runbookState?: RunbookStageSnapshot) =>
  (state: ScheduleStore): StageStatusMap => {
    if (!eventId) return EMPTY_STAGE_STATUS
    const event = state.eventsById[eventId]
    if (!event) return EMPTY_STAGE_STATUS
    return calculateStageStatus(event, runbookState)
  }

/**
 * Selector factory for event-specific stage status
 * Returns a stable selector function that can be memoized
 * 
 * @param eventId - Event ID to get status for
 * @returns A selector function that accepts runbookState and returns StageStatusMap
 */
export const createEventStageStatusSelector =
  (eventId: string) =>
  (runbookState?: RunbookStageSnapshot) =>
  (state: ScheduleStore): StageStatusMap => {
    const event = state.eventsById[eventId]
    if (!event) return EMPTY_STAGE_STATUS
    return calculateStageStatus(event, runbookState)
  }

export function calculateStageStatus(
  event: ScheduleEvent,
  runbookState?: RunbookStageSnapshot
): StageStatusMap {
  if (!event) return EMPTY_STAGE_STATUS
  
  const isEventInProgress = runbookState?.episodeId === event.id
  const activeStageKey = isEventInProgress
    ? mapRunbookStageToStageKey(runbookState?.currentStage || null)
    : null
  const failedStageKey = isEventInProgress
    ? mapRunbookStageToStageKey(runbookState?.failedStage || null)
    : null
  
  const isAudioMixed = (
    audioPath: string | null | undefined,
    timelineCsv?: string | null | undefined
  ): boolean => {
    if (!audioPath) return false
    
    // ✅ 严格要求：必须有 timeline_csv 才认为完成
    // timeline_csv 是 remix 阶段的最后一个文件，只有它生成才意味着真正完成
    if (
      timelineCsv &&
      (timelineCsv.includes('_full_mix_timeline.csv') ||
        timelineCsv.endsWith('_full_mix_timeline.csv'))
    ) {
      // 同时验证 audio 路径包含 full_mix.mp3
      return (
        audioPath.includes('_full_mix.mp3') || 
        audioPath.endsWith('_full_mix.mp3')
      )
    }
    
    // ❌ 移除 fallback：不允许仅凭 audio 路径就认为完成
    // 这确保了系统必须等待 timeline_csv 生成才认为 remix 完成
    return false
  }
  
  const hasPlaylist = !!event.playlistPath
  // ✅ 严格要求：必须有 timeline_csv 才认为音频合成完成
  // 移除了 fallback 逻辑，确保系统必须等待 timeline_csv 生成
  const hasAudio = isAudioMixed(
    event.assets.audio,
    event.assets.timeline_csv
  )
  const audioDone = hasAudio
  const coverDone = !!event.assets.cover
  const titleDone = !!event.title
  // ✅ 检查 YouTube title（youtube_title.txt）- 这是第5个文件
  const youtubeTitleDone = !!(event.youtube_title_path || event.assets.youtube_title || event.youtube_title_exists)
  const descriptionDone = !!event.assets.description
  const captionsDone = !!event.assets.captions
  
  // Calculate preparation progress: 7 required assets
  // 1. playlist.csv (playlistDone)
  // 2. cover.png (coverDone)
  // 3. title (titleDone) - episode title
  // 4. youtube_title.txt (youtubeTitleDone) - YouTube title file
  // 5. youtube_description.txt (descriptionDone)
  // 6. youtube.srt (captionsDone)
  // 7. full_mix.mp3 + full_mix_timeline.csv (audioDone)
  const playlistDone = hasPlaylist
  
  // ❌ 移除自动remixStuck检测 - 太激进，会导致正常处理中的episode被误判为失败
  // 后端已经有stuck检测逻辑（plan.py中，如果remix运行超过15分钟且没有输出，会标记为FAILED）
  // 前端只依赖后端的明确失败状态，不进行自动推断
  // const remixStuck = hasPlaylist && !hasAudio && !isEventInProgress
  
  // ✅ 检查视频文件和后续旗标文件都存在
  // render_complete_flag 确保渲染真正完成（文件写入完成、验证通过）
  // 这解决了文件在写入过程中就被检测到的问题
  const hasVideo = !!(event.assets.video || (event.assets as any).video_path)
  const hasRenderFlag = !!(event.assets as any).render_complete_flag
  const renderDone = hasVideo && hasRenderFlag
  // ✅ 检查是否所有 YouTube 资产齐备（delivery.ready 状态）
  // 这表示渲染完成且所有 YouTube 资产（video, cover, title, description, captions, tags）都已就绪
  const isDeliveryReady = runbookState?.currentStage?.toLowerCase().includes('delivery.ready')
  const uploadDone =
    renderDone &&
    (!!event.assets.uploaded_at || !!event.assets.uploaded)
  const verifyDone =
    uploadDone &&
    (!!event.assets.verified_at || !!event.assets.verified)
  
  const hasPlaylistButNotDone =
    !!event.playlistPath &&
    !(playlistDone && audioDone && coverDone && titleDone && youtubeTitleDone && descriptionDone && captionsDone)
  const isRunbookStage = (stage?: string | null, needles: string[] = []) => {
    if (!stage) return false
    const normalized = stage.toLowerCase()
    return needles.some((needle) => normalized.includes(needle))
  }
  
  const preparationInProgress =
    (activeStageKey === 'preparation' ||
      (isEventInProgress &&
        isRunbookStage(runbookState?.currentStage, [
          'remix',
          'audio',
          'cover',
          'title',
          'description',
          'caption',
          'text',
          'filler',
          'playlist',
          'timeline',
          'hashtag',
          'prep.', // Support new standardized prep.* format
        ])) ||
      hasPlaylistButNotDone) &&
    failedStageKey !== 'preparation'
  
  const preparationFailed =
    failedStageKey === 'preparation' ||
    (isEventInProgress &&
      isRunbookStage(runbookState?.failedStage, [
        'remix',
        'audio',
        'cover',
        'title',
        'description',
        'caption',
        'playlist',
        'timeline',
        'hashtag',
        'prep.', // Support new standardized prep.* format
      ]))
  // ❌ 移除 remixStuck 自动检测 - 只依赖后端的明确失败状态
  // 如果后端检测到remix stuck，会通过WebSocket发送ERROR状态，前端会收到failedStage
  
  // ✅ 如果渲染完成且所有资产齐备（delivery.ready），应该显示publish.inProgress
  // 即使没有isEventInProgress，如果状态是delivery.ready且渲染完成，也应该显示为inProgress
  // ✅ 修复：如果渲染完成但未上传，应该显示第三条进度条为inProgress
  // 但如果之前上传过（有uploaded_at历史记录），则不显示（避免误判）
  const hasUploadHistory = !!(event.assets.uploaded_at || (event.assets as any).uploaded)
  const publishInProgress =
    (activeStageKey === 'publish' ||
      (isEventInProgress &&
        runbookState?.currentStage &&
        (runbookState.currentStage.toLowerCase().startsWith('delivery.') ||
         isRunbookStage(runbookState.currentStage, ['upload', 'verify', 'publish']))) ||
      // ✅ 如果渲染完成且有delivery.ready状态，显示为inProgress
      (renderDone && isDeliveryReady) ||
      // ✅ 如果渲染完成但未上传，且没有上传历史记录，显示为inProgress（准备上传）
      // 这确保刷新后即使runbookState丢失，也能正确显示第三条进度条
      (renderDone && !uploadDone && !hasUploadHistory)) &&
    failedStageKey !== 'publish'
  
  const publishFailed =
    failedStageKey === 'publish' ||
    (isEventInProgress &&
      isRunbookStage(runbookState?.failedStage, ['upload', 'verify', 'publish']))
  
  // ✅ Calculate preparation progress based on 7 required assets for preparation stage
  // 10 files total, but preparation stage tracks 7 core assets:
  // 1. playlist.csv (playlistDone)
  // 2. cover.png (coverDone)
  // 3. title (titleDone) - episode title
  // 4. youtube_title.txt (youtubeTitleDone) - YouTube title file
  // 5. youtube_description.txt (descriptionDone)
  // 6. youtube.srt (captionsDone)
  // 7. full_mix.mp3 + full_mix_timeline.csv (audioDone)
  // Note: playlist_metadata.json, manifest.json, youtube_tags.txt are assumed to exist if related files exist
  const preparationAssets = [playlistDone, coverDone, titleDone, youtubeTitleDone, descriptionDone, captionsDone, audioDone]
  const preparationProgress = preparationAssets.filter(Boolean).length / preparationAssets.length
  // ✅ Preparation is done only when ALL 7 required assets are complete (100% threshold)
  // This ensures accurate progress display and that all 10 files are ready before first bar lights up
  const preparationDone = preparationProgress >= 1.0
  return {
    preparation: {
      done: preparationDone,
      inProgress: preparationInProgress,
      failed: preparationFailed,
    },
    render: {
      done: renderDone,
      // Only show in-progress if actively rendering (not queued)
      // render.queue should not show as in-progress
      // ✅ 修复：显式检查 render.in_progress 状态
      // ✅ 如果视频文件存在但没有render_complete_flag，也应该判断为inProgress（即使runbookState丢失）
      inProgress: (() => {
        // 检查是否有视频文件但没有完成标志（说明正在渲染）
        const hasVideoFile = !!(event.assets.video || (event.assets as any).video_path)
        const hasRenderCompleteFlag = !!(event.assets as any).render_complete_flag
        const isRenderingByFileState = hasVideoFile && !hasRenderCompleteFlag && !renderDone
        
        // 检查runbook状态
        const isInProgressByRunbook = (activeStageKey === 'render' || 
                              (isEventInProgress && 
                               runbookState?.currentStage && 
                               (runbookState.currentStage.toLowerCase() === 'render.in_progress' ||
                                runbookState.currentStage.toLowerCase().includes('render.in_progress')))) && 
                             failedStageKey !== 'render' &&
                             runbookState?.currentStage?.toLowerCase() !== 'render.queue' &&
                             !runbookState?.currentStage?.toLowerCase().includes('render.queue')
        
        // 如果通过文件状态或runbook状态判断为渲染中，返回true
        const isInProgress = isInProgressByRunbook || isRenderingByFileState
        
        // ✅ 添加调试日志以追踪渲染状态计算
        if (event.id === '20251117' || event.id.includes('20251117')) {
          const currentStageLower = runbookState?.currentStage?.toLowerCase() || ''
          const isRenderQueue = currentStageLower === 'render.queue' || currentStageLower.includes('render.queue')
          const isRenderInProgress = currentStageLower === 'render.in_progress' || currentStageLower.includes('render.in_progress')
          console.debug('[calculateStageStatus] Render inProgress calculation:', {
            eventId: event.id,
            activeStageKey,
            isEventInProgress,
            currentStage: runbookState?.currentStage,
            currentStageLower,
            isRenderQueue,
            isRenderInProgress,
            hasVideoFile,
            hasRenderCompleteFlag,
            isRenderingByFileState,
            isInProgressByRunbook,
            failedStageKey,
            isInProgress,
          })
        }
        return isInProgress
      })(),
      failed: failedStageKey === 'render',
    },
    publish: {
      done: uploadDone && verifyDone,
      inProgress: publishInProgress,
      failed: publishFailed,
    },
  }
}
