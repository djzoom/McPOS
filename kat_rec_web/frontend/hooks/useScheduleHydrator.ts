/**
 * Schedule Hydrator Hook
 * 
 * Loads schedule data from APIs and hydrates the ScheduleStore.
 * Handles data transformation from backend format to unified ScheduleEvent format.
 */
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useScheduleStore, type ScheduleEvent } from '@/stores/scheduleStore'
import { fetchT2REpisodes, fetchT2RChannel, type T2REpisode, type T2RChannel, getWorkCursor } from '@/services/t2rApi'
import { fetchChannels, type Channel } from '@/services/api'

/**
 * Infer caption file path from output file
 */
function inferCaptionPath(outputFile: string | undefined): string | null {
  if (!outputFile) return null
  
  // Extract base path and episode_id
  const pathParts = outputFile.split('/')
  const filename = pathParts[pathParts.length - 1]
  const episodeIdMatch = filename.match(/^(\d{8})/)
  
  if (!episodeIdMatch) return null
  
  const episodeId = episodeIdMatch[1]
  const baseDir = pathParts.slice(0, -1).join('/')
  
  // Common SRT file patterns
  const possiblePaths = [
    `${baseDir}/${episodeId}.srt`,
    `${baseDir}/${episodeId}_youtube.srt`,
    `${baseDir}/${episodeId}_youtube_youtube_upload.srt`,
    outputFile.replace(/\.mp4$/, '.srt').replace(/\.json$/, '.srt'),
  ]
  
  // Note: We can't actually check file existence client-side,
  // so we infer likely paths. Backend can verify via API if needed.
  return possiblePaths[0] // Return most likely path
}

/**
 * Infer playlist file path from episode_id and channel_id or other paths
 */
function inferPlaylistPath(
  episodeId: string | undefined,
  channelId: string | undefined,
  audioPath?: string | null,
  timelineCsvPath?: string | null
): string | null {
  if (!episodeId) return null
  
  // If we have audio_path or timeline_csv_path, use their directory
  if (audioPath) {
    const pathParts = audioPath.split('/')
    const baseDir = pathParts.slice(0, -1).join('/')
    return `${baseDir}/playlist.csv`
  }
  
  if (timelineCsvPath) {
    const pathParts = timelineCsvPath.split('/')
    const baseDir = pathParts.slice(0, -1).join('/')
    return `${baseDir}/playlist.csv`
  }
  
  // Fallback: infer from episode_id and channel_id
  // Output path convention: channels/<channelId>/output/<episodeId>/
  if (channelId) {
    return `channels/${channelId}/output/${episodeId}/playlist.csv`
  }
  
  return null
}

/**
 * Transform backend episode to ScheduleEvent
 */
const CHANNEL_ALIASES: Record<string, string> = {
  'kat records': 'kat_lofi',
  'kat-records': 'kat_lofi',
  'kat_rec': 'kat_lofi',
  'kat-rec': 'kat_lofi',
  'kat_lofi': 'kat_lofi',
  kat_lofi: 'kat_lofi',
}

function normalizeChannelId(channelId?: string | null): string {
  if (!channelId) return 'kat_lofi'
  const trimmed = channelId.trim()
  const key = trimmed.toLowerCase()
  return CHANNEL_ALIASES[key] || trimmed
}

