/**
 * Schedule Hydrator Hook
 * 
 * Loads schedule data from APIs and hydrates the ScheduleStore.
 * Handles data transformation from backend format to unified ScheduleEvent format.
 */
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useScheduleStore, type ScheduleEvent } from '@/stores/scheduleStore'
import { fetchT2REpisodes, fetchT2RChannel, type T2REpisode, type T2RChannel } from '@/services/t2rApi'
import { fetchChannels, type Channel } from '@/services/api'
import { normalizeStatus } from '@/lib/designTokens'

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
 * Transform backend episode to ScheduleEvent
 */
function transformEpisode(episode: T2REpisode, channelId: string): ScheduleEvent {
  // Extract duration from output file or default to 0
  // TODO: Could fetch from video metadata if API provides it
  const durationSec = 0
  
  // Check asset completeness
  const hasCover = !!episode.image_path
  const hasAudio = !!episode.output_file
  // Description is usually in schedule_master.json or generated, so assume exists if episode has title
  const hasDescription = !!(episode.title || episode.lock_reason)
  // Infer caption path from output file
  const captionPath = inferCaptionPath(episode.output_file)
  const hasCaptions = !!captionPath
  
  // Determine asset completeness
  const assetCount = [hasCover, hasAudio, hasDescription, hasCaptions].filter(Boolean).length
  const completeness = assetCount === 4 ? 'complete' : assetCount === 0 ? 'missing' : 'partial'
  
  // Normalize status
  const status = normalizeStatus(episode.status)
  
  // Extract issues (from locked_reason or empty)
  const issues: string[] = []
  if (episode.lock_reason && status !== 'verified') {
    issues.push(episode.lock_reason)
  }
  
  return {
    id: episode.episode_id,
    channelId,
    date: episode.schedule_date,
    title: episode.title || `Episode ${episode.episode_number || episode.episode_id}`,
    durationSec,
    bpm: null,
    assets: {
      cover: episode.image_path || null,
      audio: episode.output_file || null,
      description: episode.title ? `Description for ${episode.title}` : null, // Placeholder
      captions: captionPath,
    },
    status,
    issues,
    kpis: {
      lastRunAt: episode.locked_at,
    },
  }
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
  
  // Fetch episodes from T2R API
  const {
    data: episodesData,
    isLoading: episodesLoading,
    error: episodesError,
  } = useQuery({
    queryKey: ['t2r-episodes'],
    queryFn: fetchT2REpisodes,
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 60 * 1000, // Refetch every minute
  })
  
  // Fetch channel info (primary channel)
  const {
    data: primaryChannel,
    isLoading: channelLoading,
    error: channelError,
  } = useQuery({
    queryKey: ['t2r-channel'],
    queryFn: fetchT2RChannel,
    staleTime: 30 * 1000,
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
  
  // Hydrate store when data is available
  useEffect(() => {
    if (episodesData?.episodes && (primaryChannel || allChannels)) {
      // Determine channel ID
      const channelId = primaryChannel?.id || allChannels?.[0]?.id || 'kat-rec'
      
      // Transform episodes to ScheduleEvents
      const events: ScheduleEvent[] = episodesData.episodes.map((ep) =>
        transformEpisode(ep, channelId)
      )
      
      // Extract channel IDs
      const channels: string[] = []
      if (primaryChannel) {
        channels.push(primaryChannel.id)
      }
      if (allChannels && allChannels.length > 0) {
        channels.push(...extractChannelIds(allChannels))
      }
      // Deduplicate
      const uniqueChannels = Array.from(new Set(channels))
      
      // Hydrate store
      hydrate({
        channels: uniqueChannels.length > 0 ? uniqueChannels : [channelId],
        events,
      })
    }
  }, [episodesData, primaryChannel, allChannels, hydrate])
  
  // Initialize date range on mount (if not already set)
  useEffect(() => {
    setDateRange({ days: 14 })
  }, [setDateRange])
  
  return {
    isLoading: episodesLoading || channelLoading || channelsLoading,
    error: episodesError || channelError,
    episodeCount: episodesData?.episodes?.length || 0,
  }
}
