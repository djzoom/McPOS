'use client'

import { useState, useMemo, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useRouter } from 'next/navigation'
import { useScheduleStore, calculateStageStatus, type ScheduleEvent, type DateRange } from '@/stores/scheduleStore'
import { GridProgressIndicator } from './GridProgressIndicator'
import { ResetConfirmDialog } from './ResetConfirmDialog'
import { APIHealthStatus } from './APIHealthStatus'
import { createEpisode, resetChannel } from '@/services/t2rApi'
import toast from 'react-hot-toast'
import { RotateCcw } from 'lucide-react'
import { handleError } from '@/lib/errorHandler'
import { useDebouncedRefresh } from '@/hooks/useDebouncedRefresh'
import { logger } from '@/lib/logger'
import { useQueryClient } from '@tanstack/react-query'

const GRID_BORDER_COLOR = 'rgba(148, 163, 184, 0.12)'
const VOID_HIGHLIGHT_BG = 'rgba(16, 185, 129, 0.08)'
const HIGHLIGHT_BORDER = '1px solid rgba(207, 255, 56, 0.5)'
const HIGHLIGHT_SHADOW = '0 0 8px rgba(207, 255, 56, 0.2)'

interface OverviewGridProps {
  channels: string[]
  dateRange: DateRange
  eventIds: string[]
  onCellClick?: (channelId: string, date: string, openPanel?: boolean) => void
}

// 加号组件 - 始终显示，hover时更明显
function PlusIcon({ 
  isHovered,
  isActive,
}: { 
  isHovered: boolean
  isActive: boolean
}) {
  return (
    <motion.svg
      key="plus-icon"
      initial={{ opacity: 0.45, scale: 0.95 }}
      animate={{
        opacity: isHovered ? [0.6, 1, 0.6] : [0.35, 0.55, 0.35],
        scale: isHovered ? [1, 1.12, 1] : [0.96, 1, 0.96],
        rotate: isHovered ? [-2, 0, 2, 0, -2] : [-1, 0, 1, 0, -1],
      }}
      transition={{
        duration: isHovered ? 1.8 : 3.6,
        repeat: Infinity,
        ease: 'easeInOut',
      }}
      width="20"
      height="20"
      viewBox="0 0 16 16"
      className="pointer-events-none select-none"
    >
      <line
        x1="2"
        y1="8"
        x2="14"
        y2="8"
        stroke={isActive ? 'rgba(207, 255, 56, 1)' : 'rgba(207, 255, 56, 0.6)'}
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <line
        x1="8"
        y1="2"
        x2="8"
        y2="14"
        stroke={isActive ? 'rgba(207, 255, 56, 1)' : 'rgba(207, 255, 56, 0.6)'}
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </motion.svg>
  )
}

function HighlightBackground({
  tone = 'void',
  zIndex = 12,
  opacity = 1,
}: {
  tone?: 'void'
  zIndex?: number
  opacity?: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="absolute inset-0 pointer-events-none rounded-md"
      style={{
        backgroundColor: VOID_HIGHLIGHT_BG,
        zIndex,
      }}
    />
  )
}

function HighlightFrame({
  pulse = false,
  zIndex = 18,
  staticOpacity = 0.55, // 静态外框的透明度，默认为VOID hover的亮度
}: {
  pulse?: boolean
  zIndex?: number
  staticOpacity?: number // 静态外框的透明度
}) {
  // 统一的动画参数 - 所有脉冲效果使用相同的参数
  const animate = pulse
    ? { 
        opacity: [0.9, 1, 0.9], // SCAFFOLD pulse的透明度范围
        scale: [0.98, 1, 0.98], // 统一的缩放范围
      }
    : { opacity: staticOpacity, scale: 1 } // 静态外框使用传入的透明度

  // 统一的动画时长和曲线 - 与GridProgress同步
  const transition = pulse
    ? { 
        duration: 2.0, // 与GridProgress同步
        repeat: Infinity, 
        ease: 'easeInOut' as const 
      }
    : { duration: 0.2 }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={animate}
      exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.1 } }}
      transition={transition}
      className="absolute inset-0 m-auto w-[90%] h-[90%] rounded-md pointer-events-none"
      style={{
        border: HIGHLIGHT_BORDER,
        boxShadow: HIGHLIGHT_SHADOW,
        zIndex,
      }}
    />
  )
}

// Workflow automation: All production stages (playlist, cover, remix, render) are handled by backend automation.
// Frontend only triggers episode creation and monitors progress via WebSocket.

