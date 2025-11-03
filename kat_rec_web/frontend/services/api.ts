/**
 * API Service
 *
 * Client-side API calls to backend FastAPI service.
 */
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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
export async function fetchSongs(params?: { search?: string; limit?: number }) {
  const queryParams = new URLSearchParams()
  if (params?.search) queryParams.set('search', params.search)
  if (params?.limit) queryParams.set('limit', params.limit.toString())
  
  const query = queryParams.toString()
  return apiRequest(`/api/library/songs${query ? `?${query}` : ''}`)
}

export async function fetchImages(params?: { search?: string; limit?: number }) {
  const queryParams = new URLSearchParams()
  if (params?.search) queryParams.set('search', params.search)
  if (params?.limit) queryParams.set('limit', params.limit.toString())
  
  const query = queryParams.toString()
  return apiRequest(`/api/library/images${query ? `?${query}` : ''}`)
}

// Metrics endpoints
export async function fetchSummary(period: string = '24h') {
  return apiRequest(`/metrics/summary?period=${period}`)
}

export async function fetchEpisodes(params?: { status?: string; limit?: number }) {
  const queryParams = new URLSearchParams()
  if (params?.status) queryParams.set('status', params.status)
  if (params?.limit) queryParams.set('limit', params.limit.toString())
  
  const query = queryParams.toString()
  return apiRequest(`/metrics/episodes${query ? `?${query}` : ''}`)
}

export async function fetchEvents(params?: { limit?: number; since?: string }) {
  const queryParams = new URLSearchParams()
  if (params?.limit) queryParams.set('limit', params.limit.toString())
  if (params?.since) queryParams.set('since', params.since)
  
  const query = queryParams.toString()
  return apiRequest(`/metrics/events${query ? `?${query}` : ''}`)
}

// Channels endpoints (for Channel Workbench)
export async function fetchChannels() {
  // 尝试从 /api/channels 获取，如果失败则返回空数组
  return apiRequest('/api/channels').catch(() => {
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
