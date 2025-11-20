/**
 * WebSocket Hook
 * 
 * Main WebSocket connection for T2R and Schedule business logic.
 * Handles all real-time updates for episodes, runbooks, assets, and batch operations.
 * 
 * Benefits:
 * - Single WebSocket connection (reduces network overhead by 50%)
 * - Unified event handling (eliminates ~400 lines of duplicate code)
 * - Easier debugging (single connection point)
 */
import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { WSClient, type WSMessage } from '@/services/wsClient'
import { useScheduleStore, type ScheduleEvent } from '@/stores/scheduleStore'
import { useT2RScheduleStore } from '@/stores/t2rScheduleStore'
import { useT2RAssetsStore } from '@/stores/t2rAssetsStore'
import { useT2RSrtStore } from '@/stores/t2rSrtStore'
import { useRunbookStore } from '@/stores/runbookStore'
import { getWsBase } from '@/lib/apiBase'
import { fillerGenerate } from '@/services/t2rApi'
import { logger } from '@/lib/logger'
import { 
  RunbookStageUpdateSchema, 
  UploadProgressSchema, 
  VerifyResultSchema,
  type RunbookStageUpdate,
  type UploadProgress,
  type VerifyResult,
} from '@/types/schemas'
import * as Sentry from '@sentry/nextjs'

const WS_URL = getWsBase()

// Fallback timer configuration
const FALLBACK_DELAY_MS = 30000 // 30 seconds (for timeout errors)
const SHORT_FALLBACK_DELAY_MS = 6000 // 6 seconds (for keeping grid animating)