export function OverviewGrid({ channels, dateRange, eventIds, onCellClick }: OverviewGridProps) {
  const router = useRouter()
  const queryClient = useQueryClient()
  
  // Use debounced refresh to reduce redundant network requests
  // Fix: Use base query key - React Query's invalidateQueries supports prefix matching
  // This will invalidate all queries starting with ['t2r-episodes'], including channel-specific ones
  const refreshEpisodes = useDebouncedRefresh({
    delay: 1000,
    queryKeys: [['t2r-episodes']], // Prefix match will invalidate all ['t2r-episodes', ...] queries
    refetch: true,
  })
  const refreshAfterReset = useDebouncedRefresh({
    delay: 500,
    refetch: true,
  })
  
  
  const channelState = useScheduleStore((state) => state.channelState)
  const setChannelState = useScheduleStore((state) => state.setChannelState)
  const resetStore = useScheduleStore((state) => state.reset)
  const eventsById = useScheduleStore((state) => state.eventsById)
  const upsertEvents = useScheduleStore((state) => state.upsertEvents)
  // Listen for stage updates to clear generating state
  useEffect(() => {
    const unsubscribe = useScheduleStore.subscribe(
      (state) => {
        // Clear generating state for episodes that are now verified (all stages done)
        const allEvents = Object.values(state.eventsById)
        setGeneratingEpisodes((prev) => {
          const newSet = new Set(prev)
          let changed = false
          prev.forEach((eventId) => {
            const event = allEvents.find((e: ScheduleEvent) => e.id === eventId)
            if (event) {
              // Get runbook state from scheduleStore (unified state management)
              const runbookState = state.runbookSnapshots[eventId] || null
              const stages = calculateStageStatus(event, runbookState)
              // If publish stage is done (verify completed), clear generating state
              if (stages.publish.done) {
              newSet.delete(eventId)
              changed = true
              }
            }
          })
          return changed ? newSet : prev
        })
      }
    )
    return unsubscribe
  }, [])
  
  const [hoveredEmptyCell, setHoveredEmptyCell] = useState<{ channelId: string; date: string } | null>(null)
  const [hoveredCellArea, setHoveredCellArea] = useState<{ channelId: string; date: string; area: 'plus' | 'other' } | null>(null)
  const [creatingEpisodes, setCreatingEpisodes] = useState<Set<string>>(new Set())
  const [resetDialogOpen, setResetDialogOpen] = useState<{ channelId: string } | null>(null)
  const [generatingEpisodes, setGeneratingEpisodes] = useState<Set<string>>(new Set()) // Track which episodes are generating

  const removeGeneratingFlags = (episodeIds: string[]) => {
    if (!episodeIds.length) return
    setGeneratingEpisodes((prev) => {
      if (prev.size === 0) {
        return prev
      }
      const next = new Set(prev)
      let changed = false
      episodeIds.forEach((id) => {
        if (next.delete(id)) {
          changed = true
        }
      })
      return changed ? next : prev
    })
  }
  
  const events = useMemo(() => {
    return eventIds
      .map((id) => eventsById[id])
      .filter((event): event is ScheduleEvent => Boolean(event))
  }, [eventIds, eventsById])

  // Get work cursor date for the first channel (or default)
  const workCursorDate = useScheduleStore((state) => {
    const firstChannel = channels[0] || 'kat_lofi'
    return state.getWorkCursorDate(firstChannel)
  })

  // Automatically clear generating flags once preparation assets就绪
  useEffect(() => {
    if (!generatingEpisodes.size) return
    const runbookSnapshots = useScheduleStore.getState().runbookSnapshots
    const readyIds: string[] = []
    events.forEach((event) => {
      if (!generatingEpisodes.has(event.id)) return
      const runbookState = runbookSnapshots[event.id] || null
      const stages = calculateStageStatus(event, runbookState)
      if (stages.preparation.done) {
        readyIds.push(event.id)
      }
    })
    if (readyIds.length) {
      removeGeneratingFlags(readyIds)
    }
  }, [events, generatingEpisodes])
  
  // Generate date range array with special handling for dates before work cursor
  const { dateArray, completedDatesRange } = useMemo(() => {
    const dates: string[] = []
    const start = new Date(dateRange.from)
    const end = new Date(dateRange.to)
    
    // Calculate dates before work cursor
    let completedStart: string | null = null
    let completedEnd: string | null = null
    
    if (workCursorDate) {
      // Parse work cursor date (YYYY-MM-DD format)
      const cursorDateStr = workCursorDate
      const cursorDate = new Date(cursorDateStr + 'T00:00:00')
      cursorDate.setHours(0, 0, 0, 0)
      const cursorDateStrFormatted = cursorDate.toISOString().split('T')[0]
      
      // Find the earliest date in the range that is before cursor
      const rangeStart = new Date(start)
      rangeStart.setHours(0, 0, 0, 0)
      const rangeStartStr = rangeStart.toISOString().split('T')[0]
      
      // Find the last date before cursor (cursor date - 1 day)
      const lastBeforeCursor = new Date(cursorDate)
      lastBeforeCursor.setDate(lastBeforeCursor.getDate() - 1)
      const lastBeforeCursorStr = lastBeforeCursor.toISOString().split('T')[0]
      
      // Include dates up to and including the day before cursor date
      // If cursor is 2025-11-17, completed range should include up to 2025-11-16
      if (rangeStartStr < cursorDateStrFormatted) {
        completedStart = rangeStartStr
        completedEnd = lastBeforeCursorStr
        
        // Only add dates from cursor onwards (cursor date and later)
        // Use string comparison to avoid timezone issues
        for (let d = new Date(cursorDate); d <= end; d.setDate(d.getDate() + 1)) {
          const dateStr = d.toISOString().split('T')[0]
          // Only add if date is >= cursor date
          if (dateStr >= cursorDateStrFormatted) {
            dates.push(dateStr)
          }
        }
      } else {
        // All dates are from cursor onwards, no completed range
        for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
          const dateStr = d.toISOString().split('T')[0]
          // Only add if date is >= cursor date
          if (dateStr >= cursorDateStrFormatted) {
            dates.push(dateStr)
          }
        }
      }
    } else {
      // No work cursor, show all dates
      for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
        dates.push(d.toISOString().split('T')[0])
      }
    }
    
    return {
      dateArray: dates,
      completedDatesRange: completedStart && completedEnd && completedStart <= completedEnd ? { from: completedStart, to: completedEnd } : null
    }
  }, [dateRange, workCursorDate])

  // Group events by channel and date, filtering out dates before work cursor
  const eventsByChannelAndDate = useMemo(() => {
  const grouped: Record<string, Record<string, ScheduleEvent[]>> = {}
    
    channels.forEach((channelId) => {
      grouped[channelId] = {}
      // Only initialize dates that are in dateArray (after work cursor)
      dateArray.forEach((date) => {
        grouped[channelId][date] = []
      })
    })
  
  // Filter events: only include events that are in dateArray (after work cursor)
  // This ensures events before work cursor (like 16th) are not included
  const dateArraySet = new Set(dateArray)
  events.forEach((event) => {
      // Only add event if its date is in dateArray (after work cursor)
      if (dateArraySet.has(event.date) && grouped[event.channelId]) {
        if (!grouped[event.channelId][event.date]) {
          grouped[event.channelId][event.date] = []
        }
        grouped[event.channelId][event.date].push(event)
      }
  })
  
  return grouped
  }, [channels, dateArray, events])
  
  // Find first empty cell for a channel
  const findFirstEmptyCell = (channelId: string): string | null => {
    for (const date of dateArray) {
      const cellEvents = eventsByChannelAndDate[channelId]?.[date] || []
      if (cellEvents.length === 0) {
        return date
      }
    }
    return null
  }
  
  // Check if a date is in the range from first empty to target
  const isInEmptyRange = (channelId: string, date: string): boolean => {
    if (!hoveredEmptyCell || hoveredEmptyCell.channelId !== channelId) return false
    
    const firstEmpty = findFirstEmptyCell(channelId)
    if (!firstEmpty) return false
    
    const firstEmptyIndex = dateArray.indexOf(firstEmpty)
    const targetIndex = dateArray.indexOf(hoveredEmptyCell.date)
    const currentIndex = dateArray.indexOf(date)
    
    return currentIndex >= firstEmptyIndex && currentIndex <= targetIndex
  }
  
  // Check if this is the last date in the hovered range
  const isLastDateInRange = (channelId: string, date: string): boolean => {
    return hoveredEmptyCell?.channelId === channelId && hoveredEmptyCell?.date === date
  }
  
  // Find first event cell for a channel
  const findFirstEventCell = (channelId: string): string | null => {
    const currentState = channelState[channelId] || 'void'
    if (currentState === 'void') return null
    
    // 找到第一个有事件的格子
    for (const date of dateArray) {
      const cellEvents = eventsByChannelAndDate[channelId]?.[date] || []
      if (cellEvents.length > 0) {
        return date
      }
    }
    return null
  }
  
  // Find first unverified cell for a channel
  const findFirstUnverifiedCell = (channelId: string): string | null => {
    const runbookSnapshots = useScheduleStore.getState().runbookSnapshots
    for (const date of dateArray) {
      const cellEvents = eventsByChannelAndDate[channelId]?.[date] || []
      const hasUnverified = cellEvents.some((e) => {
        const runbookState = runbookSnapshots[e.id] || null
        const stages = calculateStageStatus(e, runbookState)
        return !stages.publish.done
      })
      if (hasUnverified) {
        return date
      }
    }
    return null
  }
  
  // Check if a date should be highlighted from plus hover
  const shouldHighlightFromPlus = (channelId: string, date: string): boolean => {
    if (!hoveredCellArea || hoveredCellArea.channelId !== channelId || hoveredCellArea.area !== 'plus') {
      return false
    }
    
    // 使用第一个事件格子作为起始点
    const firstEventCell = findFirstEventCell(channelId)
    if (!firstEventCell) return false
    
    const firstEventCellIndex = dateArray.indexOf(firstEventCell)
    const targetIndex = dateArray.indexOf(hoveredCellArea.date)
    const currentIndex = dateArray.indexOf(date)
    
    // 只要在范围内就显示（从第一个事件格子到当前 hover 的格子）
    return currentIndex >= firstEventCellIndex && currentIndex <= targetIndex
  }
  
  // Handle empty cell click
  const handleEmptyCellClick = async (channelId: string, date: string) => {
    const currentState = channelState[channelId] || 'void'
    
    if (currentState === 'void') {
      // Open initialize dialog would be handled here
      // For now, create episode directly
      await handleCreateEpisode(channelId, date)
    } else {
      await handleCreateEpisode(channelId, date)
    }
  }
    
  // Handle create episode (batch from first empty to target)
  const handleCreateEpisode = async (channelId: string, targetDate: string) => {
    logger.debug('[handleCreateEpisode]', { channelId, targetDate })
    
    // 使用 Sentry span 追踪创建排播的性能
    const Sentry = await import('@sentry/nextjs').catch(() => null)
    if (Sentry) {
      return Sentry.startSpan(
        {
          op: 'ui.action',
          name: 'Create Episode',
        },
        async (span) => {
          span.setAttribute('channel_id', channelId)
          span.setAttribute('target_date', targetDate)
          return await executeCreateEpisode(channelId, targetDate, span)
        }
      )
    } else {
      return await executeCreateEpisode(channelId, targetDate, null)
    }
  }
  
  const executeCreateEpisode = async (
    channelId: string, 
    targetDate: string, 
    span: any
  ) => {
    
    // Check if target cell is already occupied
    const targetCellEvents = eventsByChannelAndDate[channelId]?.[targetDate] || []
    if (targetCellEvents.length > 0) {
      logger.debug('[handleCreateEpisode] Target cell already has events, opening panel instead')
      if (onCellClick) {
        onCellClick(channelId, targetDate, true)
      }
      return
    }
    
    // Clean up any stale events for dates we're about to create
    // This prevents +2 display after reset (old events with different IDs but same dates)
    // After reset, refreshAfterReset() might reload stale events from backend before they're fully deleted
    const firstEmpty = findFirstEmptyCell(channelId)
    const datesToClean: string[] = []
    if (!firstEmpty) {
      datesToClean.push(targetDate)
    } else {
      const firstEmptyIndex = dateArray.indexOf(firstEmpty)
      const targetIndex = dateArray.indexOf(targetDate)
      for (let i = firstEmptyIndex; i <= targetIndex; i++) {
        datesToClean.push(dateArray[i])
      }
    }
    
    // Remove any existing events for these dates (they might be stale after reset)
    // This ensures we don't show +2 when creating new events after reset
    const store = useScheduleStore.getState()
    const currentEvents = store.events[channelId] || []
    const eventsToKeep = currentEvents.filter((event) => !datesToClean.includes(event.date))
    if (eventsToKeep.length !== currentEvents.length) {
      logger.debug('[handleCreateEpisode] Cleaning up stale events after reset', {
        removed: currentEvents.length - eventsToKeep.length,
        dates: datesToClean,
      })
      // Remove stale events from store (similar to resetStore but only for specific dates)
      const removedEventIds = currentEvents
        .filter((event) => datesToClean.includes(event.date))
        .map((event) => event.id)
      
      // Update store: remove events from the channel's event list and from indexes
      const newEvents = { ...store.events }
      newEvents[channelId] = eventsToKeep
      
      const newEventsById = { ...store.eventsById }
      const newEventChannelIndex = { ...store.eventChannelIndex }
      const newRunbookSnapshots = { ...store.runbookSnapshots }
      
      // Remove deleted events from all indexes
      removedEventIds.forEach((id) => {
        delete newEventsById[id]
        delete newEventChannelIndex[id]
        delete newRunbookSnapshots[id]
      })
      
      // Update store
      useScheduleStore.setState({
        events: newEvents,
        eventsById: newEventsById,
        eventChannelIndex: newEventChannelIndex,
        runbookSnapshots: newRunbookSnapshots,
      })
    }
    
    logger.debug('[handleCreateEpisode] First empty cell:', firstEmpty)
    
    // If no first empty found, just create the clicked cell
    const datesToCreate: string[] = []
    if (!firstEmpty) {
      datesToCreate.push(targetDate)
    } else {
      const firstEmptyIndex = dateArray.indexOf(firstEmpty)
      const targetIndex = dateArray.indexOf(targetDate)
      
      // Only create from first empty to target (inclusive)
      // After cleanup, re-check events from store (eventsByChannelAndDate is memoized and won't update during function execution)
      const updatedEvents = useScheduleStore.getState().events[channelId] || []
      const updatedEventsByDate = new Map<string, ScheduleEvent[]>()
      updatedEvents.forEach((event) => {
        if (!updatedEventsByDate.has(event.date)) {
          updatedEventsByDate.set(event.date, [])
        }
        updatedEventsByDate.get(event.date)!.push(event)
      })
      
      for (let i = firstEmptyIndex; i <= targetIndex; i++) {
        const date = dateArray[i]
        // Only add if cell is actually empty (after cleanup)
        const cellEvents = updatedEventsByDate.get(date) || []
        if (cellEvents.length === 0) {
          datesToCreate.push(date)
        }
      }
    }
    
    if (datesToCreate.length === 0) {
      logger.debug('[handleCreateEpisode] No dates to create')
      toast.error('没有可创建的排播日期')
      return
    }
    
    logger.debug('[handleCreateEpisode] Creating episodes for dates:', datesToCreate)
    
    // Set loading state for all cells
    const loadingKeys = datesToCreate.map((d) => `${channelId}-${d}`)
    setCreatingEpisodes(new Set(loadingKeys))
    
    // Declare variables outside try block so they're accessible in finally/catch
    let episodeIds: string[] = []
    
    try {
      // Step 1: Create episodes quickly in parallel (without starting generation)
      // This creates folders and schedule entries, but doesn't trigger slow init_episode
      logger.debug(`[handleCreateEpisode] Creating ${datesToCreate.length} episodes in parallel (scaffold only)...`)
      const createPromises = datesToCreate.map(async (date) => {
        try {
          logger.debug(`[handleCreateEpisode] Creating scaffold for ${date}...`)
          const result = await createEpisode({
            channel_id: channelId,
            date,
            start_generation: false, // Don't start generation yet - create scaffold first
          })
          return { date, result, error: null }
        } catch (error: unknown) {
          logger.error(`[handleCreateEpisode] Failed to create scaffold for ${date}:`, error)
          return { date, result: null, error }
        }
      })
      
      // Wait for all scaffold creations to complete
      const createResults = await Promise.all(createPromises)
      
      // Collect successful episode IDs
      let successCount = 0
      episodeIds = []
      
      for (const { date, result, error } of createResults) {
        if (error) {
          handleError(error, {
            component: 'OverviewGrid',
            action: 'createEpisode',
            toastMessage: `创建 ${date} 的排播失败`,
          })
          continue
        }
        
        if (result && result.status === 'ok' && result.episode_id) {
          successCount++
          episodeIds.push(result.episode_id)
            
            // Inject placeholder event so UI reflects the new episode immediately
            try {
              const placeholderEvent: ScheduleEvent = {
                id: result.episode_id,
                channelId,
                date,
                title: result.episode?.title || '',
                durationSec: 0,
                bpm: null,
                assets: {
                  cover: null,
                  audio: null,
                  description: null,
                  captions: null,
                  timeline_csv: null,
                  video: null,
                  video_path: null,
                  uploaded_at: null,
                  uploaded: false,
                  verified_at: null,
                  verified: false,
                },
                image_path: null,
                issues: [],
                hasOutputFolder: true,
                playlistPath: result.csv_path || null,
                // Initialize asset existence flags as false (will be updated when files are generated)
                audio_exists: false,
                description_exists: false,
                captions_exists: false,
                cover_exists: false,
                youtube_title_exists: false,
                gridProgress: {
                  lastStage: null,
                  lastStageTimestamp: Date.now(),
                  stageHistory: [],
                },
              }
              upsertEvents(channelId, [placeholderEvent])
              // Immediately update channel state to 'in_production' after first placeholder is created
              // This ensures UI shows scaffold state immediately without waiting for API refresh
              if (successCount === 1) {
                setChannelState(channelId, 'in_production')
              }
            } catch (e) {
              logger.warn('[handleCreateEpisode] Failed to upsert placeholder event', e)
            }
          logger.debug(`[handleCreateEpisode] Successfully created scaffold for ${result.episode_id}`)
          } else {
          logger.error(`[handleCreateEpisode] Failed to create scaffold for ${date}:`, {
            status: result?.status,
            episode_id: result?.episode_id,
            errors: result?.errors,
          })
          toast.error(`创建 ${date} 的排播失败: ${result?.errors?.join(', ') || '未知错误'}`)
        }
      }
      
      // Step 2: Now start generation for all created episodes in parallel
      // This triggers init_episode which creates playlist.csv and recipe.json, then enqueues automation
      if (episodeIds.length > 0) {
        logger.debug(`[handleCreateEpisode] Starting generation for ${episodeIds.length} episodes...`)
        
        // Import initEpisode function
        const { initEpisode } = await import('@/services/t2rApi')
        
        const generationPromises = episodeIds.map(async (episodeId) => {
          try {
            logger.debug(`[handleCreateEpisode] Creating files and starting automation for ${episodeId}...`)
            
            // Create playlist.csv and recipe.json via init_episode
            // This also triggers automation queue in the backend if configured
            const initResult = await initEpisode({
              episode_id: episodeId,
              channel_id: channelId,
              avoid_duplicates: true,
              seo_template: true,
              channelId: channelId,
            })
            
            if (initResult.status !== 'ok') {
              logger.warn(`[handleCreateEpisode] init_episode failed for ${episodeId}:`, initResult.errors)
              return { episodeId, success: false, error: initResult.errors?.join(', ') || 'init_episode failed' }
            }
            
            logger.debug(`[handleCreateEpisode] ✅ Created files for ${episodeId}`)
            
            // Now enqueue for automation by calling create-episode with start_generation=true
            // This will trigger enqueue_episode in the backend
            try {
              // Convert episodeId (YYYYMMDD) to date format (YYYY-MM-DD) for createEpisode API
              const episodeDate = episodeId.length === 8 
                ? `${episodeId.slice(0, 4)}-${episodeId.slice(4, 6)}-${episodeId.slice(6, 8)}`
                : episodeId // Fallback if already in correct format
              
              logger.debug(`[handleCreateEpisode] Converting episodeId ${episodeId} to date format ${episodeDate}`)
              
              const enqueueResult = await createEpisode({
                channel_id: channelId,
                date: episodeDate, // Converted to YYYY-MM-DD format
                start_generation: true,
              })
              
              if (enqueueResult.automation_queued === false) {
                logger.warn(`[handleCreateEpisode] Automation not queued for ${episodeId}`)
                return { episodeId, success: true, error: 'automation not queued' }
              }
              
              logger.debug(`[handleCreateEpisode] ✅ Enqueued automation for ${episodeId}`)
              return { episodeId, success: true, error: null }
            } catch (enqueueError: unknown) {
              logger.warn(`[handleCreateEpisode] Failed to enqueue automation for ${episodeId}:`, enqueueError)
              return { episodeId, success: true, error: `enqueue failed: ${enqueueError}` }
          }
        } catch (error: unknown) {
            logger.error(`[handleCreateEpisode] Failed to start generation for ${episodeId}:`, error)
            return { episodeId, success: false, error: String(error) }
          }
        })
        
        // Wait for all generation starts (but don't wait for completion)
        const generationResults = await Promise.all(generationPromises)
        
        // Check for generation errors
        let failures = 0
        for (const { episodeId, success, error } of generationResults) {
          if (!success) {
            failures++
            logger.warn(`[handleCreateEpisode] Generation failed for ${episodeId}: ${error}`)
            toast.error(`排播 ${episodeId} 的生成流程失败: ${error}`, {
              duration: 5000,
            })
          } else if (error) {
            // Success but with warning
            logger.warn(`[handleCreateEpisode] Generation completed with warning for ${episodeId}: ${error}`)
            // Use toast() with custom styling for warnings
            toast(`排播 ${episodeId} 的生成完成，但有警告: ${error}`, {
              duration: 4000,
              icon: '⚠️',
            })
          }
        }
        
        if (failures === 0) {
          logger.debug(`[handleCreateEpisode] ✅ Successfully started generation for all ${episodeIds.length} episodes`)
        } else {
          logger.warn(`[handleCreateEpisode] ⚠️ ${failures} episodes had generation failures`)
        }
      }
      
      if (episodeIds.length === 0) {
        logger.error('[handleCreateEpisode] No episodes were successfully created')
        toast.error('没有成功创建的排播')
        setCreatingEpisodes(new Set())
        return
      }
      
      logger.debug(`[handleCreateEpisode] Successfully created ${episodeIds.length} episodes:`, episodeIds)
      
      // Channel state was already set to 'in_production' when first placeholder was created
      // This ensures UI shows scaffold state immediately without waiting for API refresh
      
      // Refresh data to get the created episodes (immediate, not debounced for better UX)
      logger.debug('[handleCreateEpisode] Refreshing episodes data immediately...')
      // Invalidate and refetch immediately to get latest data from backend
      queryClient.invalidateQueries({ queryKey: ['t2r-episodes'], exact: false })
      queryClient.refetchQueries({ queryKey: ['t2r-episodes'], exact: false })
      
      // Also trigger debounced refresh as fallback
      refreshEpisodes()
      
      // Clear creating state
      setCreatingEpisodes(new Set())
      
      // Mark episodes as generating (generation was already started in Step 2 above)
      setGeneratingEpisodes(new Set(episodeIds))
      
      toast.success(`已创建 ${episodeIds.length} 期排播，文件生成和自动化流程已启动`, {
        id: `generate-${channelId}`,
        duration: 4000,
      })
    } catch (error: unknown) {
      handleError(error, {
        component: 'OverviewGrid',
        action: 'createEpisodes',
        toastMessage: '创建排播失败',
      })
      setCreatingEpisodes(new Set())
      removeGeneratingFlags(episodeIds)
    }
    
    // 记录成功创建的排播数量
    if (span && episodeIds.length > 0) {
      span.setAttribute('episodes_created', episodeIds.length.toString())
    }
  }
  
  // Find first unrendered cell for a channel (assets done but render not started)
  const findFirstUnrenderedCell = (channelId: string): string | null => {
    const runbookSnapshots = useScheduleStore.getState().runbookSnapshots
    for (const date of dateArray) {
      const cellEvents = eventsByChannelAndDate[channelId]?.[date] || []
      const hasUnrendered = cellEvents.some((e) => {
        const runbookState = runbookSnapshots[e.id] || null
        const stages = calculateStageStatus(e, runbookState)
        return stages.preparation.done && !stages.render.done && !stages.render.inProgress
      })
      if (hasUnrendered) {
        return date
      }
    }
    return null
  }
  
  // Handle SCAFFOLD/ACTIVE cell click on plus area - Render prepared files
  const handleScaffoldActivePlusClick = async (channelId: string, date: string) => {
    // Reset hover state
    setHoveredCellArea(null)
    
    // Find all episodes ready for rendering (assets done but render not started) from first unrendered to clicked date
    const firstUnrendered = findFirstUnrenderedCell(channelId)
    if (!firstUnrendered) {
      toast.error('没有可渲染的排播（需要先完成准备：封面、标题、描述、字幕）', { duration: 3000 })
      return
    }
    
    const firstIndex = dateArray.indexOf(firstUnrendered)
    const targetIndex = dateArray.indexOf(date)
    
    // Collect all episodes ready for rendering in the range
    const episodesToRender: { eventId: string; date: string; event: ScheduleEvent }[] = []
    const runbookSnapshots = useScheduleStore.getState().runbookSnapshots
    
    for (let i = firstIndex; i <= targetIndex; i++) {
      const currentDate = dateArray[i]
      const cellEvents = eventsByChannelAndDate[channelId]?.[currentDate] || []
      const readyEvents = cellEvents.filter((e) => {
        const runbookState = runbookSnapshots[e.id] || null
        const stages = calculateStageStatus(e, runbookState)
        // Ready for render: preparation done, but render not done and not in progress
        return stages.preparation.done && !stages.render.done && !stages.render.inProgress
      })
      readyEvents.forEach((event) => {
        episodesToRender.push({ eventId: event.id, date: currentDate, event })
      })
    }
    
    if (episodesToRender.length === 0) {
      toast.error('没有可渲染的排播（需要先完成准备：封面、标题、描述、字幕）', { duration: 3000 })
      return
    }
    
    // Check prerequisites: preparation must be done (cover, title, description, captions)
    // According to plan: render requires assets (cover + audio), but we check preparation.done
    // which includes cover, title, description, captions (audio is optional for rendering)
    const missingAssets: string[] = []
    episodesToRender.forEach(({ event }) => {
      const runbookState = runbookSnapshots[event.id] || null
      const stages = calculateStageStatus(event, runbookState)
      if (!stages.preparation.done) {
        if (!event.assets.cover) missingAssets.push('封面')
        if (!event.title) missingAssets.push('标题')
        if (!event.assets.description) missingAssets.push('描述')
        if (!event.assets.captions) missingAssets.push('字幕')
      }
    })
    
    if (missingAssets.length > 0) {
      const uniqueAssets = Array.from(new Set(missingAssets))
      toast.error(`部分排播的准备未完成（需要：${uniqueAssets.join('、')}）`, { duration: 3000 })
      return
    }
    
    try {
      // Import API dynamically
      const { enqueueRenderJobs } = await import('@/services/t2rApi')
      
      toast.loading(`正在为 ${episodesToRender.length} 期排播启动渲染...`, {
        id: `render-${channelId}`,
      })
      
      // Start rendering in parallel for all episodes
      const response = await enqueueRenderJobs(channelId, episodesToRender.map((item) => item.eventId))
      const failedJobs = response.results.filter((item) => !item.queued).map((item) => item.episode_id)

      if (failedJobs.length) {
        toast.error(`以下排播已在渲染队列中：${failedJobs.join(', ')}`)
      } else {
        toast.success(`已将 ${episodesToRender.length} 期排播加入渲染队列`, {
        id: `render-${channelId}`,
        duration: 3000,
      })
      }
    } catch (error: unknown) {
      handleError(error, {
        component: 'OverviewGrid',
        action: 'startRendering',
        toastMessage: '启动渲染失败',
      })
    }
  }
  
  // Handle SCAFFOLD/ACTIVE cell click on other areas
  const handleScaffoldActiveOtherClick = (channelId: string, date: string, e?: React.MouseEvent) => {
    // Prevent event from bubbling to parent elements
    if (e) {
      e.stopPropagation()
    }
    
    logger.debug('[handleScaffoldActiveOtherClick] Clicked scaffold/active cell', { channelId, date })
    
    // Navigate to channel page (with or without opening panel)
    if (onCellClick) {
      onCellClick(channelId, date, true)
    } else {
      // Fallback: navigate directly if onCellClick is not provided
      router.push(`/mcrb/channel/${channelId}?focus=${date}`)
    }
  }
  
  // Handle reset confirm
  const handleResetConfirm = async (channelId: string) => {
    try {
      const response = await resetChannel({ 
        channel_id: channelId,
        confirm: true 
      })
      
      if (response.status === 'reset_complete' || response.status === 'partial') {
        // Check if asset reset was successful
        if (response.assets_reset === false) {
          logger.error('[OverviewGrid] Asset reset failed:', response.errors)
          toast.error(`重置失败: 资产使用统计未重置成功。${response.errors?.join(', ') || ''}`)
        }
        
        // Immediately clear store state for this channel
        resetStore(channelId)
        
        // Set channel state to void immediately
        setChannelState(channelId, 'void')
        
        // Force refresh data (debounced) - replaces fixed 500ms wait
        refreshAfterReset()
        
        if (response.assets_reset === false) {
          toast.error(`频道 ${channelId} 已重置，但资产使用统计可能未完全清零，请检查后端日志`)
        } else {
        toast.success(`频道 ${channelId} 已重置`)
        }
      } else {
        toast.error(`重置失败: ${response.message || '未知错误'}`)
      }
    } catch (error: unknown) {
      handleError(error, {
        component: 'OverviewGrid',
        action: 'resetChannel',
        toastMessage: '重置失败',
      })
    } finally {
      setResetDialogOpen(null)
    }
  }
  
  // Render empty cell (VOID or empty in SCAFFOLD/ACTIVE)
  // 样式统一：所有VOID格子样式始终一致，不因其他状态改变而改变
  const renderEmptyCell = (channelId: string, date: string) => {
    const channelCellEvents = eventsByChannelAndDate[channelId]?.[date] || []
    const shouldHighlight = isInEmptyRange(channelId, date)
    const isLastDate = isLastDateInRange(channelId, date)
    const isCreating = creatingEpisodes.has(`${channelId}-${date}`)
    
    // 统一的VOID样式 - 永远不变（所有空格子都使用相同的背景色）
    const getEmptyCellStyle = () => {
      return 'bg-[#050812]'
    }
    
    // 统一的线框样式 - 永远不变，使用统一的GRID_BORDER_COLOR
    const cellBorderStyle = { borderColor: GRID_BORDER_COLOR }
    
    return (
      <td
        key={date}
        className={`h-28 px-2 py-2 border-r border-b relative group w-[100px] ${getEmptyCellStyle()} ${
          isCreating ? 'opacity-60 cursor-wait' : ''
        }`}
        style={cellBorderStyle}
        onClick={() => handleEmptyCellClick(channelId, date)}
        onMouseEnter={() => setHoveredEmptyCell({ channelId, date })}
        onMouseLeave={() => setHoveredEmptyCell(null)}
      >
        {/* 统一的VOID指示器：所有空格子都显示一像素点 - 样式永远不变 */}
        {!isCreating && !shouldHighlight && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div
              className="rounded-full pointer-events-none"
              style={{
                width: '1px',
                height: '1px',
                backgroundColor: 'var(--kat-primary, #CFFF38)',
                boxShadow: '0 0 6px rgba(207, 255, 56, 0.35)',
              }}
            />
          </div>
        )}
        
        {/* 统一的hover高亮效果 */}
        {shouldHighlight && !isCreating && (
          <>
            <HighlightBackground tone="void" />
            <HighlightFrame zIndex={50} />
          </>
        )}
        
        {/* 统一的最后日期帧效果 */}
        {isLastDate && !isCreating && (
          <HighlightFrame pulse={false} zIndex={200} />
        )}

      </td>
    )
  }
  
  // Render cell with events (in_production)
  const renderEventCell = (channelId: string, date: string, cellEvents: ScheduleEvent[]) => {
    const currentState = channelState[channelId] || 'void'
    const primaryEvent = cellEvents[0]
    const isGenerating = primaryEvent ? generatingEpisodes.has(primaryEvent.id) : false
    // Safety check: ensure primaryEvent exists
    if (!primaryEvent) {
      logger.warn('[renderEventCell] No primaryEvent for', { channelId, date, cellEvents })
      return null
    }
    
    const hasMultiple = cellEvents.length > 1
    const hasOutputFolder = primaryEvent.hasOutputFolder || false
    // 样式判断：基于 GridProgress 阶段（所有阶段未开始且无 playlist 显示 SCAFFOLD 样式，其他显示 ACTIVE 样式）
    const runbookState = useScheduleStore.getState().runbookSnapshots[primaryEvent.id] || null
    const stages = calculateStageStatus(primaryEvent, runbookState)
    // Check if event is draft (all stages not started and no playlist)
    const isScaffold = !primaryEvent.playlistPath && 
                       !stages.preparation.done && 
                       !stages.render.done
    const isActive = currentState === 'in_production'
    
    // Debug log for grid progress rendering
    if (isScaffold || isActive) {
      logger.debug('[renderEventCell] GridProgress should render', {
        channelId,
        date,
        eventId: primaryEvent.id,
        isScaffold,
        isActive,
        currentState,
      })
    }
    
    const isHoveredPlus = hoveredCellArea?.channelId === channelId && 
                         hoveredCellArea?.date === date && 
                         hoveredCellArea?.area === 'plus'
    const isHoveredOther = hoveredCellArea?.channelId === channelId && 
                          hoveredCellArea?.date === date && 
                          hoveredCellArea?.area === 'other'
    const shouldHighlightFromPlusHover = shouldHighlightFromPlus(channelId, date)
    
    // 统一的样式定义 - 状态样式永远不变，不因其他状态改变
    const getEventCellStyle = () => {
      if (isScaffold) {
        // SCAFFOLD样式：统一，永远不变
        return 'bg-[rgba(16,185,129,0.08)] shadow-[inset_0_0_0_1px_rgba(16,185,129,0.18)]'
      } else if (isActive) {
        // ACTIVE样式：统一，永远不变
        if (hasOutputFolder) {
          return 'bg-green-500/20 shadow-[inset_0_0_0_1px_rgba(34,197,94,0.25)]'
        } else {
          return 'bg-dark-bg-primary/95'
        }
      } else {
        // 默认样式
        return 'bg-dark-bg-primary/95'
      }
    }
    
    // 统一的线框样式 - 永远不变，使用统一的GRID_BORDER_COLOR
    const cellBorderStyle = { borderColor: GRID_BORDER_COLOR }
    
    return (
      <td
        key={date}
        data-cell-id={`${channelId}-${date}`}
        className={`h-28 px-2 py-2 border-r border-b relative group w-[100px] ${getEventCellStyle()}`}
        style={cellBorderStyle}
        onMouseEnter={(e) => {
          // 检查鼠标是否在十字区域
          const target = e.target as HTMLElement
          const isInPlusArea = target.closest('.plus-area') !== null
          
          if (!isInPlusArea) {
            // 在格子区域内但不在十字区域：只点亮外框
            setHoveredCellArea({ channelId, date, area: 'other' })
          }
        }}
        onMouseLeave={(e) => {
          // 检查鼠标是否还在格子内
          const relatedTarget = e.relatedTarget as HTMLElement | null
          const isMovingWithinCell = relatedTarget && typeof relatedTarget.closest === 'function'
            ? relatedTarget.closest(`td[data-cell-id="${channelId}-${date}"]`)
            : null
          
          // 如果离开格子区域，scaffold格子立刻恢复原状
          if (!isMovingWithinCell) {
            setHoveredCellArea(null)
            if (typeof window !== 'undefined' && (window as any).__gridProgressPulse) {
              (window as any).__gridProgressPulse = {}
            }
          }
        }}
      >
        {/* 统一的外框样式 - 与VOID hover样式完全一致（放在motion.div外面，确保定位上下文一致） */}
        {isHoveredOther && (
          <>
            {/* 使用与VOID完全相同的样式（tone="void"） */}
            <HighlightBackground tone="void" zIndex={12} />
            <HighlightFrame zIndex={100} pulse={false} staticOpacity={0.8} />
          </>
        )}
        
        {/* 统一的同步脉冲外框 - 使用统一的HighlightFrame组件，只在十字区域hover时显示脉冲 */}
        {shouldHighlightFromPlusHover && (
          <>
            {/* 向前染色：加入透明绿背景（与VOID hover效果完全一致） */}
            <HighlightBackground tone="void" zIndex={14} />
            {/* 所有序列中的scaffold格子（包括当前hover的）都使用相同的高光样式 */}
            <HighlightFrame 
              zIndex={200} 
              pulse={true}
            />
          </>
        )}
        
        <motion.div
          className="w-full h-full rounded-lg transition-all flex flex-col items-center justify-center relative cursor-pointer"
          onClick={(e) => {
            // Only handle click if not clicking on plus area
            const target = e.target as HTMLElement
            const isInPlusArea = target.closest('.plus-area') !== null
            if (!isInPlusArea) {
              handleScaffoldActiveOtherClick(channelId, date, e)
            }
          }}
        >
            <div className="flex flex-col items-center justify-center h-full px-1 py-1 w-full min-h-0">
              {hasMultiple && (
                <span className="text-sm font-semibold text-dark-text mb-1 z-10">
                  +{cellEvents.length}
                </span>
              )}
              <div className="w-full flex-1 flex items-center justify-center min-h-0 px-2">
            {(isActive || isScaffold) && (
              <AnimatePresence mode="wait">
                {shouldHighlightFromPlusHover ? (
                  // 统一的脉冲动画：GridProgress和边框同步闪烁（使用统一的动画参数）
                  <motion.div
                    key="pulse-mode"
                    initial={{ opacity: 0, scale: 0.96 }}
                    animate={{ 
                      opacity: [0.4, 0.7, 0.4], // 统一的透明度范围
                      scale: [0.98, 1, 0.98], // 统一的缩放范围
                    }}
                    exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.1 } }}
                    transition={{ 
                      duration: 2.0, // 统一的动画时长
                      repeat: Infinity,
                      ease: 'easeInOut',
                    }}
                  >
                    <GridProgressIndicator eventId={primaryEvent.id} size="sm" />
                  </motion.div>
                ) : (
                  // 正常显示模式：始终显示 GridProgress，随阶段更新
                  <motion.div
                    key="normal-mode"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0, transition: { duration: 0.1 } }}
                    transition={{ duration: 0.2 }}
                  >
                    <GridProgressIndicator eventId={primaryEvent.id} size="sm" />
                  </motion.div>
                )}
              </AnimatePresence>
            )}
              </div>
            </div>
            
            {/* Plus icon - 在scaffold/active格子中始终显示，hover时更明显 */}
            {(isScaffold || isActive) && !isGenerating && (
              <div 
                className="absolute inset-0 flex items-center justify-center pointer-events-none"
                style={{ zIndex: 30 }}
              >
                <div
                  className="plus-area flex items-center justify-center pointer-events-auto rounded-full"
                  style={{
                    width: '32px',
                    height: '32px',
                    zIndex: 32,
                  }}
                  onMouseEnter={(e) => {
                    e.stopPropagation()
                    setHoveredCellArea({ channelId, date, area: 'plus' })
                  }}
                  onMouseLeave={(e) => {
                    e.stopPropagation()
                    const relatedTarget = e.relatedTarget as HTMLElement | null
                    const isMovingToCell = relatedTarget && typeof relatedTarget.closest === 'function'
                      ? relatedTarget.closest(`td[data-cell-id="${channelId}-${date}"]`)
                      : null
                    
                    if (isMovingToCell) {
                      setHoveredCellArea({ channelId, date, area: 'other' })
                    } else {
                      setHoveredCellArea(null)
                    }
                  }}
                  onClick={(e) => {
                    e.stopPropagation()
                    handleScaffoldActivePlusClick(channelId, date)
                  }}
                >
                  <PlusIcon 
                    isHovered={isHoveredPlus} 
                    isActive={isHoveredPlus || shouldHighlightFromPlusHover}
                  />
                </div>
              </div>
            )}
            
            {/* 十字区域背景层 - 用于检测hover和点击 */}
            {(isScaffold || isActive) && (
              <div 
                className="absolute inset-0 flex items-center justify-center pointer-events-none"
              >
                {/* 十字区域背景（中心区域，用于检测hover） */}
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ 
                    opacity: isHoveredPlus 
                      ? 0.15 
                      : 0,
                  }}
                  transition={{ duration: 0.2 }}
                  className="w-[90%] h-[90%] rounded-md pointer-events-none"
                  style={{
                    backgroundColor: isScaffold ? 'rgba(16, 185, 129, 0.08)' : 'rgba(207, 255, 56, 0.05)',
                  }}
                />
              </div>
            )}
          </motion.div>
      </td>
    )
  }
  
  // Get channel display name
  const getChannelDisplayName = (channelId: string): string => {
    if (channelId === 'kat_lofi') {
      return 'Kat Records'
    }
    return channelId
  }
  
  return (
    <>
      {/* Workflow automation: Backend handles all production stages. Frontend monitors progress via WebSocket. */}
      
    <div 
      className="w-full"
      style={{ 
        overflowX: 'auto',
        overflowY: 'visible',
        scrollbarWidth: 'thin',
        WebkitOverflowScrolling: 'touch',
        msOverflowStyle: '-ms-autohiding-scrollbar',
      }}
    >
      <table
        className="border-collapse border"
        style={{ 
          borderColor: GRID_BORDER_COLOR,
          width: 'max-content',
          minWidth: '100%',
          tableLayout: 'fixed',
        }}
      >
        <colgroup>
          <col style={{ width: '100px', minWidth: '100px' }} />
          {completedDatesRange && <col style={{ width: '60px', minWidth: '60px' }} />}
          {dateArray.map(() => (
            <col key={Math.random()} style={{ width: '60px', minWidth: '60px' }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            <th
              className="h-14 px-2 text-center text-xs font-medium text-dark-text-muted border-b border-r bg-dark-bg-secondary/85 sticky left-0 z-20"
              style={{
                backdropFilter: 'blur(4px)',
                WebkitBackdropFilter: 'blur(4px)',
                borderColor: GRID_BORDER_COLOR,
              }}
            >
              <div className="flex flex-col items-center justify-center">
                <span className="text-xs font-semibold text-dark-text">频道名称</span>
                <span className="text-[10px] text-dark-text-muted">Kat Records</span>
              </div>
            </th>
            {completedDatesRange && (() => {
              const fromDate = new Date(completedDatesRange.from)
              const toDate = new Date(completedDatesRange.to)
              const fromDay = fromDate.getDate()
              const toDay = toDate.getDate()
              const fromMonth = fromDate.getMonth() + 1
              const toMonth = toDate.getMonth() + 1
              const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
              const fromWeekday = weekdays[fromDate.getDay()]
              const toWeekday = weekdays[toDate.getDay()]
              
              // 如果同一个月，只显示一次月份
              const showMonth = fromMonth === toMonth
              
              return (
            <th
              key="completed-range"
              className="h-14 px-1 text-center text-xs font-medium text-dark-text-muted border-b border-r bg-dark-bg-secondary/85"
              style={{
                backdropFilter: 'blur(4px)',
                WebkitBackdropFilter: 'blur(4px)',
                borderColor: GRID_BORDER_COLOR,
                borderWidth: '2px',
              }}
            >
              <div className="flex flex-col items-center justify-center gap-0.5">
                <span className="text-sm font-semibold text-dark-text">{fromDay} - {toDay}</span>
                <span className="text-[10px] text-dark-text-muted">{fromWeekday} - {toWeekday}</span>
                {showMonth ? (
                  <span className="text-[10px] opacity-60 text-dark-text-muted">{fromMonth}月</span>
                ) : (
                  <span className="text-[10px] opacity-60 text-dark-text-muted">{fromMonth}/{toMonth}月</span>
                )}
              </div>
            </th>
              )
            })()}
            {dateArray.map((date) => {
              const dateObj = new Date(date)
              const day = dateObj.getDate()
              const month = dateObj.getMonth() + 1
              const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
              const weekday = weekdays[dateObj.getDay()]
              return (
                <th
                  key={date}
                  className="h-14 px-0.5 text-center text-xs font-medium text-dark-text-muted border-b border-r bg-dark-bg-secondary/85"
                  style={{
                    backdropFilter: 'blur(4px)',
                    WebkitBackdropFilter: 'blur(4px)',
                    borderColor: GRID_BORDER_COLOR,
                  }}
                >
                  <div className="flex flex-col items-center justify-center gap-0.5">
                    <span className="text-sm font-semibold text-dark-text">{day}</span>
                    <span className="text-[10px] text-dark-text-muted">{weekday}</span>
                    <span className="text-[10px] opacity-60 text-dark-text-muted">{month}月</span>
                  </div>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {channels.map((channelId) => {
            const channelEvents = eventsByChannelAndDate[channelId] || {}
            
            return (
              <tr key={channelId}>
                <td
                  className="h-28 px-1 py-2 border-r border-b bg-dark-bg-secondary/85 sticky left-0 z-10 text-center"
                style={{
                    backdropFilter: 'blur(4px)',
                    WebkitBackdropFilter: 'blur(4px)',
                    borderColor: GRID_BORDER_COLOR,
                  }}
                >
                  <div className="flex flex-col items-center justify-center h-full gap-0.5">
                    <span className="text-xs font-semibold text-dark-text">
                      {getChannelDisplayName(channelId)}
                    </span>
                    {/* Reset button - below channel name */}
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation()
                        setResetDialogOpen({ channelId })
                                    }}
                      onMouseEnter={(e) => e.stopPropagation()}
                      onMouseLeave={(e) => e.stopPropagation()}
                      className="group flex items-center gap-1.5 px-1.5 py-0.5 rounded transition-all duration-200 bg-transparent hover:bg-red-500"
                      title="重置频道"
                    >
                      <RotateCcw className="w-3 h-3 text-red-500/70 group-hover:text-white transition-colors duration-200" />
                      <span className="text-xs font-light text-red-500/0 group-hover:text-red-500/0 group-hover:text-white transition-all duration-200 opacity-0 group-hover:opacity-100 whitespace-nowrap">
                        Reset
                      </span>
                                  </button>
                  </div>
                </td>
                {completedDatesRange && (
                  <td
                    key="completed-range-cell"
                    className="h-28 px-1 py-2 border-r border-b bg-dark-bg-secondary/85 text-center"
                    style={{
                      backdropFilter: 'blur(4px)',
                      WebkitBackdropFilter: 'blur(4px)',
                      borderColor: GRID_BORDER_COLOR,
                      borderWidth: '2px',
                    }}
                  >
                    <div className="flex flex-col items-center justify-center h-full">
                      <div className="w-full h-full flex items-center justify-center border-2 border-solid border-dark-text-muted/30 rounded-md bg-dark-bg/50">
                        <div className="text-center text-[10px] text-dark-text-muted leading-tight px-0.5">
                          <div>已经上传</div>
                          <div>排播完毕</div>
                        </div>
                      </div>
                    </div>
                  </td>
                )}
                {dateArray.map((date) => {
                  // Double-check: exclude dates before work cursor (should not happen, but safety check)
                  // Also exclude dates that are in completedDatesRange
                  if (workCursorDate && date < workCursorDate) {
                    return null
                  }
                  if (completedDatesRange && date >= completedDatesRange.from && date <= completedDatesRange.to) {
                    return null
                  }
                  
                  const cellEvents = channelEvents[date] || []
                  
                  if (cellEvents.length === 0) {
                    return renderEmptyCell(channelId, date)
                  } else {
                    return renderEventCell(channelId, date, cellEvents)
                  }
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
      
      {/* Reset Confirm Dialog */}
      {resetDialogOpen && (
        <ResetConfirmDialog
          isOpen={true}
          onClose={() => setResetDialogOpen(null)}
          onConfirm={() => handleResetConfirm(resetDialogOpen.channelId)}
          channelId={resetDialogOpen.channelId}
        />
      )}
      
    </div>
    </>
  )
}
