/**
 * API Service
 *
 * Client-side API calls to backend FastAPI service.
 */
import { getApiBase } from '../lib/apiBase'

const API_URL = getApiBase()

// API Client helper
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

// Status endpoints
export async function fetchStatus() {
  return apiRequest('/api/status')
}

export async function fetchChannel(channelId?: string) {
  const url = channelId ? `/api/channel?channel_id=${channelId}` : '/api/channel'
  return apiRequest(url)
}

// Library endpoints
export interface Song {
  id: string
  title: string
  artist?: string
  duration?: number
  file_path?: string
}

export interface Image {
  id: string
  filename: string
  path?: string
  url?: string
}

export async function fetchSongs(params?: { search?: string; limit?: number }): Promise<Song[]> {
  const queryParams = new URLSearchParams()
  if (params?.search) queryParams.set('search', params.search)
  if (params?.limit) queryParams.set('limit', params.limit.toString())
  
  const query = queryParams.toString()
  return apiRequest<Song[]>(`/api/library/songs${query ? `?${query}` : ''}`)
}

export async function fetchImages(params?: { search?: string; limit?: number }): Promise<Image[]> {
  const queryParams = new URLSearchParams()
  if (params?.search) queryParams.set('search', params.search)
  if (params?.limit) queryParams.set('limit', params.limit.toString())
  
  const query = queryParams.toString()
  return apiRequest<Image[]>(`/api/library/images${query ? `?${query}` : ''}`)
}

// Metrics endpoints
export interface SummaryData {
  global_state?: {
    total_episodes: number
    completed: number
    error: number
    remixing: number
    rendering: number
    pending: number
  }
  stages?: {
    [key: string]: {
      avg_duration: number
      count: number
    }
  }
  period?: string
}

export async function fetchSummary(period: string = '24h'): Promise<SummaryData> {
  return apiRequest<SummaryData>(`/metrics/summary?period=${period}`)
}

export interface Episode {
  id: string
  episode_id: string
  episode_number?: number
  status: 'pending' | 'remixing' | 'rendering' | 'uploading' | 'completed' | 'error'
  schedule_date?: string
  progress?: number
  created_at?: string
  updated_at?: string
}

export interface EpisodesResponse {
  episodes: Episode[]
  total?: number
}

export async function fetchEpisodes(params?: { status?: string; limit?: number }): Promise<EpisodesResponse> {
  const queryParams = new URLSearchParams()
  if (params?.status) queryParams.set('status', params.status)
  if (params?.limit) queryParams.set('limit', params.limit.toString())
  
  const query = queryParams.toString()
  return apiRequest<EpisodesResponse>(`/metrics/episodes${query ? `?${query}` : ''}`)
}

export async function fetchEvents(params?: { limit?: number; since?: string }) {
  const queryParams = new URLSearchParams()
  if (params?.limit) queryParams.set('limit', params.limit.toString())
  if (params?.since) queryParams.set('since', params.since)
  
  const query = queryParams.toString()
  return apiRequest(`/metrics/events${query ? `?${query}` : ''}`)
}

// Channels endpoints (for Channel Workbench)
export interface Channel {
  id: string
  name: string
  isActive: boolean
  nextSchedule?: string
  queueCount?: number
}

export async function fetchChannels(): Promise<Channel[]> {
  // 尝试从 /api/channels 获取，如果失败则返回空数组
  return apiRequest<Channel[]>('/api/channels').catch(() => {
    // 如果API不存在，返回空数组
    return []
  })
}

// Upload endpoints
export async function enqueueUpload(task: {
  episode_id: string
  video_file: string
  title?: string
  description?: string
  privacy?: string
}) {
  return apiRequest('/api/upload', {
    method: 'POST',
    body: JSON.stringify(task),
  })
}

// Queue endpoints
export async function fetchQueue(params?: { status?: string; limit?: number }) {
  const queryParams = new URLSearchParams()
  if (params?.status) queryParams.set('status', params.status)
  if (params?.limit) queryParams.set('limit', params.limit.toString())
  
  const query = queryParams.toString()
  return apiRequest(`/api/ops/queue${query ? `?${query}` : ''}`).catch(() => {
    // 如果API不存在，返回空数组
    return []
  })
}

export async function retryTask(taskId: string) {
  return apiRequest(`/api/ops/queue/${taskId}/retry`, {
    method: 'POST',
  })
}

export async function pauseTask(taskId: string) {
  return apiRequest(`/api/ops/queue/${taskId}/pause`, {
    method: 'POST',
  })
}

export async function updateTaskPriority(taskId: string, priority: number) {
  return apiRequest(`/api/ops/queue/${taskId}/priority`, {
    method: 'PUT',
    body: JSON.stringify({ priority }),
  })
}

// Alerts endpoints
export async function fetchAlerts(params?: { unread_only?: boolean; limit?: number }) {
  const queryParams = new URLSearchParams()
  if (params?.unread_only) queryParams.set('unread_only', 'true')
  if (params?.limit) queryParams.set('limit', params.limit.toString())
  
  const query = queryParams.toString()
  return apiRequest(`/api/alerts${query ? `?${query}` : ''}`).catch(() => {
    // 如果API不存在，返回空数组
    return []
  })
}

export async function acknowledgeAlert(alertId: string) {
  return apiRequest(`/api/alerts/${alertId}/acknowledge`, {
    method: 'POST',
  })
}

// Task control endpoints
export interface TaskControlRequest {
  channel_id: string
  action: 'start' | 'pause' | 'retry' | 'stop'
}

export interface TaskControlResponse {
  status: string
  message: string
  channel_id: string
  timestamp: string
}

export async function controlTask(request: TaskControlRequest): Promise<TaskControlResponse> {
  return apiRequest<TaskControlResponse>('/api/task/control', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}