function transformEpisode(episode: T2REpisode, channelId: string): ScheduleEvent {
  // Extract duration from output file or default to 0
  // TODO: Could fetch from video metadata if API provides it
  const durationSec = 0
  
  // Check asset completeness
  // IMPORTANT: Distinguish between image_path (original source image) and cover_path (generated cover)
  // - image_path: Original source image from library (shown in drawer)
  // - cover_path: Generated cover image (_cover.png) (shown in card and drawer)
  const hasCover = !!episode.cover_path  // Use cover_path for completeness check
  const hasAudio = !!episode.output_file
  // Description path should come from backend (episode.description_path or episode.assets?.description)
  // Priority: description_path (top-level field) > assets.description (nested field)
  const descriptionPath = (episode as any).description_path || (episode as any).assets?.description || null
  const hasDescription = !!descriptionPath
  // Captions path should come from backend (episode.captions_path or episode.assets?.captions)
  // If not provided, try to infer from output file
  const captionPath = (episode as any).captions_path || (episode as any).assets?.captions || inferCaptionPath(episode.output_file)
  const hasCaptions = !!captionPath
  
  // Determine asset completeness
  const assetCount = [hasCover, hasAudio, hasDescription, hasCaptions].filter(Boolean).length
  const completeness = assetCount === 4 ? 'complete' : assetCount === 0 ? 'missing' : 'partial'
  
  // Extract issues (from locked_reason or empty)
  const issues: string[] = []
  if (episode.lock_reason) {
    issues.push(episode.lock_reason)
  }
  
  // Title should only be set if backend explicitly provides it
  // Title generation logic: 排播 → 文件夹 → 挑歌 → 主题图 → 选色 → 标题
  // So we should NOT show placeholder titles like "Episode X"
  // Get audio_path from episode (full mix file)
  const audioPath = (episode as any).audio_path || episode.assets?.audio || null
  // Get timeline_csv_path from episode (indicator that remix is complete)
  const timelineCsvPath = (episode as any).timeline_csv_path || (episode.assets as any)?.timeline_csv || null
  // Get video_path from episode (rendered video file)
  // output_file is the video file path (rendered video), not audio
  const videoPath = (episode as any).video_path || episode.assets?.video || episode.output_file || null
  
  // Get render_complete_flag from episode assets (indicator that render is truly complete)
  const renderCompleteFlag = (episode.assets as any)?.render_complete_flag || null
  
  const event: ScheduleEvent & { hasOutputFolder?: boolean } = {
    id: episode.episode_id,
    channelId,
    date: episode.schedule_date,
    title: episode.title || null, // Only set if backend provides actual title, no placeholder
    durationSec,
    bpm: null,
    assets: {
      // Use cover_path for card display (generated cover), fallback to image_path if cover doesn't exist
      cover: episode.cover_path || null,  // Generated cover image - shown in card and drawer
      audio: audioPath || null,  // Full mix audio file - use audio_path from backend
      description: descriptionPath, // Only set if backend provides actual path, no placeholder
      captions: captionPath,
      // Include timeline_csv for remix completion check
      timeline_csv: timelineCsvPath || null,  // Timeline CSV path (indicator that remix is complete)
      // Video path (rendered video file) - output_file is the video file
      video: videoPath || null,
      video_path: videoPath || null,
      // ✅ 关键：包含 render_complete_flag，用于判断渲染是否真正完成
      render_complete_flag: renderCompleteFlag,
    } as any,  // Use 'as any' to allow timeline_csv field
    image_path: episode.image_path || null,  // Original source image from library - shown in drawer only
    // Playlist path: use backend value, or infer from audio/timeline_csv paths, or from episode_id/channel_id
    playlistPath: (episode as any).playlist_path || inferPlaylistPath(
      episode.episode_id,
      channelId,
      audioPath,
      timelineCsvPath
    ),
    issues,
    kpis: {
      lastRunAt: episode.locked_at,
    },
    hasOutputFolder: episode.has_output_folder || episode.hasOutputFolder || false,  // For grid coloring and state detection
    // Asset existence flags (from backend file system checks)
    audio_exists: (episode as any).audio_exists ?? (!!audioPath),
    description_exists: (episode as any).description_exists ?? (!!descriptionPath),
    captions_exists: (episode as any).captions_exists ?? (!!captionPath),
    cover_exists: (episode as any).cover_exists ?? (!!episode.cover_path),
    // YouTube title path (different from album title)
    youtube_title_path: (episode as any).youtube_title_path || (episode.assets as any)?.youtube_title || null,
    youtube_title_exists: (episode as any).youtube_title_exists ?? (!!((episode as any).youtube_title_path || (episode.assets as any)?.youtube_title)),
  }
  return event
}

/**
 * Transform backend channel to channel ID array
 */
function extractChannelIds(channels: (Channel | T2RChannel)[]): string[] {
  return channels.map((ch) => ch.id).filter(Boolean)
}

/**
 * Hook to hydrate schedule store from APIs
 */
