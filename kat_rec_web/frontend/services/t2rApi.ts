/**
 * T2R API Service
 * 
 * Client-side API calls for T2R (Trip to Reality) endpoints.
 */
import { getApiBase } from '../lib/apiBase'

const API_URL = getApiBase()

async function apiRequest<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`)
  }

  return response.json()
}

// Scan and Lock
export interface ScanResponse {
  status: 'ok' | 'error'
  summary?: {
    locked_count: number
    conflicts_count?: number
    conflicts?: Array<{
      type: string
      asset: string
      episodes: string[]
    }>
    asset_usage?: {
      total_episodes?: number
      duplicate_images?: number
      images?: Record<string, string[]>
      songs?: Record<string, string[]>
      episodes?: Record<string, any>
    }
  }
  data?: {
    locked_count: number
    conflicts?: Array<{
      type: string
      asset: string
      episodes: string[]
    }>
  }
  errors?: string[]
}

export async function scanSchedule(): Promise<ScanResponse> {
  return apiRequest<ScanResponse>('/api/t2r/scan', { method: 'POST' })
}

// SRT Operations
export interface SRTInspectRequest {
  episode_id?: string
  file_path?: string
}

export interface SRTInspectResponse {
  status: 'ok' | 'error'
  issues?: Array<{
    type: string
    message: string
    start?: string
    end?: string
  }>
  errors?: string[]
}

export async function inspectSRT(request: SRTInspectRequest): Promise<SRTInspectResponse> {
  return apiRequest<SRTInspectResponse>('/api/t2r/srt/inspect', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export interface SRTFixRequest {
  episode_id: string
  strategy: 'clip' | 'shift' | 'merge'
  dry_run?: boolean
}

export interface SRTFixResponse {
  status: 'ok' | 'error'
  diff?: string
  fixed_path?: string
  errors?: string[]
}

export async function fixSRT(request: SRTFixRequest): Promise<SRTFixResponse> {
  return apiRequest<SRTFixResponse>('/api/t2r/srt/fix', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

// Description Linting
export interface DescLintRequest {
  episode_id: string
  description: string
  auto_fix?: boolean
}

export interface DescFlag {
  type: 'branding_misuse' | 'cc0_missing' | 'seo_weak'
  message: string
}

export interface DescSuggestion {
  type: string
  issue: string
  fix: string
}

export interface DescLintResponse {
  status: 'ok' | 'error'
  flags?: DescFlag[]
  suggestions?: DescSuggestion[]
  fixed_description?: string
  errors?: string[]
}

export async function lintDescription(request: DescLintRequest): Promise<DescLintResponse> {
  return apiRequest<DescLintResponse>('/api/t2r/desc/lint', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

// Plan and Run
export interface PlanRequest {
  episode_id: string
  start_date?: string
  avoid_duplicates?: boolean
  seo_template?: boolean
}

export interface PlanResponse {
  status: 'ok' | 'error'
  summary?: {
    episode_id: string
    recipe_saved: boolean
  }
  recipe?: any
  recipe_json_path?: string
  cli_command?: string
  errors?: string[]
}

export async function planEpisode(request: PlanRequest): Promise<PlanResponse> {
  return apiRequest<PlanResponse>('/api/t2r/plan', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export interface RunRequest {
  episode_id: string
  recipe_path?: string
  stages?: string[]
  dry_run?: boolean
}

export interface RunResponse {
  status: 'ok' | 'error'
  summary?: {
    run_id: string
    background?: boolean
    dry_run?: boolean
    stages?: string[]
  }
  run_id?: string
  current_stage?: string
  progress?: number
  message?: string
  errors?: string[]
}

export async function runEpisode(request: RunRequest): Promise<RunResponse> {
  return apiRequest<RunResponse>('/api/t2r/run', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

// Upload and Verification
export interface UploadStartRequest {
  episode_id: string
  video_file: string
  metadata: Record<string, any>
}

export async function startUpload(request: UploadStartRequest) {
  return apiRequest('/api/t2r/upload/start', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function getUploadStatus(uploadId: string) {
  return apiRequest(`/api/t2r/upload/status?upload_id=${uploadId}`)
}

export interface UploadVerifyRequest {
  episode_id: string
  video_id: string
  platform?: string
}

export interface UploadVerifyResponse {
  status: 'ok' | 'error'
  episode_id?: string
  video_id?: string
  checks?: Array<{
    name: string
    status: 'passed' | 'failed' | 'warning'
    message: string
  }>
  all_passed?: boolean
  errors?: string[]
}

export async function verifyUpload(request: UploadVerifyRequest): Promise<UploadVerifyResponse> {
  return apiRequest<UploadVerifyResponse>('/api/t2r/upload/verify', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

// Audit
export interface AuditRequest {
  start_date?: string
  end_date?: string
  format?: 'json' | 'csv' | 'markdown'
  report_type?: 'daily' | 'weekly' | 'custom'
}

export interface AuditReport {
  status: 'ok' | 'error'
  report_type?: string
  format?: string
  start_date?: string
  end_date?: string
  data?: any
  content?: string
  errors?: string[]
}

export async function getAuditReport(request: AuditRequest = {}): Promise<AuditReport> {
  const params = new URLSearchParams()
  if (request.start_date) params.set('start_date', request.start_date)
  if (request.end_date) params.set('end_date', request.end_date)
  if (request.format) params.set('format', request.format)
  if (request.report_type) params.set('report_type', request.report_type)
  
  const query = params.toString()
  return apiRequest<AuditReport>(`/api/t2r/audit${query ? `?${query}` : ''}`)
}

