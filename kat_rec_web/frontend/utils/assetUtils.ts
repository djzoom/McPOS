/**
 * Asset Utilities
 * 
 * Shared utility functions for checking asset existence and status.
 * Centralizes the logic for checking asset completion with strict validation.
 * 
 * IMPORTANT: These functions use strict completion checks to ensure assets are truly ready,
 * not just that files exist. This aligns with the completion detection logic in scheduleStore.
 */
import type { ScheduleEvent } from '@/stores/scheduleStore'

/**
 * Check if audio asset is fully completed (audio file + timeline CSV)
 * 
 * Uses the same strict logic as isAudioMixed in scheduleStore:
 * - Requires both audio file AND timeline_csv to exist
 * - timeline_csv is the last file generated in remix stage, so its presence indicates completion
 * - Audio path must contain '_full_mix.mp3'
 * - Timeline CSV must contain '_full_mix_timeline.csv'
 */
export function hasAudio(event: ScheduleEvent): boolean {
  const audioPath = event.assets.audio
  const timelineCsv = event.assets.timeline_csv
  
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
  
  // ❌ 不允许仅凭 audio 路径就认为完成
  // 这确保了系统必须等待 timeline_csv 生成才认为 remix 完成
  return false
}

/**
 * Check if audio asset has started (audio file exists but timeline CSV may not)
 * 
 * This is useful for showing "generating..." status in UI
 */
export function hasAudioStarted(event: ScheduleEvent): boolean {
  return event.audio_exists ?? !!event.assets.audio
}

/**
 * Check if cover asset exists
 * 
 * Currently checks cover_exists flag or cover path.
 * Cover generation is typically fast and atomic, so path existence is sufficient.
 */
export function hasCover(event: ScheduleEvent): boolean {
  return event.cover_exists ?? !!event.assets.cover
}

/**
 * Check if description asset exists
 * 
 * Currently checks description_exists flag or description path.
 * Description files are text files, so path existence is sufficient.
 */
export function hasDescription(event: ScheduleEvent): boolean {
  return event.description_exists ?? !!event.assets.description
}

/**
 * Check if captions asset exists
 * 
 * Currently checks captions_exists flag or captions path.
 * Caption files (SRT) are text files, so path existence is sufficient.
 */
export function hasCaptions(event: ScheduleEvent): boolean {
  return event.captions_exists ?? !!event.assets.captions
}

/**
 * Check if video render is fully completed (video file + render complete flag)
 * 
 * Uses strict logic aligned with calculateStageStatus:
 * - Requires both video file AND render_complete_flag to exist
 * - render_complete_flag is created after video rendering and validation
 * - This ensures the video file is fully written and validated, not just detected during write
 */
export function hasVideo(event: ScheduleEvent): boolean {
  // ✅ 严格要求：必须有 render_complete_flag 才认为完成
  // render_complete_flag 确保渲染真正完成（文件写入完成、验证通过）
  return !!(
    (event.assets.video || event.assets.video_path) &&
    event.assets.render_complete_flag
  )
}

/**
 * Check if video render has started (video file exists but flag may not)
 * 
 * This is useful for showing "rendering..." status in UI
 */
export function hasVideoStarted(event: ScheduleEvent): boolean {
  return !!(event.assets.video || event.assets.video_path)
}

/**
 * Check if YouTube title asset exists
 */
export function hasYouTubeTitle(event: ScheduleEvent): boolean {
  return event.youtube_title_exists ?? !!event.youtube_title_path ?? !!event.assets.youtube_title
}

/**
 * Check if timeline CSV exists
 */
export function hasTimelineCsv(event: ScheduleEvent): boolean {
  return !!event.assets.timeline_csv
}

/**
 * Check if playlist exists
 */
export function hasPlaylist(event: ScheduleEvent): boolean {
  return !!event.playlistPath
}

