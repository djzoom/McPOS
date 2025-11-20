/**
 * Zod Schemas for Runtime Type Validation
 * 
 * This file contains Zod schemas for all major data types used in the application.
 * These schemas provide runtime type safety and can be used to validate API responses,
 * WebSocket messages, and form inputs.
 */

import { z } from 'zod'

/**
 * ScheduleEvent Schema
 * 
 * Unified event model for Schedule Board
 */
export const ScheduleEventSchema = z.object({
  id: z.string(),
  channelId: z.string(),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Date must be in YYYY-MM-DD format'),
  title: z.string(),
  durationSec: z.number().nonnegative(),
  bpm: z.number().nullable(),
  assets: z.object({
    cover: z.string().nullable(),
    audio: z.string().nullable(),
    description: z.string().nullable(),
    captions: z.string().nullable(),
    // Extended fields for video and upload status
    timeline_csv: z.string().nullable().optional(),
    video: z.string().nullable().optional(),
    video_path: z.string().nullable().optional(),
    render_complete_flag: z.string().nullable().optional(),  // ✅ 新增：渲染完成旗标文件
    uploaded_at: z.string().nullable().optional(),
    uploaded: z.boolean().optional(),
    verified_at: z.string().nullable().optional(),
    verified: z.boolean().optional(),
  }),
  image_path: z.string().nullable().optional(),
  issues: z.array(z.string()),
  kpis: z.object({
    successRate: z.number().optional(),
    lastRunAt: z.string().optional(),
  }).optional(),
  hasOutputFolder: z.boolean().optional(),
  playlistPath: z.string().nullable().optional(),
})

/**
 * T2REpisode Schema
 * 
 * Backend episode format from T2R API
 * Matches the actual response from /api/t2r/episodes
 */
export const T2REpisodeSchema = z.object({
  episode_id: z.string(),
  episode_number: z.number().optional(),
  schedule_date: z.string().optional(), // Backend uses schedule_date, not date
  channel_id: z.string().optional(), // May be undefined in response
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Date must be in YYYY-MM-DD format').optional(), // May be undefined
  status: z.string().optional(), // May be undefined
  title: z.string().nullable().optional(),
  image_path: z.string().nullable().optional(),
  cover_path: z.string().nullable().optional(),
  output_file: z.string().nullable().optional(),
  playlist_path: z.string().nullable().optional(),
  assets: z.object({
    audio: z.string().nullable().optional(),
    cover: z.string().nullable().optional(),
    captions: z.string().nullable().optional(),
    description: z.string().nullable().optional(),
    timeline_csv: z.string().nullable().optional(),
    video: z.string().nullable().optional(),
    video_path: z.string().nullable().optional(),
    render_complete_flag: z.string().nullable().optional(),  // ✅ 新增：渲染完成旗标文件
  }).optional(),
  // Extended fields that may come from backend
  audio_path: z.string().nullable().optional(),
  description_path: z.string().nullable().optional(),
  captions_path: z.string().nullable().optional(),
  timeline_csv_path: z.string().nullable().optional(),
  video_path: z.string().nullable().optional(),
  uploaded_at: z.string().nullable().optional(),
  uploaded: z.boolean().optional(),
  verified_at: z.string().nullable().optional(),
  verified: z.boolean().optional(),
  lock_reason: z.string().nullable().optional(),
  locked_at: z.string().nullable().optional(),
  // Additional fields from backend
  file_exists: z.boolean().optional(),
  image_exists: z.boolean().optional(),
  cover_exists: z.boolean().optional(),
  playlist_exists: z.boolean().optional(),
  audio_exists: z.boolean().optional(),
  description_exists: z.boolean().optional(),
  captions_exists: z.boolean().optional(),
  has_output_folder: z.boolean().optional(),
}).passthrough() // Allow additional fields from backend

/**
 * ScheduleEpisode Schema
 * 
 * Episode format for T2R Schedule Store
 */
export const ScheduleEpisodeSchema = z.object({
  episode_id: z.string(),
  episode_number: z.number().int().nonnegative(),
  schedule_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Date must be in YYYY-MM-DD format'),
  image_path: z.string().optional(),
  status: z.string(),
  locked_at: z.string().optional(),
  lock_reason: z.string().optional(),
})

/**
 * ScheduleConflict Schema
 */
export const ScheduleConflictSchema = z.object({
  type: z.string(),
  asset: z.string(),
  episodes: z.array(z.string()),
  severity: z.enum(['info', 'warning', 'error']),
})

/**
 * T2REpisodesResponse Schema
 * 
 * Matches the actual response from /api/t2r/episodes
 * Backend returns: { episodes: [], total: 0, schedule_empty: bool, needs_initialization: bool, timestamp: str }
 */
export const T2REpisodesResponseSchema = z.object({
  episodes: z.array(T2REpisodeSchema).optional(),
  total: z.number().optional(),
  schedule_empty: z.boolean().optional(),
  needs_initialization: z.boolean().optional(),
  timestamp: z.string().optional(),
  error: z.string().optional(), // Error message if something went wrong
}).passthrough() // Allow additional fields from backend

/**
 * T2RChannel Schema
 */
export const T2RChannelSchema = z.object({
  channel_id: z.string(),
  channel_name: z.string().optional(),
  description: z.string().optional(),
  // Add other channel fields as needed
}).passthrough() // Allow additional fields

/**
 * WebSocket Event Envelope Schema
 */
export const EventEnvelopeSchema = z.object({
  type: z.string(),
  version: z.number().optional(),
  ts: z.string().optional(),
  level: z.enum(['info', 'warn', 'error']).optional(),
  data: z.any().optional(),
})

/**
 * Runbook Stage Update Schema
 */
const RunbookStageStatusEnum = z.enum(['pending', 'in_progress', 'done', 'error'])

export const RunbookStageUpdateSchema = z.object({
  episode_id: z.string(),
  channel_id: z.string().optional(),
  stage: z.string(),
  legacy_stage: z.string().optional(),
  lane: z.enum(['preparation', 'render', 'delivery']).optional(),
  status: RunbookStageStatusEnum,
  progress: z.number().min(0).max(100).optional(),
  message: z.string().optional(),
  artifacts: z.record(z.any()).optional(),
  assets: z.record(z.any()).optional(), // backward compat
  error: z.union([z.string(), z.record(z.any())]).optional(),
})

/**
 * Upload Progress Schema
 */
export const UploadProgressSchema = z.object({
  episode_id: z.string(),
  progress: z.number().min(0).max(100),
  message: z.string().optional(),
  video_id: z.string().optional(),
})

/**
 * Verify Result Schema
 */
export const VerifyResultSchema = z.object({
  episode_id: z.string(),
  verified: z.boolean(),
  video_id: z.string().optional(),
  message: z.string().optional(),
  errors: z.array(z.string()).optional(),
})

/**
 * TypeScript types inferred from schemas
 */
export type ScheduleEvent = z.infer<typeof ScheduleEventSchema>
export type T2REpisode = z.infer<typeof T2REpisodeSchema>
export type ScheduleEpisode = z.infer<typeof ScheduleEpisodeSchema>
export type ScheduleConflict = z.infer<typeof ScheduleConflictSchema>
export type T2REpisodesResponse = z.infer<typeof T2REpisodesResponseSchema>
export type T2RChannel = z.infer<typeof T2RChannelSchema>
export type EventEnvelope = z.infer<typeof EventEnvelopeSchema>
export type RunbookStageUpdate = z.infer<typeof RunbookStageUpdateSchema>
export type UploadProgress = z.infer<typeof UploadProgressSchema>
export type VerifyResult = z.infer<typeof VerifyResultSchema>
