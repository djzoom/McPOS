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
export async function scanSchedule() {
  return apiRequest('/api/t2r/scan', { method: 'POST' })
}

// SRT Operations
export interface SRTInspectRequest {
  episode_id?: string
  file_path?: string
}

export async function inspectSRT(request: SRTInspectRequest) {
  return apiRequest('/api/t2r/srt/inspect', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export interface SRTFixRequest {
  episode_id: string
  strategy: 'clip' | 'shift' | 'merge'
  dry_run?: boolean
}

export async function fixSRT(request: SRTFixRequest) {
  return apiRequest('/api/t2r/srt/fix', {
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

export async function lintDescription(request: DescLintRequest) {
  return apiRequest('/api/t2r/desc/lint', {
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

export async function planEpisode(request: PlanRequest) {
  return apiRequest('/api/episodes/plan', {
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

export async function runEpisode(request: RunRequest) {
  return apiRequest('/api/episodes/run', {
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
  return apiRequest('/api/upload/start', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function getUploadStatus(uploadId: string) {
  return apiRequest(`/api/upload/status?upload_id=${uploadId}`)
}

export interface UploadVerifyRequest {
  episode_id: string
  video_id: string
  platform?: string
}

export async function verifyUpload(request: UploadVerifyRequest) {
  return apiRequest('/api/upload/verify', {
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

export async function getAuditReport(request: AuditRequest = {}) {
  const params = new URLSearchParams()
  if (request.start_date) params.set('start_date', request.start_date)
  if (request.end_date) params.set('end_date', request.end_date)
  if (request.format) params.set('format', request.format)
  if (request.report_type) params.set('report_type', request.report_type)
  
  const query = params.toString()
  return apiRequest(`/api/t2r/audit${query ? `?${query}` : ''}`)
}