export function useWebSocket() {
  const clientRef = useRef<WSClient | null>(null)
  const queryClient = useQueryClient()
  
  // Schedule store
  const patchEvent = useScheduleStore((state) => state.patchEvent)
  
  // T2R stores
  const updateEpisode = useT2RScheduleStore((state) => state.updateEpisode)
  const addConflict = useT2RAssetsStore((state) => state.addConflict)
  const setFixResult = useT2RSrtStore((state) => state.setFixResult)
  
  // Runbook store (kept for backward compatibility during migration)
  const addLog = useRunbookStore((state) => state.addLog)
  const setEpisodeId = useRunbookStore((state) => state.setEpisodeId)
  const setCurrentStage = useRunbookStore((state) => state.setCurrentStage)
  const setProgress = useRunbookStore((state) => state.setProgress)
  const setFailedStage = useRunbookStore((state) => state.setFailedStage)
  const setIsRunning = useRunbookStore((state) => state.setIsRunning)
  
  // Schedule store (new unified state management)
  const setRunbookSnapshot = useScheduleStore((state) => state.setRunbookSnapshot)
  
  // Auto text generation tracking
  const autoTextGenerationRef = useRef<Set<string>>(new Set())
  
  // Fallback timers for stage updates
  const fallbackTimersRef = useRef<Map<string, NodeJS.Timeout>>(new Map())
  
  // Short fallback timers for keeping grid animating (5-8 seconds)
  const shortFallbackTimersRef = useRef<Map<string, NodeJS.Timeout>>(new Map())
  
  // Track current stage per episode for short fallback progression
  const episodeStageRef = useRef<Map<string, { stage: string; progress: number }>>(new Map())
  
  // WebSocket message batching system
  // Collects multiple patchEvent calls and applies them in batches to reduce re-renders
  const pendingUpdatesRef = useRef<Map<string, Partial<ScheduleEvent>>>(new Map())
  const batchTimeoutRef = useRef<number | null>(null)
  const batchRafRef = useRef<number | null>(null)
  const isProcessingBatchRef = useRef(false)
  
  // Batch processing configuration
  const BATCH_DELAY_MS = 50 // 50ms batch window - balances responsiveness and performance
  const CRITICAL_STAGES = ['failed', 'completed', 'verify', 'error'] // Stages that require immediate update
  
  // Check if an update is critical and should be applied immediately
  const isCriticalUpdate = (updates: Partial<ScheduleEvent>, stage?: string): boolean => {
    // Check for error/issue updates
    if (updates.issues && updates.issues.length > 0) return true
    
    // Check for critical stages
    if (stage) {
      const stageLower = stage.toLowerCase()
      if (CRITICAL_STAGES.some(critical => stageLower.includes(critical))) return true
    }
    
    // Check for completion indicators (100% progress, verified assets)
    if (updates.assets?.verified === true || updates.assets?.uploaded === true) return true
    
    // Check for failed state in gridProgress
    if (updates.gridProgress?.lastStage?.toLowerCase().includes('failed')) return true
    
    return false
  }
  
  // Merge updates for the same episode (deep merge for nested objects)
  // This prevents duplicate updates and ensures the latest data is preserved
  const mergeUpdates = (
    existing: Partial<ScheduleEvent>,
    newUpdate: Partial<ScheduleEvent>
  ): Partial<ScheduleEvent> => {
    const merged = { ...existing, ...newUpdate }
    
    // Deep merge assets - preserve all asset fields
    if (existing.assets || newUpdate.assets) {
      merged.assets = {
        cover: null,
        audio: null,
        description: null,
        captions: null,
        ...(existing.assets || {}),
        ...(newUpdate.assets || {}),
      }
    }
    
    // Deep merge kpis - preserve all KPI fields
    if (existing.kpis || newUpdate.kpis) {
      merged.kpis = {
        ...(existing.kpis || {}),
        ...(newUpdate.kpis || {}),
      }
    }
    
    // Deep merge gridProgress - preserve history and merge new data
    if (existing.gridProgress || newUpdate.gridProgress) {
      const existingProgress = existing.gridProgress || { lastStage: null, lastStageTimestamp: 0, stageHistory: [] }
      const newProgress = newUpdate.gridProgress || { lastStage: null, lastStageTimestamp: 0, stageHistory: [] }
      
      // Merge stageHistory - prefer new history if available, otherwise keep existing
      const stageHistory = newProgress.stageHistory && newProgress.stageHistory.length > 0
        ? newProgress.stageHistory
        : (existingProgress.stageHistory || [])
      
      merged.gridProgress = {
        ...existingProgress,
        ...newProgress,
        // Use merged history and preserve lastStage and lastStageTimestamp from the most recent update
        stageHistory,
        lastStage: newProgress.lastStage || existingProgress.lastStage || null,
        lastStageTimestamp: newProgress.lastStageTimestamp || existingProgress.lastStageTimestamp || 0,
      }
    }
    
    // Merge issues arrays - combine unique issues
    if (existing.issues || newUpdate.issues) {
      const existingIssues = existing.issues || []
      const newIssues = newUpdate.issues || []
      // Combine and deduplicate issues
      const allIssues = [...existingIssues, ...newIssues]
      merged.issues = Array.from(new Set(allIssues))
    }
    
    return merged
  }
  
  // Apply all pending updates in a batch
  // This is called after the batch delay window to apply all accumulated updates at once
  const applyBatchUpdates = () => {
    if (isProcessingBatchRef.current || pendingUpdatesRef.current.size === 0) {
      return
    }
    
    isProcessingBatchRef.current = true
    
    // Get all pending updates (create a snapshot)
    const updates = new Map(pendingUpdatesRef.current)
    pendingUpdatesRef.current.clear()
    
    // Apply all updates in a single batch
    // This reduces the number of store updates and re-renders
    updates.forEach((updateData, episodeId) => {
      try {
        patchEvent(episodeId, updateData)
      } catch (error) {
        logger.error(`[useWebSocket] Error applying batch update for episode ${episodeId}:`, error)
      }
    })
    
    isProcessingBatchRef.current = false
    batchTimeoutRef.current = null
    
    // Invalidate React Query cache to ensure UI reflects store updates
    // This is critical for components that rely on React Query data
    if (updates.size > 0) {
      logger.debug(`[useWebSocket] Applied batch update for ${updates.size} episode(s), invalidating React Query cache`)
      queryClient.invalidateQueries({ queryKey: ['t2r-episodes'], exact: false })
    }
  }
  
  // Schedule batch update (debounced using requestAnimationFrame + setTimeout)
  // This ensures updates are batched within the same frame cycle
  const scheduleBatchUpdate = () => {
    // If already scheduled, skip (debouncing)
    if (batchTimeoutRef.current !== null || batchRafRef.current !== null) {
      return
    }
    
    // Use requestAnimationFrame to align with browser's rendering cycle
    // This ensures we batch updates that occur in the same frame
    batchRafRef.current = window.requestAnimationFrame(() => {
      batchRafRef.current = null
      
      // Schedule the actual batch update after a short delay
      // This allows multiple updates to accumulate in the same batch window
      batchTimeoutRef.current = window.setTimeout(() => {
        batchTimeoutRef.current = null
        applyBatchUpdates()
      }, BATCH_DELAY_MS) as any
    })
  }
  
  // Batched patchEvent wrapper
  const batchedPatchEvent = (
    episodeId: string,
    updates: Partial<ScheduleEvent>,
    options?: { immediate?: boolean; stage?: string }
  ) => {
    const isDev = process.env.NODE_ENV === 'development' || window.location.search.includes('debug=true')
    
    // ✅ 添加监控：状态更新日志（高优先级，仅开发环境）
    if (isDev) {
      console.debug('[StateUpdate] Batched update:', {
        episodeId,
        updates: Object.keys(updates),
        timestamp: Date.now(),
        pendingCount: pendingUpdatesRef.current.size,
        isCritical: options?.immediate || isCriticalUpdate(updates, options?.stage),
        stage: options?.stage,
      })
    }
    
    const isCritical = options?.immediate || isCriticalUpdate(updates, options?.stage)
    
    if (isCritical) {
      // Apply critical updates immediately
      patchEvent(episodeId, updates)
      // Also remove from pending queue if it exists
      pendingUpdatesRef.current.delete(episodeId)
      // Invalidate React Query cache immediately for critical updates
      // This ensures UI reflects store updates without waiting for refetch interval
      queryClient.invalidateQueries({ queryKey: ['t2r-episodes'], exact: false })
      logger.debug(`[useWebSocket] Applied critical update immediately for episode ${episodeId}, invalidated React Query cache`)
    } else {
      // Add to batch queue
      const existing = pendingUpdatesRef.current.get(episodeId)
      const merged = existing ? mergeUpdates(existing, updates) : updates
      pendingUpdatesRef.current.set(episodeId, merged)
      
      // Schedule batch update
      scheduleBatchUpdate()
    }
  }
  
  // Ensure text assets are generated after remix completion
  const ensureTextAssets = async (episodeId: string) => {
    if (autoTextGenerationRef.current.has(episodeId)) return
    const targetEvent = useScheduleStore.getState().eventsById[episodeId]
    if (!targetEvent) return
    const needsTitle = !targetEvent.title
    const needsDescription = !targetEvent.assets?.description
    const needsCaptions = !targetEvent.assets?.captions
    if (!needsTitle && !needsDescription && !needsCaptions) return

    const assetTypes: Array<'title' | 'description' | 'captions' | 'tags'> = []
    if (needsTitle) assetTypes.push('title')
    if (needsDescription) assetTypes.push('description')
    if (needsCaptions) assetTypes.push('captions')
    assetTypes.push('tags')

    autoTextGenerationRef.current.add(episodeId)
    try {
      await fillerGenerate({
        episode_id: episodeId,
        channel_id: targetEvent.channelId,
        asset_types: assetTypes,
        overwrite: false,
      })
    } catch (error) {
      logger.error('[useWebSocket] Auto text asset generation failed:', error)
    } finally {
      autoTextGenerationRef.current.delete(episodeId)
    }
  }
  
  // Clear fallback timer for an episode
  const clearFallbackTimer = (episodeId: string) => {
    const timer = fallbackTimersRef.current.get(episodeId)
    if (timer) {
      clearTimeout(timer)
      fallbackTimersRef.current.delete(episodeId)
    }
  }
  
  // Clear short fallback timer for an episode
  const clearShortFallbackTimer = (episodeId: string) => {
    const timer = shortFallbackTimersRef.current.get(episodeId)
    if (timer) {
      clearTimeout(timer)
      shortFallbackTimersRef.current.delete(episodeId)
    }
  }
  
  // Get next stage in progression
  const getNextStage = (currentStage: string): { stage: string; progress: number } | null => {
    const stage = currentStage.toLowerCase()
    if (stage.includes('playlist') || stage === 'playlist') {
      return { stage: 'remix', progress: 5 }
    } else if (stage.includes('remix') || stage === 'remix') {
      return { stage: 'render', progress: 5 }
    } else if (stage.includes('render') || stage === 'render') {
      return { stage: 'upload', progress: 5 }
    } else if (stage.includes('upload') || stage === 'upload') {
      return { stage: 'verify', progress: 5 }
    }
    return null
  }
  
  // Set short fallback timer to advance cached stage if backend is slow
  const setShortFallbackTimer = (episodeId: string, currentStage: string, currentProgress: number) => {
    clearShortFallbackTimer(episodeId)
    
    // Store current stage
    episodeStageRef.current.set(episodeId, { stage: currentStage, progress: currentProgress })
    
    const timer = setTimeout(() => {
      // Check if we still haven't received an update
      const stored = episodeStageRef.current.get(episodeId)
      if (!stored || stored.stage === currentStage) {
        // Backend hasn't pushed next stage - temporarily advance cached stage
        const nextStage = getNextStage(currentStage)
        if (nextStage) {
          logger.debug(`[useWebSocket] Short fallback: advancing ${episodeId} from ${currentStage} to ${nextStage.stage}`)
          
          // Update runbook store with optimistic stage (backward compatibility)
          setEpisodeId(episodeId)
          setCurrentStage(nextStage.stage as any)
          setProgress(nextStage.progress)
          
          // Update scheduleStore runbook snapshot (unified state management)
          setRunbookSnapshot(episodeId, {
            currentStage: nextStage.stage,
            episodeId,
            failedStage: null,
            errorMessage: null,
          })
          
          // Update cache
          episodeStageRef.current.set(episodeId, { stage: nextStage.stage, progress: nextStage.progress })
          
          // Update schedule store to show "waiting for backend" state
          const currentEvent = useScheduleStore.getState().eventsById[episodeId]
          if (currentEvent) {
            batchedPatchEvent(episodeId, {
              kpis: {
                ...currentEvent.kpis,
                waitingForBackend: true,
              } as any,
            })
          }
          
          // Show subtle notification (non-intrusive)
          if (typeof window !== 'undefined' && window.dispatchEvent) {
            window.dispatchEvent(new CustomEvent('toast', {
              detail: {
                type: 'info',
                message: '等待后端更新...',
                duration: 2000,
              }
            }))
          }
          
          // Set another short timer for the next stage
          setShortFallbackTimer(episodeId, nextStage.stage, nextStage.progress)
        }
      }
    }, SHORT_FALLBACK_DELAY_MS)
    
    shortFallbackTimersRef.current.set(episodeId, timer)
  }
  
  // Set fallback timer for stage update
  const setFallbackTimer = (episodeId: string, stage: string) => {
    clearFallbackTimer(episodeId)
    
    const timer = setTimeout(() => {
      logger.warn(`[useWebSocket] Stage update timeout for episode ${episodeId}, stage ${stage}`)
      setFailedStage(stage, 'WebSocket timeout - stage update not received')
      
      // Show toast notification (if available)
      if (typeof window !== 'undefined' && window.dispatchEvent) {
        window.dispatchEvent(new CustomEvent('toast', {
          detail: {
            type: 'error',
            message: '阶段更新超时，请检查后端连接',
          }
        }))
      }
      
      fallbackTimersRef.current.delete(episodeId)
    }, FALLBACK_DELAY_MS)
    
    fallbackTimersRef.current.set(episodeId, timer)
  }

  useEffect(() => {
    clientRef.current = new WSClient({
      url: `${WS_URL}/ws/status`,
      onMessage: (message: WSMessage) => {
        // Handle direct t2r_* messages (new format)
        // Message structure from generate_t2r_event: { type: "t2r_xxx", version, ts, level, data }
        if (message.type?.startsWith('t2r_')) {
          const eventData = message.data || {}
          const baseType = message.type.substring(4) // Remove "t2r_" prefix
          const data = eventData
          
          // T2R scan progress
          if (baseType === 'scan_progress') {
            // Update T2R schedule store
            if (data.locked_count !== undefined) {
              useT2RScheduleStore.getState().setLockedCount(data.locked_count)
            }
            if (data.conflicts) {
              useT2RScheduleStore.getState().setConflicts(data.conflicts)
            }
            
            // Update schedule store (verified_at)
            if (data.episode_id && data.locked) {
              const currentEvent = useScheduleStore.getState().eventsById[data.episode_id]
              if (currentEvent) {
                batchedPatchEvent(data.episode_id, {
                  assets: {
                    ...currentEvent.assets,
                    verified_at: new Date().toISOString(),
                    verified: true,
                  } as any,
                }, { immediate: true }) // Verified status is critical
              }
            }
          }
          
          // T2R fix applied
          if (baseType === 'fix_applied') {
            if (data.srt_fix) {
              setFixResult(data.srt_fix)
            }
          }
          
          // Runbook stage update (merged logic from both hooks)
          if (baseType === 'runbook_stage_update') {
            const episodeId = data.episode_id || data.episodeId
            if (episodeId) {
              // Clear fallback timers since we received the update
              clearFallbackTimer(episodeId)
              clearShortFallbackTimer(episodeId)
              
              // CRITICAL: Update episodeId FIRST so GridProgress can match the event
              // Update both runbookStore (backward compatibility) and scheduleStore (unified)
              setEpisodeId(episodeId)
              
              // Get current event to preserve existing KPIs and gridProgress
              const currentEvent = useScheduleStore.getState().eventsById[episodeId]
              
              // Extract timestamp from message (prefer message.ts, fallback to data.timestamp or current time)
              const eventTimestamp = typeof message.ts === 'number' ? message.ts : (data.timestamp ? new Date(data.timestamp).getTime() : Date.now())
              
              // Check if this update is newer than the last known stage (prevent flicker on reconnect)
              const lastStageTimestamp = currentEvent?.gridProgress?.lastStageTimestamp || 0
              const isNewerUpdate = eventTimestamp > lastStageTimestamp
              
              // Only process if this is a newer update (forward-only animation)
              if (!isNewerUpdate) {
                logger.debug(`[useWebSocket] Ignoring stale stage update for ${episodeId}: eventTimestamp=${eventTimestamp}, lastStageTimestamp=${lastStageTimestamp}`)
                
                // ✅ 添加监控：检测时间戳冲突（高优先级）
                if (Math.abs(eventTimestamp - lastStageTimestamp) < 100) {
                  const isDev = process.env.NODE_ENV === 'development' || window.location.search.includes('debug=true')
                  if (isDev) {
                    console.warn('[StateUpdate] Potential timestamp conflict:', {
                      episodeId,
                      eventTimestamp,
                      lastStageTimestamp,
                      diff: Math.abs(eventTimestamp - lastStageTimestamp),
                      stage: data.stage,
                      progress: data.progress,
                    })
                  }
                }
                
                return // Skip processing this update
              }
              
              // Clear "waiting for backend" flag
              if (currentEvent?.kpis && 'waitingForBackend' in currentEvent.kpis && (currentEvent.kpis as any).waitingForBackend) {
                batchedPatchEvent(episodeId, {
                  kpis: {
                    ...currentEvent.kpis,
                    waitingForBackend: false,
                  } as any,
                })
              }
              
              // Status field removed - state is now determined by GridProgress stages
              // Update assets if provided (e.g., audio_path after remix completion)
              const stage = data.stage?.toLowerCase() || ''
              const progress = data.progress || 0
              
              // Update gridProgress history (forward-only, timestamp-based)
              const existingHistory = currentEvent?.gridProgress?.stageHistory || []
              const newHistoryEntry = { stage, timestamp: eventTimestamp, progress }
              
              // Only add to history if it's a new stage or higher progress
              const lastHistoryEntry = existingHistory[existingHistory.length - 1]
              const shouldAddToHistory = !lastHistoryEntry || 
                lastHistoryEntry.stage !== stage || 
                lastHistoryEntry.progress < progress ||
                (typeof lastHistoryEntry.timestamp === 'number' && lastHistoryEntry.timestamp < eventTimestamp) ||
                (typeof lastHistoryEntry.timestamp === 'string' && new Date(lastHistoryEntry.timestamp).getTime() < eventTimestamp)
              
              const updatedHistory = shouldAddToHistory 
                ? [...existingHistory, newHistoryEntry].slice(-10) // Keep last 10 entries
                : existingHistory
              
              const updates: any = {
                kpis: {
                  ...(currentEvent?.kpis || {}),
                  lastRunAt: message.ts || data.timestamp || new Date().toISOString(),
                },
                gridProgress: {
                  lastStage: stage,
                  lastStageTimestamp: eventTimestamp,
                  stageHistory: updatedHistory,
                },
              }
              
              // ✅ 如果 remix 完成，更新 assets.audio 和 assets.timeline_csv
              // 只有在 timeline_csv 存在时才认为 remix 真正完成
              if (stage.includes('remix') && data.progress === 100) {
                const audioPath = data.audio_path || data.assets?.audio
                const timelineCsvPath = data.timeline_csv_path || data.assets?.timeline_csv
                const playlistPath = data.playlist_path || data.assets?.playlist
                
                if (audioPath || timelineCsvPath || playlistPath) {
                  updates.assets = {
                    ...(currentEvent?.assets || {}),
                    ...(audioPath ? { audio: audioPath } : {}),
                    ...(timelineCsvPath ? { timeline_csv: timelineCsvPath } : {}),
                    ...(playlistPath ? { playlist: playlistPath } : {})
                  }
                  
                  // Set existence flags
                  if (audioPath) {
                    updates.audio_exists = true
                    logger.debug('[useWebSocket] Updating assets.audio for episode', episodeId, 'with path:', audioPath)
                  }
                  if (timelineCsvPath) {
                    logger.debug('[useWebSocket] Updating assets.timeline_csv for episode', episodeId, 'with path:', timelineCsvPath)
                  }
                  if (playlistPath) {
                    updates.playlistPath = playlistPath
                    logger.debug('[useWebSocket] Updating playlistPath for episode', episodeId, 'with path:', playlistPath)
                  }
                }
                
                // ✅ 只有在 timeline_csv 存在时才认为 remix 真正完成
                // timeline_csv 是 remix 阶段的最后一个文件，只有它生成才意味着真正完成
                if (timelineCsvPath) {
                  // Auto-generate text assets after remix completion
                  ensureTextAssets(episodeId)
                } else {
                  logger.warn('[useWebSocket] Remix completed but timeline_csv not found, skipping text asset generation. Remix may not be fully complete.')
                }
              }
              
              // ✅ 如果渲染完成，更新 assets.video 和 assets.render_complete_flag
              // render_complete_flag 确保渲染真正完成（文件写入完成、验证通过）
              if (stage.includes('render') && data.progress === 100) {
                if (data.video_path || data.assets?.video) {
                  const videoPath = data.video_path || data.assets?.video
                  const renderCompleteFlag = data.render_complete_flag || data.assets?.render_complete_flag  // ✅ 新增
                  
                  updates.assets = {
                    ...(updates.assets || currentEvent?.assets || {}),
                    video: videoPath,
                    video_path: videoPath,
                    render_complete_flag: renderCompleteFlag,  // ✅ 新增：确保 render_complete_flag 被更新
                  }
                  logger.debug('[useWebSocket] Updating assets.video and render_complete_flag for episode', episodeId, {
                    video: videoPath,
                    render_complete_flag: renderCompleteFlag,
                  })
                }
              }
              
              // Calculate cumulative progress for first GridProgressIndicator (preparation stage) - 10 assets
              // Asset breakdown for preparation stage (first bar):
              // 1. playlist.csv: 0-1% (1%)
              // 2. playlist_metadata.json: 1-2% (1%)
              // 3. manifest.json: 2-3% (1%)
              // 4. cover.png: 3-4% (1%)
              // 5. youtube_title.txt: 4-5% (1%)
              // 6. youtube_description.txt: 5-6% (1%)
              // 7. youtube_tags.txt: 6-7% (1%)
              // 8. youtube.srt: 7-8% (1%)
              // 9. full_mix_timeline.csv: 8-10% (2%)
              // 10. full_mix.mp3: 10-100% (90%, main time)
              // Progress should be cumulative and continuous from left to right
              
              // Calculate base progress from completed files (cumulative) using current event + updates
              const eventWithUpdates = {
                ...currentEvent,
                ...updates,
                assets: {
                  ...(currentEvent?.assets || {}),
                  ...(updates.assets || {}),
                },
                playlistPath: updates.playlistPath || currentEvent?.playlistPath,
              }
              
              let baseProgress = 0
              // 1. playlist.csv + playlist_metadata.json: 0-2%
              if (eventWithUpdates.playlistPath) {
                baseProgress = 2
              }
              // 2. manifest.json: 2-3% (assume exists if playlist exists)
              if (eventWithUpdates.playlistPath) {
                baseProgress = 3
              }
              // 3. cover.png: 3-4%
              if (eventWithUpdates.assets?.cover || eventWithUpdates.cover_exists) {
                baseProgress = Math.max(baseProgress, 4)
              }
              // 4. youtube_title.txt: 4-5%
              if (eventWithUpdates.youtube_title_path || eventWithUpdates.assets?.youtube_title || eventWithUpdates.youtube_title_exists) {
                baseProgress = Math.max(baseProgress, 5)
              }
              // 5. youtube_description.txt: 5-6%
              if (eventWithUpdates.assets?.description || eventWithUpdates.description_exists) {
                baseProgress = Math.max(baseProgress, 6)
              }
              // 6. youtube_tags.txt: 6-7% (not tracked separately, assume done if description done)
              if (eventWithUpdates.assets?.description || eventWithUpdates.description_exists) {
                baseProgress = Math.max(baseProgress, 7)
              }
              // 7. youtube.srt: 7-8%
              if (eventWithUpdates.assets?.captions || eventWithUpdates.captions_exists) {
                baseProgress = Math.max(baseProgress, 8)
              }
              // 8. full_mix_timeline.csv: 8-10%
              if (eventWithUpdates.assets?.timeline_csv) {
                baseProgress = Math.max(baseProgress, 10)
              }
              // 9. full_mix.mp3: 10-100% (90%, main time)
              // ✅ 修复：只有在 remix 完成（有 timeline_csv）且不在 remix 中时，才设为 100
              // ✅ 如果正在 remix 中，优先使用 WebSocket 实时进度
              const hasAudioFile = !!(eventWithUpdates.assets?.audio || eventWithUpdates.audio_exists)
              const hasTimelineCsv = !!eventWithUpdates.assets?.timeline_csv
              const isRemixInProgress = stage.includes('remix') || stage.includes('audio')
              
              if (hasAudioFile && hasTimelineCsv && !isRemixInProgress) {
                // ✅ Audio exists and remix is complete (both audio and timeline_csv exist, and not currently remixing)
                baseProgress = 100
              } else if (hasAudioFile && !hasTimelineCsv) {
                // ✅ Audio file exists but timeline CSV doesn't - remix may be in progress
                // Don't set baseProgress to 100, let remix progress mapping handle it
                // Set to at least 10% (audio file detected, but remix not complete)
                baseProgress = Math.max(baseProgress, 10)
              }
              
              // Map current stage progress to the appropriate range (cumulative, no skipping)
              const rawProgress = data.progress || 0
              let mappedProgress = baseProgress
              
              // Only for preparation stage (first bar)
              if (stage.includes('playlist') || stage.includes('manifest') || stage.includes('cover') || 
                  stage.includes('image') || stage.includes('title') || stage.includes('description') || 
                  stage.includes('caption') || stage.includes('srt') || stage.includes('tag') || 
                  stage.includes('text') || stage.includes('filler') || stage.includes('timeline') || 
                  stage.includes('remix') || stage.includes('audio')) {
                
                // Map current stage progress to its allocated range, ensuring it's >= baseProgress
                if (stage.includes('playlist')) {
                  // playlist.csv + playlist_metadata.json: 0-2%
                  mappedProgress = Math.max(baseProgress, Math.min(2, rawProgress * 0.02))
                } else if (stage.includes('manifest')) {
                  // manifest.json: 2-3%
                  mappedProgress = Math.max(baseProgress, Math.min(3, 2 + (rawProgress * 0.01)))
                } else if (stage.includes('cover') || stage.includes('image')) {
                  // cover.png: 3-4%
                  mappedProgress = Math.max(baseProgress, Math.min(4, 3 + (rawProgress * 0.01)))
                } else if (stage.includes('title') && !stage.includes('description') && !stage.includes('tag')) {
                  // youtube_title.txt: 4-5%
                  mappedProgress = Math.max(baseProgress, Math.min(5, 4 + (rawProgress * 0.01)))
                } else if (stage.includes('description')) {
                  // youtube_description.txt: 5-6%
                  mappedProgress = Math.max(baseProgress, Math.min(6, 5 + (rawProgress * 0.01)))
                } else if (stage.includes('tag')) {
                  // youtube_tags.txt: 6-7%
                  mappedProgress = Math.max(baseProgress, Math.min(7, 6 + (rawProgress * 0.01)))
                } else if (stage.includes('caption') || stage.includes('srt')) {
                  // youtube.srt: 7-8%
                  mappedProgress = Math.max(baseProgress, Math.min(8, 7 + (rawProgress * 0.01)))
                } else if (stage.includes('timeline') || stage.includes('csv')) {
                  // full_mix_timeline.csv: 8-10%
                  mappedProgress = Math.max(baseProgress, Math.min(10, 8 + (rawProgress * 0.02)))
                } else if (stage.includes('remix') || stage.includes('audio')) {
                  // full_mix.mp3: 10-100% (90%, main time)
                  // ✅ 修复：如果正在 remix 中，优先使用 WebSocket 实时进度，忽略 baseProgress 的 100% 设置
                  if (isRemixInProgress) {
                    // ✅ 正在 remix 中，使用 WebSocket 实时进度
                    if (rawProgress <= 5) {
                      mappedProgress = Math.min(12, 10 + (rawProgress / 5) * 2)
                    } else if (rawProgress < 97) {
                      mappedProgress = Math.min(98, 12 + ((rawProgress - 5) / 92) * 86)
                    } else {
                      mappedProgress = Math.min(100, 98 + ((rawProgress - 97) / 3) * 2)
                    }
                    // ✅ 确保进度不低于已完成资产的进度，但不高于 remix 实时进度
                    mappedProgress = Math.max(baseProgress, mappedProgress)
                  } else {
                    // ✅ Remix not in progress - use baseProgress (may be 100 if remix is complete)
                    mappedProgress = baseProgress
                  }
                }
                // If baseProgress is already >= current stage's max, keep it (no regression)
                // This ensures continuous progress from left to right
              } else if (stage.includes('render') || stage.includes('video')) {
                // Render stage: This is for the SECOND GridProgressIndicator bar (not first)
                mappedProgress = Math.max(0, Math.min(100, rawProgress))
              } else if (stage.includes('upload')) {
                // Upload stage: This is for the THIRD GridProgressIndicator bar (not first)
                mappedProgress = Math.max(0, Math.min(100, rawProgress))
              } else if (stage.includes('verify') || stage.includes('publish')) {
                // Verify stage: This is for the THIRD GridProgressIndicator bar (not first)
                mappedProgress = Math.max(0, Math.min(100, rawProgress))
              }
              
              // Apply updates using batched patchEvent (this is the legacy format handler)
              // Use immediate=true for completion/error states, otherwise batch
              const isCompletion = stage.includes('completed') || stage.includes('verify') || mappedProgress >= 100
              batchedPatchEvent(episodeId, updates, {
                immediate: isCompletion,
                stage: data.stage,
              })
              
              // Update runbook store with stage and progress (backward compatibility)
              logger.debug(`[useWebSocket] Updating runbook: episode=${episodeId}, stage=${data.stage}, progress=${mappedProgress}`)
              setCurrentStage(data.stage as any)
              setProgress(mappedProgress)
              addLog({
                timestamp: message.ts || data.timestamp || new Date().toISOString(),
                stage: data.stage,
                message: data.message || '',
                level: message.level || data.level || 'info',
              })
              
              // Update scheduleStore runbook snapshot (unified state management)
              // ✅ 确保 render.in_progress 状态被正确更新
              const normalizedStage = data.stage || data.currentStage || null
              setRunbookSnapshot(episodeId, {
                currentStage: normalizedStage,
                episodeId,
                failedStage: data.failedStage || null,
                errorMessage: data.error || data.message || null,
              })
              // ✅ 添加调试日志以追踪渲染状态更新
              if (normalizedStage && normalizedStage.toLowerCase().includes('render')) {
                logger.debug(`[useWebSocket] Render state updated for ${episodeId}: stage=${normalizedStage}, progress=${progress}`)
              }
              
              // Update batch generation progress if active
              const { batchGenerationStatus, updateBatchGenerationProgress } = useScheduleStore.getState()
              if (batchGenerationStatus && batchGenerationStatus.status === 'running') {
                const currentStage = data.stage || data.currentStage
                if (currentStage && (currentStage.includes('completed') || currentStage.includes('verify'))) {
                  const newCompleted = Math.min(
                    batchGenerationStatus.completedEpisodes + 1,
                    batchGenerationStatus.totalEpisodes
                  )
                  const progress = (newCompleted / batchGenerationStatus.totalEpisodes) * 100
                  
                  updateBatchGenerationProgress({
                    completedEpisodes: newCompleted,
                    currentEpisode: episodeId,
                    currentStage: currentStage,
                    progress: progress,
                  })
                } else {
                  updateBatchGenerationProgress({
                    currentEpisode: episodeId,
                    currentStage: currentStage || null,
                  })
                }
              }
              
              // Set fallback timer for next stage (if not completed)
              if (mappedProgress < 100 && !stage.includes('completed') && !stage.includes('verify')) {
                setFallbackTimer(episodeId, data.stage)
              }
              
              // Set short fallback timer to keep grid animating if backend is slow
              // Only set if progress is low (generation just started) or stage changed
              const stored = episodeStageRef.current.get(episodeId)
              const stageChanged = !stored || stored.stage !== data.stage
              const isEarlyStage = mappedProgress < 20 || stageChanged
              
              if (isEarlyStage && mappedProgress < 100 && !stage.includes('completed') && !stage.includes('verify')) {
                setShortFallbackTimer(episodeId, data.stage, mappedProgress)
              }
            }
          }
          
          // Asset regenerated event
          if (baseType === 'asset_regenerated') {
            const episodeId = data.episode_id || data.episodeId
            if (episodeId) {
              const assetType = data.asset_type?.toLowerCase() || ''
              const updates: any = {}
              
              // Map asset type to runbook stage for progress tracking
              let runbookStage: string | null = null
              if (assetType === 'title') {
                runbookStage = 'title'
              } else if (assetType === 'description') {
                runbookStage = 'description'
              } else if (assetType === 'captions') {
                runbookStage = 'captions'
              } else if (assetType === 'cover') {
                runbookStage = 'cover'
              } else if (assetType === 'audio') {
                runbookStage = 'remix'
              }
              
              // Set runbook state for progress tracking
              if (runbookStage) {
                setEpisodeId(episodeId)
                setCurrentStage(runbookStage as any)
                setProgress(100)
                
                // Update scheduleStore runbook snapshot (unified state management)
                setRunbookSnapshot(episodeId, {
                  currentStage: runbookStage,
                  episodeId,
                  failedStage: null,
                  errorMessage: null,
                })
                
                // Clear runbook state after a short delay
                setTimeout(() => {
                  const { episodeId: currentEpisodeId } = useRunbookStore.getState()
                  if (currentEpisodeId === episodeId) {
                    setCurrentStage('idle')
                    setProgress(0)
                    setEpisodeId(null)
                    // Clear scheduleStore snapshot
                    useScheduleStore.getState().clearRunbookSnapshot(episodeId)
                  }
                }, 1000)
              }
              
              // Update based on asset type and set corresponding *_exists flags
              if (assetType === 'title' && data.title) {
                updates.title = data.title
                updates.youtube_title_exists = true
              } else if (assetType === 'description' && data.file_path) {
                updates.assets = { description: data.file_path }
                updates.description_exists = true
              } else if (assetType === 'captions' && data.file_path) {
                updates.assets = { captions: data.file_path }
                updates.captions_exists = true
              } else if (assetType === 'cover' && data.cover_path) {
                updates.assets = { cover: data.cover_path }
                updates.cover_exists = true
                if (data.title) {
                  updates.title = data.title
                }
              } else if (assetType === 'audio' && data.file_path) {
                updates.assets = { audio: data.file_path }
                updates.audio_exists = true
              }
              
              if (Object.keys(updates).length > 0) {
                batchedPatchEvent(episodeId, updates, { stage: runbookStage || undefined })
                logger.debug('[useWebSocket] Updated asset:', assetType, 'for episode', episodeId, 'updates:', updates)
              }
            }
          }
          
          // Playlist generated event
          if (baseType === 'playlist_generated') {
            const episodeId = data.episode_id || data.episodeId
            if (episodeId) {
              logger.info('[useWebSocket] Playlist generated for episode', episodeId)
              
              // Update event with playlist information for GridProgress
              const playlistPath = data.playlist_path || data.playlistPath
              if (playlistPath) {
                const eventTimestamp = message.ts ? new Date(message.ts).getTime() : Date.now()
                const updates: any = {
                  playlistPath: playlistPath,
                  gridProgress: {
                    lastStage: 'playlist',
                    lastStageTimestamp: eventTimestamp,
                    stageHistory: [{
                      stage: 'playlist',
                      timestamp: eventTimestamp,
                      progress: 100,
                    }],
                  },
                }
                batchedPatchEvent(episodeId, updates)
                logger.debug('[useWebSocket] Updated playlist for episode', episodeId, 'path:', playlistPath)
                
                // Update last known stage for GridProgress indicator
                const { setLastKnownStage } = useScheduleStore.getState()
                setLastKnownStage(episodeId, 'playlist')
              }
              
              addLog({
                timestamp: message.ts || data.timestamp || new Date().toISOString(),
                stage: 'playlist',
                message: `Playlist generated: A=${data.side_a_count || 0}, B=${data.side_b_count || 0}`,
                level: 'info',
              })
            }
          }
          
          // SELECTOR generated event
          if (baseType === 'selector_generated') {
            const episodeId = data.episode_id || data.episodeId
            if (episodeId) {
              const updates: any = {
                assets: {},
              }
              
              // Update audio if provided
              if (data.full_mix_path) {
                updates.assets.audio = data.full_mix_path
                updates.audio_exists = true
              }
              
              // Update cover if provided
              if (data.cover_path) {
                updates.assets.cover = data.cover_path
                updates.cover_exists = true
              }
              
              // Update playlist path if provided
              if (data.playlist_path) {
                updates.playlistPath = data.playlist_path
              }
              
              if (Object.keys(updates.assets).length > 0 || updates.playlistPath) {
                batchedPatchEvent(episodeId, updates, { immediate: true })
                logger.info('[useWebSocket] SELECTOR generated assets for episode', episodeId, 'updates:', updates)
              }
              
              addLog({
                timestamp: message.ts || data.timestamp || new Date().toISOString(),
                stage: 'selector',
                message: `SELECTOR workflow completed: playlist=${!!data.playlist_path}, cover=${!!data.cover_path}, full_mix=${!!data.full_mix_path}`,
                level: 'info',
              })
            }
          }
          
          // FILLER generated event
          if (baseType === 'filler_generated') {
            const episodeId = data.episode_id || data.episodeId
            if (episodeId) {
              setEpisodeId(episodeId)
              setCurrentStage('idle' as any)
              setProgress(100)
              
              // Update scheduleStore runbook snapshot (unified state management)
              setRunbookSnapshot(episodeId, {
                currentStage: 'idle',
                episodeId,
                failedStage: null,
                errorMessage: null,
              })
              
              const updates: any = {
                assets: {},
              }
              
              // Update title if provided
              if (data.title) {
                updates.title = data.title
                // Also check if youtube_title_path should be set
                // (youtube_title_path is typically set when title file is saved)
              }
              
              // Update description if provided
              if (data.description_path) {
                updates.assets.description = data.description_path
                updates.description_exists = true
              }
              
              // Update captions if provided
              if (data.captions_path) {
                updates.assets.captions = data.captions_path
                updates.captions_exists = true
              }
              
              // Update tags if provided
              if (data.tags_path) {
                updates.assets.tags = data.tags_path
              }
              
              // Check if title file path should be inferred (youtube_title_path)
              // If title is provided, assume youtube_title file exists
              if (data.title) {
                // Title file path is typically: {episode_id}_youtube_title.txt
                // We can't infer the exact path here, but we can set youtube_title_exists if title is provided
                // The backend should send youtube_title_path if available
                updates.youtube_title_exists = true
              }
              
              if (Object.keys(updates.assets).length > 0 || updates.title || updates.description_exists || updates.captions_exists || updates.youtube_title_exists) {
                batchedPatchEvent(episodeId, updates, { immediate: true })
                logger.info('[useWebSocket] FILLER generated, updated episode:', episodeId, 'updates:', updates)
              }
              
              addLog({
                timestamp: message.ts || data.timestamp || new Date().toISOString(),
                stage: 'filler',
                message: `FILLER workflow completed: title=${!!data.title}, description=${!!data.description_path}, captions=${!!data.captions_path}, tags=${!!data.tags_path}`,
                level: 'info',
              })
              
              // Clear runbook state after a short delay
              setTimeout(() => {
                const { episodeId: currentEpisodeId } = useRunbookStore.getState()
                if (currentEpisodeId === episodeId) {
                  setCurrentStage('idle')
                  setProgress(0)
                  setEpisodeId(null)
                  // Clear scheduleStore snapshot
                  useScheduleStore.getState().clearRunbookSnapshot(episodeId)
                }
              }, 1000)
            }
          }
          
          // Error events
          if (baseType === 'runbook_error') {
            const episodeId = data.episode_id || data.episodeId
            const failedStage = data.stage || data.retry_point || null
            const errorMessage = data.message || data.error || 'Unknown error'
            
            if (episodeId) {
              clearFallbackTimer(episodeId)
              const issues = [errorMessage]
              batchedPatchEvent(episodeId, { issues }, { immediate: true }) // Errors are critical
              
              // Update runbook store with failure info (backward compatibility)
              const { episodeId: currentEpisodeId } = useRunbookStore.getState()
              if (episodeId === currentEpisodeId) {
                setFailedStage(failedStage, errorMessage)
                setCurrentStage('failed')
                setIsRunning(false)
              }
              
              // Update scheduleStore runbook snapshot (unified state management)
              setRunbookSnapshot(episodeId, {
                currentStage: 'failed',
                episodeId,
                failedStage: failedStage || null,
                errorMessage: errorMessage || null,
              })
            }
            
            addLog({
              timestamp: message.ts || data.timestamp || new Date().toISOString(),
              stage: (failedStage as any) || 'failed',
              message: errorMessage,
              level: 'error',
            })
          }
          
          // Batch generation events
          if (baseType === 'batch_generate_started') {
            logger.info('[useWebSocket] Received batch_generate_started:', data)
            const { setBatchGenerationStatus } = useScheduleStore.getState()
            setBatchGenerationStatus({
              runId: data.run_id || 'unknown',
              channelId: data.channel_id || 'unknown',
              totalEpisodes: data.episode_ids?.length || 0,
              completedEpisodes: 0,
              failedEpisodes: 0,
              currentEpisode: null,
              currentStage: null,
              progress: 0,
              status: 'running',
              startedAt: message.ts || data.timestamp || new Date().toISOString(),
            })
            logger.debug('[useWebSocket] Batch generation status set')
          }
          
          if (baseType === 'batch_generate_completed') {
            logger.info('[useWebSocket] Received batch_generate_completed:', data)
            const { updateBatchGenerationProgress, batchGenerationStatus } = useScheduleStore.getState()
            if (batchGenerationStatus && batchGenerationStatus.runId === data.run_id) {
              updateBatchGenerationProgress({
                completedEpisodes: data.success_count || batchGenerationStatus.totalEpisodes,
                progress: 100,
                status: 'completed',
                completedAt: message.ts || data.timestamp || new Date().toISOString(),
              })
              
              // Save to localStorage for Mission Control history
              try {
                const history = JSON.parse(localStorage.getItem('batch_generation_history') || '[]')
                history.unshift({
                  runId: batchGenerationStatus.runId,
                  channelId: batchGenerationStatus.channelId,
                  days: 7,
                  totalEpisodes: batchGenerationStatus.totalEpisodes,
                  completedEpisodes: data.success_count || batchGenerationStatus.totalEpisodes,
                  failedEpisodes: batchGenerationStatus.failedEpisodes,
                  status: 'completed',
                  startedAt: batchGenerationStatus.startedAt,
                  completedAt: message.ts || data.timestamp || new Date().toISOString(),
                })
                localStorage.setItem('batch_generation_history', JSON.stringify(history.slice(0, 50)))
                logger.debug('[useWebSocket] Batch history saved to localStorage')
              } catch (e) {
                logger.warn('Failed to save batch history:', e)
                if (process.env.NEXT_PUBLIC_SENTRY_DSN) {
                  import('@sentry/nextjs').then((Sentry) => {
                    Sentry.captureException(e, {
                      tags: {
                        component: 'useWebSocket',
                        action: 'save_batch_history',
                      },
                    })
                  })
                }
              }
              
              // Refresh schedule data after batch completion
              setTimeout(() => {
                window.location.reload()
              }, 2000)
            }
          }
          
          if (baseType === 'batch_generate_failed') {
            const { updateBatchGenerationProgress, batchGenerationStatus } = useScheduleStore.getState()
            if (batchGenerationStatus && batchGenerationStatus.runId === data.run_id) {
              updateBatchGenerationProgress({
                status: 'failed',
                error: data.error || 'Batch generation failed',
                completedAt: message.ts || data.timestamp || new Date().toISOString(),
              })
            }
          }
          
          return // Early return for direct t2r_* messages
        }
        
        // Handle event-type messages (legacy format)
        if (message.type === 'event' && message.data) {
          const eventType = message.data.type || message.data.get?.('type')
          const data = message.data.data || message.data
          
          // T2R scan progress
          if (eventType === 't2r_scan_progress') {
            if (data.locked_count !== undefined) {
              useT2RScheduleStore.getState().setLockedCount(data.locked_count)
            }
            if (data.conflicts) {
              useT2RScheduleStore.getState().setConflicts(data.conflicts)
            }
            
            if (data.episode_id && data.locked) {
              const currentEvent = useScheduleStore.getState().eventsById[data.episode_id]
              if (currentEvent) {
                batchedPatchEvent(data.episode_id, {
                  assets: {
                    ...currentEvent.assets,
                    verified_at: new Date().toISOString(),
                    verified: true,
                  } as any,
                }, { immediate: true }) // Verified status is critical
              }
            }
          }
          
          // T2R fix applied
          if (eventType === 't2r_fix_applied') {
            if (data.srt_fix) {
              setFixResult(data.srt_fix)
            }
          }
          
          // Runbook stage update (legacy format with Zod validation)
          if (eventType === 'runbook_stage_update' || eventType === 't2r_runbook_stage_update') {
            const validationResult = RunbookStageUpdateSchema.safeParse(data)
            if (!validationResult.success) {
              const error = new Error(`Invalid runbook stage update format: ${validationResult.error.message}`)
              Sentry.captureException(error, {
                tags: {
                  component: 'useWebSocket',
                  action: 'runbook_stage_update',
                },
                contexts: {
                  websocket: {
                    message_type: eventType,
                    raw_data: data,
                    validation_errors: validationResult.error.issues,
                  },
                },
              })
              if (process.env.NODE_ENV === 'development') {
                console.warn('[useWebSocket] Invalid runbook stage update:', validationResult.error.issues)
              }
            }
            
            const validatedData = validationResult.success ? validationResult.data : (data as any)
            const episodeId = validatedData.episode_id
            if (episodeId) {
              clearFallbackTimer(episodeId)
              setEpisodeId(episodeId)
              
              const stage = (validatedData.stage || '').toLowerCase()
              const currentEvent = useScheduleStore.getState().eventsById[episodeId]
              const updates: any = {
                kpis: {
                  ...(currentEvent?.kpis || {}),
                  lastRunAt: validatedData.timestamp || new Date().toISOString(),
                },
              }
              
              const mergeAssets = (source?: Record<string, any>) => {
                if (!source) return
                if (!updates.assets) updates.assets = {}
                const title = source.title || source.youtube_title
                const description = source.description || source.description_path
                const captions = source.captions || source.captions_path
                const video = source.video || source.video_path
                const audio = source.audio || source.audio_path
                const timeline = source.timeline_csv || source.timeline_csv_path
                const hashtag = source.hashtag || source.hashtag_path
                
                if (title) updates.title = title
                if (description) updates.assets.description = description
                if (captions) updates.assets.captions = captions
                if (video) {
                  updates.assets.video = video
                  updates.assets.video_path = video
                }
                if (audio) updates.assets.audio = audio
                if (timeline) updates.assets.timeline_csv = timeline
                if (hashtag) updates.assets.hashtag = hashtag
                if (source.cover) updates.assets.cover = source.cover
                if (source.playlist) updates.playlistPath = source.playlist
              }

              const artifacts = validatedData.artifacts || (validatedData as any).assets
              mergeAssets(artifacts as Record<string, any> | undefined)
              mergeAssets((data.assets || null) as Record<string, any> | undefined)
              
              // Also check top-level asset fields (for backward compatibility)
              if (data.title) updates.title = data.title
              if (data.description_path) {
                if (!updates.assets) updates.assets = {}
                updates.assets.description = data.description_path
              }
              if (data.captions_path) {
                if (!updates.assets) updates.assets = {}
                updates.assets.captions = data.captions_path
              }
              if (data.video_path) {
                if (!updates.assets) updates.assets = {}
                updates.assets.video = data.video_path
                updates.assets.video_path = data.video_path
              }
              if (data.audio_path) {
                if (!updates.assets) updates.assets = {}
                updates.assets.audio = data.audio_path
              }
              if (data.timeline_csv_path) {
                if (!updates.assets) updates.assets = {}
                updates.assets.timeline_csv = data.timeline_csv_path
              }
              
              batchedPatchEvent(episodeId, updates, { stage: validatedData.stage || data.stage })
              
              // Clear failed state if stage is progressing successfully
              const stageName = validatedData.stage || data.stage
              if (stageName && stageName !== 'failed' && stageName !== 'completed') {
                setFailedStage(null, null)
              }
              setCurrentStage(stageName as any)
              setProgress(validatedData.progress ?? data.progress ?? 0)
              addLog({
                timestamp: data.timestamp || new Date().toISOString(),
                stage: stageName || 'idle',
                message: validatedData.message || data.message || '',
                level: data.level || 'info',
              })
              
              // Update scheduleStore runbook snapshot (unified state management)
              setRunbookSnapshot(episodeId, {
                currentStage: stageName || 'idle',
                episodeId,
                failedStage: null,
                errorMessage: null,
              })
            }
          }
          
          // Upload progress
          if (eventType === 'upload_progress' || eventType === 't2r_upload_progress') {
            const episodeId = data.episode_id || data.episodeId
            if (episodeId) {
              const currentEvent = useScheduleStore.getState().eventsById[episodeId]
              if (currentEvent && data.progress === 100) {
                batchedPatchEvent(episodeId, {
                  assets: {
                    ...currentEvent.assets,
                    uploaded_at: new Date().toISOString(),
                    uploaded: true,
                  } as any,
                }, { immediate: true }) // Upload completion is critical
                
                // ✅ Invalidate work cursor query when upload completes
                // This ensures the work cursor updates immediately after upload
                queryClient.invalidateQueries({ queryKey: ['t2r-work-cursor'] })
              }
              
              setProgress(data.progress || 0)
              addLog({
                timestamp: data.timestamp || new Date().toISOString(),
                stage: 'upload',
                message: `Upload progress: ${data.progress}%`,
                level: 'info',
              })
            }
          }
          
          // Verify result
          if (eventType === 'verify_result' || eventType === 't2r_verify_result') {
            const validationResult = VerifyResultSchema.safeParse(data)
            if (!validationResult.success) {
              const error = new Error(`Invalid verify result format: ${validationResult.error.message}`)
              Sentry.captureException(error, {
                tags: {
                  component: 'useWebSocket',
                  action: 'verify_result',
                },
                contexts: {
                  websocket: {
                    message_type: eventType,
                    raw_data: data,
                    validation_errors: validationResult.error.issues,
                  },
                },
              })
              if (process.env.NODE_ENV === 'development') {
                console.warn('[useWebSocket] Invalid verify result:', validationResult.error.issues)
              }
            }
            
            const validatedData = validationResult.success ? validationResult.data : data
            const episodeId = validatedData.episode_id
            if (episodeId) {
              const currentEvent = useScheduleStore.getState().eventsById[episodeId]
              if (validatedData.all_passed) {
                batchedPatchEvent(episodeId, {
                  issues: [],
                  assets: {
                    ...(currentEvent?.assets || {}),
                    verified_at: new Date().toISOString(),
                    verified: true,
                  } as any,
                }, { immediate: true }) // Verification result is critical
                
                // ✅ Invalidate work cursor query when verification passes
                // This ensures the work cursor updates after successful verification
                queryClient.invalidateQueries({ queryKey: ['t2r-work-cursor'] })
              } else {
                if (data.checks) {
                  const issues = data.checks
                    .filter((check: any) => check.status === 'failed')
                    .map((check: any) => check.message)
                  batchedPatchEvent(episodeId, { issues }, { immediate: true }) // Verification failures are critical
                } else {
                  batchedPatchEvent(episodeId, { issues: ['验证失败'] }, { immediate: true }) // Verification failures are critical
                }
              }
            }
            
            addLog({
              timestamp: data.timestamp || new Date().toISOString(),
              stage: 'verify',
              message: data.message || (data.all_passed ? 'Verification completed' : 'Verification failed'),
              level: data.all_passed ? 'info' : 'warning',
            })
          }
          
          // Error events
          if (eventType === 'error' || eventType === 't2r_runbook_error' || eventType === 'runbook_error') {
            const episodeId = data.episode_id || data.episodeId
            const failedStage = data.stage || data.retry_point || null
            const errorMessage = data.message || data.error || 'Unknown error'
            
            if (episodeId) {
              clearFallbackTimer(episodeId)
              const issues = [errorMessage]
              batchedPatchEvent(episodeId, { issues }, { immediate: true }) // Errors are critical
              
              const { episodeId: currentEpisodeId } = useRunbookStore.getState()
              if (episodeId === currentEpisodeId) {
                setFailedStage(failedStage, errorMessage)
                setCurrentStage('failed')
                setIsRunning(false)
                addLog({
                  timestamp: data.timestamp || new Date().toISOString(),
                  stage: (failedStage as any) || 'failed',
                  message: errorMessage,
                  level: 'error',
                })
              }
              
              // Update scheduleStore runbook snapshot (unified state management)
              setRunbookSnapshot(episodeId, {
                currentStage: 'failed',
                episodeId,
                failedStage: failedStage || null,
                errorMessage: errorMessage || null,
              })
            }
            
            addLog({
              timestamp: data.timestamp || new Date().toISOString(),
              stage: 'failed',
              message: data.message || data.error || 'Unknown error',
              level: 'error',
            })
          }
        }
        
        // Handle status_update messages (legacy, ignored)
        if (message.type === 'status_update' && message.data) {
          return
        }
      },
      onError: (error) => {
        // Report WebSocket connection errors to Sentry
        if (process.env.NEXT_PUBLIC_SENTRY_DSN) {
          Sentry.captureException(error, {
            tags: {
              component: 'useWebSocket',
              action: 'websocket_connection',
            },
            contexts: {
              websocket: {
                url: `${WS_URL}/ws/status`,
                state: clientRef.current?.readyState,
              },
            },
          })
        }
        
        const wsUrl = `${WS_URL}/ws/status`
        logger.warn('Unified WebSocket error (may be normal if backend is not running):', {
          url: wsUrl,
          error: error instanceof Error ? error.message : 'Connection failed',
        })
      },
      onOpen: () => {
        logger.info('✅ Unified WebSocket connected')
      },
      onClose: () => {
        logger.info('👋 Unified WebSocket disconnected')
      },
    })
    
    clientRef.current.connect()
    
    return () => {
      // Clear all fallback timers on cleanup
      fallbackTimersRef.current.forEach((timer) => clearTimeout(timer))
      fallbackTimersRef.current.clear()
      
      shortFallbackTimersRef.current.forEach((timer) => clearTimeout(timer))
      shortFallbackTimersRef.current.clear()
      
      episodeStageRef.current.clear()
      
      // Clear batch processing
      if (batchRafRef.current !== null) {
        window.cancelAnimationFrame(batchRafRef.current)
        batchRafRef.current = null
      }
      if (batchTimeoutRef.current !== null) {
        window.clearTimeout(batchTimeoutRef.current)
        batchTimeoutRef.current = null
      }
      // Apply any pending updates before cleanup
      if (pendingUpdatesRef.current.size > 0) {
        applyBatchUpdates()
      }
      pendingUpdatesRef.current.clear()
      
      clientRef.current?.disconnect()
    }
  }, [
    patchEvent,
    updateEpisode,
    addConflict,
    setFixResult,
    addLog,
    setEpisodeId,
    setCurrentStage,
    setProgress,
    setFailedStage,
    setIsRunning,
  ])
  
  return {
    client: clientRef.current,
  }
}