export function useScheduleHydrator() {
  const hydrate = useScheduleStore((state) => state.hydrate)
  const setDateRange = useScheduleStore((state) => state.setDateRange)
  const setChannelState = useScheduleStore((state) => state.setChannelState)
  
  // Get selected channel from store (if available)
  const selectedChannel = useScheduleStore((state) => state.selectedChannel)
  
  // Normalize channel ID (kat-rec -> kat_lofi)
  const normalizedChannel = selectedChannel === 'kat-rec' ? 'kat_lofi' : selectedChannel
  
  // Fetch episodes from T2R API (with channel_id if available)
  // NO AUTO-ENSURE: Explicit initialization required via /api/t2r/schedule/initialize
  // 添加防护：确保在客户端且 QueryClient 可用时才使用 useQuery
  // 统一查询键格式：无 channelId 时使用 ['t2r-episodes']，有 channelId 时使用 ['t2r-episodes', channelId]
  // 这样 ['t2r-episodes'] 和 ['t2r-episodes', undefined] 会共享同一个缓存
  const episodesQueryKey = normalizedChannel 
    ? ['t2r-episodes', normalizedChannel] 
    : ['t2r-episodes']
  
  const {
    data: episodesData,
    isLoading: episodesLoading,
    error: episodesError,
  } = useQuery({
    queryKey: episodesQueryKey,
    queryFn: async () => {
      try {
        return await fetchT2REpisodes(normalizedChannel || undefined) // NO auto_ensure
      } catch (error: any) {
        // Handle network errors gracefully
        if (error?.isNetworkError || (error?.message && error.message.includes('无法连接到后端服务'))) {
          console.debug('[useScheduleHydrator] Backend not available, returning empty episodes')
          return { episodes: [], total: 0, schedule_empty: true, needs_initialization: false }
        }
        throw error
      }
    },
    staleTime: 30 * 1000, // 30 seconds - balance between freshness and performance
    refetchInterval: (query) => {
      // Only refetch if query is stale and window is focused
      if (typeof window !== 'undefined' && document.hasFocus()) {
        return 30 * 1000 // 30 seconds when focused
      }
      return false // Don't refetch when tab is not focused
    },
    retry: (failureCount, error: any) => {
      // Don't retry on network errors (backend not running)
      if (error?.isNetworkError || (error?.message && error.message.includes('无法连接到后端服务'))) {
        return false
      }
      // Retry up to 2 times for other errors
      return failureCount < 2
    },
  })
  
  // Fetch channel info (primary channel, with channel_id if available)
  // Note: This is optional - if it fails, we'll use fallback channels
  const {
    data: primaryChannel,
    isLoading: channelLoading,
    error: channelError,
  } = useQuery({
    queryKey: ['t2r-channel', selectedChannel],
    queryFn: () => fetchT2RChannel(selectedChannel || undefined),
    staleTime: 30 * 1000,
    retry: false, // Don't retry on failure - it's optional
    onError: (error) => {
      // Log but don't treat as fatal - we have fallback channels
      console.warn('[ScheduleHydrator] Channel fetch failed (non-fatal):', error)
    },
  })
  
  // Fetch all channels (fallback)
  const {
    data: allChannels,
    isLoading: channelsLoading,
  } = useQuery({
    queryKey: ['channels'],
    queryFn: fetchChannels,
    staleTime: 60 * 1000,
    enabled: !primaryChannel, // Only fetch if primary channel not available
  })
  
  // Fetch work cursor date for each channel
  const {
    data: workCursorData,
    isLoading: workCursorLoading,
  } = useQuery({
    queryKey: ['t2r-work-cursor', normalizedChannel],
    queryFn: () => getWorkCursor(normalizedChannel || undefined),
    staleTime: 10 * 1000, // 10 seconds - refresh more frequently to catch cursor updates
    retry: 2, // Retry up to 2 times in case backend hasn't loaded the route yet
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 5000), // Exponential backoff
    refetchInterval: 30000, // Refetch every 30 seconds to catch work cursor updates
    onError: (error) => {
      // Only log as warning, don't throw - this is optional functionality
      console.warn('[ScheduleHydrator] Work cursor fetch failed (non-fatal):', error)
    },
  })
  
  // Update work cursor date in store
  const setWorkCursorDate = useScheduleStore((state) => state.setWorkCursorDate)
  useEffect(() => {
    if (workCursorData && workCursorData.work_cursor_date) {
      const channelId = workCursorData.channel_id || normalizedChannel || 'kat_lofi'
      setWorkCursorDate(channelId, workCursorData.work_cursor_date)
    }
  }, [workCursorData, normalizedChannel, setWorkCursorDate])
  
  // Hydrate store when data is available
  useEffect(() => {
    // Always hydrate, even if episodes array is empty (to clear store after RESET)
    if (episodesData !== undefined) {
      // Extract channel IDs from episodes data
      // Each episode may have its own channel_id, so we need to group by channel
      const channels: string[] = []
      const eventsByChannel: Record<string, ScheduleEvent[]> = {}
      
      // First, collect all unique channel IDs from episodes
      const episodeChannels = new Set<string>()
      if (episodesData.episodes && episodesData.episodes.length > 0) {
        episodesData.episodes.forEach((ep: any) => {
          // Try to get channel_id from episode data
          const epChannelId = normalizeChannelId(ep.channel_id || primaryChannel?.id || allChannels?.[0]?.id || selectedChannel || 'kat_lofi')
          episodeChannels.add(epChannelId)
        })
      }
      
      // Also add channels from API responses
      if (primaryChannel) {
        episodeChannels.add(primaryChannel.id)
      }
      if (allChannels && allChannels.length > 0) {
        allChannels.forEach((ch: any) => {
          episodeChannels.add(ch.id)
        })
      }
      
      // If no channels found, use default channel ID
      const uniqueChannels = episodeChannels.size > 0 
        ? Array.from(episodeChannels)
        : [normalizeChannelId(primaryChannel?.id || allChannels?.[0]?.id || selectedChannel || 'kat_lofi')]
      
      // Transform episodes to ScheduleEvents, grouping by channel
      const events: ScheduleEvent[] = []
      if (episodesData.episodes && episodesData.episodes.length > 0) {
        episodesData.episodes.forEach((ep: any) => {
          // Determine channel ID for this episode
          const epChannelId = normalizeChannelId(ep.channel_id || primaryChannel?.id || allChannels?.[0]?.id || selectedChannel || 'kat_lofi')
          const event = transformEpisode(ep, epChannelId)
          events.push(event)
          
          // Group by channel for debugging
          if (!eventsByChannel[epChannelId]) {
            eventsByChannel[epChannelId] = []
          }
          eventsByChannel[epChannelId].push(event)
        })
      }
      
      // Hydrate store (pass empty array to clear if RESET)
      hydrate({
        channels: uniqueChannels,
        events, // Can be empty array to clear events
      })
      
      // Debug logging
      console.log('[useScheduleHydrator] Transformed episodes:', {
        inputEpisodesCount: episodesData.episodes?.length || 0,
        outputEventsCount: events.length,
        uniqueChannels,
        eventsByChannel: Object.fromEntries(
          Object.entries(eventsByChannel).map(([ch, evs]) => [ch, evs.length])
        ),
      })
      
      // Calculate and set channel state based on API response and episode data
      // IMPORTANT: Only update state when we have definitive information from API
      // Don't reset to 'void' if current state is 'in_production' and events are temporarily empty
      // (this can happen during episode generation when API hasn't caught up yet)
      if (episodesData) {
        const scheduleEmpty = episodesData.schedule_empty === true
        const needsInitialization = episodesData.needs_initialization === true
        
        // Determine state for each channel
        uniqueChannels.forEach((chId) => {
          const channelEvents = events.filter(e => e.channelId === chId)
          const currentState = useScheduleStore.getState().channelState[chId]
          
          // Only set to 'void' if API explicitly says schedule is empty
          // Don't reset to 'void' if we're already 'in_production' and events are temporarily empty
          // (this prevents flickering during episode generation)
          if (scheduleEmpty || needsInitialization) {
            // API explicitly says schedule is empty - set to void
            setChannelState(chId, 'void')
          } else if (channelEvents.length > 0) {
            // Has episodes - set to in_production
            setChannelState(chId, 'in_production')
          } else if (currentState === 'void') {
            // Current state is void and no events - keep void
            // (don't change state if already void)
          } else if (currentState === 'in_production' && channelEvents.length === 0) {
            // Current state is in_production but no events in this refresh
            // Don't reset to void - might be temporary (episode still generating)
            // Only reset if API explicitly says schedule is empty (handled above)
            // This prevents flickering when episode is being created but not yet in API response
          }
          // If currentState is undefined, leave it (will be set when episodes appear)
        })
      }
      
      // Log for debugging
      console.log('[ScheduleHydrator] Hydrated store:', {
        channelCount: uniqueChannels.length,
        eventCount: events.length,
        channels: uniqueChannels,
        isEmpty: events.length === 0,
        scheduleEmpty: episodesData?.schedule_empty,
        needsInitialization: episodesData?.needs_initialization,
      })
    }
  }, [episodesData, primaryChannel, allChannels, selectedChannel, hydrate, setChannelState])
  
  // Initialize date range on mount - preserve existing range if set
  // Only set default if dateRange is uninitialized or matches the default 64-day range
  useEffect(() => {
    const state = useScheduleStore.getState()
    const currentDateRange = state.dateRange
    
    // Calculate what the default 64-day range would be
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const defaultFrom = today.toISOString().split('T')[0]
    const defaultTo = new Date(today)
    defaultTo.setDate(defaultTo.getDate() + 64)
    const defaultToStr = defaultTo.toISOString().split('T')[0]
    
    // Only set date range if it's uninitialized or matches the default 64-day range
    // This preserves user's date range selection across page refreshes
    if (!currentDateRange || 
        (currentDateRange.from === defaultFrom && currentDateRange.to === defaultToStr)) {
      // Set date range from today (14 days forward)
      setDateRange({ days: 14 })
    }
  }, [setDateRange])
  
  // Only treat episodes error as fatal - channel errors are non-fatal (we have fallbacks)
  // Only consider episodes loading as the main loading state - channel loading is optional
  return {
    isLoading: episodesLoading, // Only wait for episodes, not channels (channels are optional)
    error: episodesError, // Only report episodes error - channel error is non-fatal
    episodeCount: episodesData?.episodes?.length || 0,
  }
}
