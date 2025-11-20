/**
 * T2R API Service
 * 
 * Client-side API calls for T2R (Trip to Reality) endpoints.
 */
import { getApiBase } from '../lib/apiBase'
import { handleError } from '../lib/errorHandler'
import { logger } from '../lib/logger'
import { T2REpisodesResponseSchema, T2REpisodeSchema, type T2REpisodesResponse as T2REpisodesResponseType, type T2REpisode as T2REpisodeType } from '@/types/schemas'

// Get API base URL lazily (don't call at module level to avoid repeated logs)
function getApiUrl(): string {
  return getApiBase()
}

async function apiRequest<T>(endpoint: string, options?: RequestInit & { channelId?: string }): Promise<T> {
  const API_URL = getApiUrl()
  const url = `${API_URL}${endpoint}`
  const method = options?.method || 'GET'
  
  // 提取 channelId（如果提供）
  const channelId = options?.channelId
  const { channelId: _, ...restOptions } = options || {}
  
  // 构建 headers，添加 x-channel-id 如果提供
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(channelId && { 'x-channel-id': channelId }),
    ...restOptions?.headers,
  }
  
  // 使用 Sentry span 追踪 API 调用性能
  return await import('@sentry/nextjs').then((Sentry) => {
    return Sentry.startSpan(
      {
        op: 'http.client',
        name: `${method} ${endpoint}`,
      },
      async (span) => {
        // 添加相关属性
        span.setAttribute('http.method', method)
        span.setAttribute('http.url', url)
        span.setAttribute('http.endpoint', endpoint)
        if (channelId) {
          span.setAttribute('channel.id', channelId)
        }
        
        // Use logger for structured logging
        logger.debug(`[apiRequest] ${method} ${url}${channelId ? ` [channel: ${channelId}]` : ''}`)
        
        try {
          const response = await fetch(url, {
            ...restOptions,
            headers,
          })
          
          // 设置 HTTP 状态码
          span.setAttribute('http.status_code', response.status)
          
          if (!response.ok) {
            const errorText = await response.text()
            let errorData: any = {}
            try {
              errorData = JSON.parse(errorText)
            } catch {
              errorData = { message: errorText || response.statusText }
            }
            const errorMessage = errorData.message || errorData.errors?.join(', ') || `API Error: ${response.statusText}`
            
            span.setStatus({ code: 2, message: 'error' })
            span.setAttribute('error.message', errorMessage)
            
            // Provide more helpful error message for 404
            if (response.status === 404) {
              throw new Error(`API 端点未找到: ${url}\n请确认：\n1. 后端服务器是否在运行\n2. 路由是否正确注册\n3. 路径是否正确`)
            }
            
            throw new Error(errorMessage)
          }

          const text = await response.text()
          if (!text || text.trim() === '') {
            span.setStatus({ code: 2, message: 'error' })
            throw new Error('API returned empty response')
          }

          try {
            const data = JSON.parse(text) as T
            // Status is automatically set based on span completion
            return data
          } catch (e) {
            span.setStatus({ code: 2, message: 'error' })
            throw new Error(`Invalid JSON response: ${text.substring(0, 100)}`)
          }
        } catch (error) {
          // Status will be set to error automatically
          throw error
        }
      }
    )
  }).catch(() => {
    // 如果 Sentry 不可用，回退到原始实现
    return originalApiRequest<T>(endpoint, options)
  })
}

async function originalApiRequest<T>(endpoint: string, options?: RequestInit & { channelId?: string }): Promise<T> {
  const API_URL = getApiUrl()
  const url = `${API_URL}${endpoint}`
  
  // 提取 channelId（如果提供）
  const channelId = options?.channelId
  const { channelId: _, ...restOptions } = options || {}
  
  // 构建 headers，添加 x-channel-id 如果提供
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(channelId && { 'x-channel-id': channelId }),
    ...restOptions?.headers,
  }
  
  // Use logger for structured logging
  logger.debug(`[apiRequest] ${restOptions?.method || 'GET'} ${url}${channelId ? ` [channel: ${channelId}]` : ''}`)
  
  try {
    const response = await fetch(url, {
      ...restOptions,
      headers,
    })

    if (!response.ok) {
      const errorText = await response.text()
      let errorData: any = {}
      try {
        errorData = JSON.parse(errorText)
      } catch {
        errorData = { message: errorText || response.statusText }
      }
      const errorMessage = errorData.message || errorData.errors?.join(', ') || `API Error: ${response.statusText}`
      logger.error(`[apiRequest] Error ${response.status} ${response.statusText}:`, errorMessage, { 
        url, 
        errorData,
        endpoint,
        apiUrl: API_URL,
        fullUrl: url
      })
      
      // Provide more helpful error message for 404
      if (response.status === 404) {
        throw new Error(`API 端点未找到: ${url}\n请确认：\n1. 后端服务器是否在运行 (${API_URL})\n2. 路由是否正确注册\n3. 路径是否正确`)
      }
      
      throw new Error(errorMessage)
    }

    const text = await response.text()
    if (!text || text.trim() === '') {
      throw new Error('API returned empty response')
    }

    try {
      return JSON.parse(text) as T
    } catch (e) {
      throw new Error(`Invalid JSON response: ${text.substring(0, 100)}`)
    }
  } catch (error: any) {
    // Handle network errors (backend not running, CORS, etc.)
    if (error.name === 'TypeError' && (error.message.includes('fetch') || error.message.includes('Failed to fetch'))) {
      // Report to Sentry for network errors (except for non-critical endpoints)
      const isCriticalEndpoint = endpoint.includes('/health') || endpoint.includes('/api-health')
      const isNonCriticalEndpoint = endpoint.includes('/library-stats') || endpoint.includes('/channel-info')
      const shouldReportToSentry = !isNonCriticalEndpoint
      
      if (shouldReportToSentry) {
        // Use dynamic import to avoid bundling Sentry in production if not needed
        import('@sentry/nextjs').then((Sentry) => {
          // Only report if Sentry is enabled (DSN is configured)
          if (process.env.NEXT_PUBLIC_SENTRY_DSN) {
            Sentry.captureException(error, {
              tags: {
                error_type: 'network_error',
                endpoint,
                api_url: API_URL,
                component: 't2rApi',
              },
              contexts: {
                network: {
                  url,
                  endpoint,
                  api_url: API_URL,
                  method: restOptions?.method || 'GET',
                },
              },
              level: 'error',
              extra: {
                error_name: error.name,
                error_message: error.message,
                stack: error.stack,
              },
            })
            // Log to logger for debugging (only in development)
            if (process.env.NODE_ENV === 'development') {
              logger.debug('[Sentry] Network error reported to Sentry', {
                endpoint,
                url,
                error_name: error.name,
              })
            }
          } else {
            // Sentry not configured, log to logger
            if (process.env.NODE_ENV === 'development') {
              logger.warn('[Sentry] NEXT_PUBLIC_SENTRY_DSN not configured, error not reported to Sentry')
            }
          }
        }).catch((importError) => {
          // Sentry not available, log to logger
          if (process.env.NODE_ENV === 'development') {
            logger.warn('[Sentry] Failed to import Sentry', { error: importError })
          }
        })
      }
      
      // Only log detailed error in debug mode or for critical endpoints
      const shouldLogDetailed = isCriticalEndpoint || process.env.NODE_ENV === 'development'
      
      if (shouldLogDetailed) {
        logger.error(`[apiRequest] Network error connecting to ${url}:`, error, {
          url,
          apiUrl: API_URL,
          endpoint,
          errorName: error.name,
          errorMessage: error.message,
        })
      } else {
        // Silent log for non-critical endpoints (library stats, etc.)
        logger.debug(`[apiRequest] Backend not available for ${endpoint}`)
      }
      
      // Create a more user-friendly error
      const isHealthCheck = endpoint.includes('/health') || endpoint.includes('/api-health')
      if (isHealthCheck) {
        // For health checks, provide detailed error message
        throw new Error(
          `无法连接到后端服务 (${API_URL})。\n` +
          `错误详情: ${error.message}\n` +
          `尝试的 URL: ${url}\n\n` +
          `请确认：\n` +
          `1. 后端服务器是否在运行 (运行 \`curl ${API_URL}/health\` 测试)\n` +
          `2. 端口是否正确 (应该是 8000)\n` +
          `3. 防火墙或代理是否阻止了连接\n` +
          `4. 浏览器控制台是否有 CORS 错误\n\n` +
          `提示: 运行 \`bash scripts/start.sh\` 或 \`make start\` 启动后端服务。`
        )
      } else {
        // For other endpoints, provide helpful error message
        const networkError = new Error(
          `无法连接到后端服务 (${API_URL})\n` +
          `端点: ${endpoint}\n` +
          `完整URL: ${url}\n\n` +
          `可能的原因：\n` +
          `1. 后端服务器未运行 - 请运行 \`bash scripts/start.sh\` 或 \`make start\`\n` +
          `2. 端口不匹配 - 检查后端是否在端口 8000 运行\n` +
          `3. CORS 问题 - 检查浏览器控制台的 CORS 错误\n` +
          `4. 网络连接问题 - 检查防火墙或代理设置`
        )
        ;(networkError as any).isNetworkError = true
        ;(networkError as any).endpoint = endpoint
        ;(networkError as any).url = url
        ;(networkError as any).apiUrl = API_URL
        throw networkError
      }
    }
    
    // Re-throw other errors (network errors already handled above)
    handleError(error, {
      component: 't2rApi',
      action: 'apiRequest',
      showToast: false, // API 错误由调用方处理
    })
    throw error
  }
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

export interface InitEpisodeRequest {
  episode_id: string
  channel_id: string
  start_date?: string
  avoid_duplicates?: boolean
  seo_template?: boolean
}

export interface InitEpisodeResponse {
  status: 'ok' | 'error'
  episode_id?: string
  recipe?: any
  recipe_json_path?: string
  playlist_path?: string
  playlist_result?: {
    status?: string
    playlist_path?: string
    message?: string
    errors?: string[]
    [key: string]: any
  }
  message?: string
  errors?: string[]
  timestamp?: string
}

/**
 * Unified init-episode endpoint (Recipe + Playlist in one call).
 */
export async function initEpisode(
  request: InitEpisodeRequest & { channelId?: string }
): Promise<InitEpisodeResponse> {
  const { channelId, ...restRequest } = request
  return apiRequest<InitEpisodeResponse>('/api/t2r/init-episode', {
    method: 'POST',
    body: JSON.stringify(restRequest),
    channelId,
  })
}

export async function ensurePlaylistInitialized(
  request: InitEpisodeRequest & { channelId?: string }
): Promise<InitEpisodeResponse> {
  try {
    const result = await initEpisode(request)
    if (result.status === 'ok') {
      return result
    }
    const legacy = await legacyPlanAndPlaylist(request)
    return legacy
  } catch (error) {
    logger.warn('[t2rApi] initEpisode failed, using legacy plan+playlist', { error })
    return legacyPlanAndPlaylist(request)
  }
}

async function legacyPlanAndPlaylist(
  request: InitEpisodeRequest & { channelId?: string }
): Promise<InitEpisodeResponse> {
  // Use initEpisode directly - deprecated planEpisode fallback has been removed
  try {
    const result = await initEpisode(request)
    // If initEpisode succeeded, return it
    if (result.status === 'ok' && result.playlist_result?.playlist_path) {
      return result
    }
    
    // If initEpisode succeeded but playlist_path is missing, try generatePlaylist as fallback
    let playlistPath = result.playlist_result?.playlist_path
    let playlistResult = result.playlist_result

    if (!playlistPath) {
    const fallback = await generatePlaylist({
      episode_id: request.episode_id,
      channel_id: request.channel_id,
    })
    if (!fallback || fallback.status !== 'ok' || !fallback.playlist_path) {
      return {
        status: 'error',
        errors: fallback?.errors || ['generatePlaylist failed'],
        message: fallback?.message,
      }
    }
    playlistPath = fallback.playlist_path
    playlistResult = fallback
  }

  if (!playlistPath) {
    const metadata = await getPlaylistMetadata(request.episode_id, request.channel_id)
    playlistPath = metadata.playlist_metadata?.playlist_path || undefined
  }

  if (!playlistPath) {
    return {
      status: 'error',
      errors: ['Playlist file not found after legacy fallback'],
    }
  }

  return {
    status: 'ok',
    episode_id: request.episode_id,
      recipe: result.recipe,
      recipe_json_path: result.recipe_json_path,
    playlist_path: playlistPath,
    playlist_result: playlistResult || { status: 'ok', playlist_path: playlistPath },
    message: 'legacy-init',
    errors: [],
    }
  } catch (error) {
    logger.error('[t2rApi] initEpisode failed in legacyPlanAndPlaylist', { error })
    const errorMessage = error instanceof Error ? error.message : 'Unknown error'
    return {
      status: 'error',
      errors: [errorMessage],
      message: errorMessage,
    }
  }
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

export async function runEpisode(request: RunRequest & { channelId?: string }): Promise<RunResponse> {
  const { channelId, ...restRequest } = request
  logger.debug('[t2rApi] runEpisode called:', { episode_id: restRequest.episode_id, stages: restRequest.stages, channelId })
  try {
    const response = await apiRequest<RunResponse>('/api/t2r/run', {
      method: 'POST',
      body: JSON.stringify(restRequest),
      channelId,
    })
    logger.debug('[t2rApi] runEpisode response:', response)
    return response
  } catch (error) {
    logger.error('[t2rApi] runEpisode error:', error)
    throw error
  }
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

// Playlist Generation
export interface GeneratePlaylistRequest {
  episode_id: string
  channel_id: string
}

export interface GeneratePlaylistResponse {
  status: 'ok' | 'error'
  episode_id?: string
  side_a?: Array<{ title: string; artist?: string; duration?: string }>
  side_b?: Array<{ title: string; artist?: string; duration?: string }>
  playlist_path?: string
  message?: string
  errors?: string[]
  timestamp?: string
}

export async function generatePlaylist(request: GeneratePlaylistRequest & { channelId?: string }): Promise<GeneratePlaylistResponse> {
  const { channelId, ...restRequest } = request
  return apiRequest<GeneratePlaylistResponse>('/api/t2r/generate-playlist', {
    method: 'POST',
    body: JSON.stringify(restRequest),
    channelId: channelId || (request as any).channel_id,
  })
}

export interface SelectorGeneratePlaylistRequest {
  episode_id: string
  channel_id: string
}

export interface SelectorGeneratePlaylistResponse {
  status: 'ok' | 'error'
  episode_id?: string
  side_a?: Array<{ title: string; artist?: string; duration?: string }>
  side_b?: Array<{ title: string; artist?: string; duration?: string }>
  playlist_path?: string
  message?: string
  errors?: string[]
  timestamp?: string
}

export async function selectorGeneratePlaylist(request: SelectorGeneratePlaylistRequest): Promise<SelectorGeneratePlaylistResponse> {
  return apiRequest<SelectorGeneratePlaylistResponse>('/api/t2r/selector/generate-playlist', {
    channelId: request.channel_id,
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export interface FillerGenerateRequest {
  episode_id: string
  channel_id: string
  asset_types?: ('title' | 'description' | 'captions' | 'tags')[]
  overwrite?: boolean
}

export interface FillerGenerateResponse {
  status: 'ok' | 'error'
  episode_id: string
  title?: string
  description_path?: string
  captions_path?: string
  tags_path?: string
  tags?: string[]
  message: string
  errors?: string[]
  timestamp?: string
}

export async function fillerGenerate(request: FillerGenerateRequest): Promise<FillerGenerateResponse> {
  return apiRequest<FillerGenerateResponse>('/api/t2r/filler/generate', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export interface PlaylistMetadataResponse {
  status: 'ok' | 'error'
  playlist_metadata?: {
    episode_id: string
    channel_id: string
    generated_at: string
    starting_track: { title: string; artist?: string }
    side_a: {
      tracks: Array<{ title: string; artist?: string; duration?: string }>
      count: number
      duration_sec: number
      duration_formatted: string
    }
    side_b: {
      tracks: Array<{ title: string; artist?: string; duration?: string }>
      count: number
      duration_sec: number
      duration_formatted: string
    }
    total: {
      count: number
      duration_sec: number
      duration_formatted: string
    }
    full_mix: {
      duration_sec: number
      duration_formatted: string
    }
    playlist_path: string
  }
  errors?: string[]
}

export async function getPlaylistMetadata(episode_id: string, channel_id: string): Promise<PlaylistMetadataResponse> {
  return apiRequest<PlaylistMetadataResponse>(`/api/t2r/playlist-metadata?episode_id=${encodeURIComponent(episode_id)}&channel_id=${encodeURIComponent(channel_id)}`)
}

// Cover Generation
export interface GenerateCoverRequest {
  episode_id: string
  channel_id: string
}

export interface GenerateCoverResponse {
  status: 'ok' | 'error'
  episode_id?: string
  image_path?: string
  image_id?: string
  color_hex?: string
  title?: string
  cover_path?: string
  message?: string
  errors?: string[]
  timestamp?: string
}

export async function generateCover(request: GenerateCoverRequest & { channelId?: string }): Promise<GenerateCoverResponse> {
  const { channelId, ...restRequest } = request
  return apiRequest<GenerateCoverResponse>('/api/t2r/generate-cover', {
    method: 'POST',
    body: JSON.stringify(restRequest),
    channelId: channelId || (request as any).channel_id,
  })
}

// Episodes
export interface T2REpisode {
  episode_id: string
  channel_id: string
  date: string
  status: string
  title?: string
  image_path?: string  // Original source image from library (for drawer display)
  cover_path?: string  // Generated cover image (_cover.png) (for card display)
  output_file?: string
  playlist_path?: string
  assets?: {
    audio?: string
    cover?: string
    captions?: string
  }
}

export interface T2REpisodesResponse {
  episodes?: T2REpisode[]
  total?: number
  schedule_empty?: boolean
  needs_initialization?: boolean
  timestamp?: string
  error?: string
}

export interface AudioRemixProgress {
  episode_id: string
  audio_path: string | null
  audio_size: number | null
  expected_size: number | null
  progress: number | null
  is_remixing: boolean
  is_complete: boolean
  error?: string
  timestamp: string
}

export interface VideoRenderProgress {
  episode_id: string
  video_path: string | null
  video_size: number | null
  expected_size: number | null
  progress: number | null
  is_rendering: boolean
  is_complete: boolean
  render_complete_flag?: string | null  // ✅ 新增：render_complete_flag 路径
  error?: string
  timestamp: string
}

/**
 * Get audio remix progress by checking MP3 file size
 */
export async function getAudioRemixProgress(
  episode_id: string,
  channel_id?: string
): Promise<AudioRemixProgress> {
  const endpoint = `/api/t2r/episodes/${episode_id}/audio-progress`
  const response = await apiRequest<AudioRemixProgress>(endpoint, {
    method: 'GET',
    channelId: channel_id,
  })
  return response
}

/**
 * Get video render progress by checking file size
 */
export async function getVideoRenderProgress(
  episode_id: string,
  channel_id?: string
): Promise<VideoRenderProgress> {
  const endpoint = `/api/t2r/episodes/${episode_id}/video-progress`
  const response = await apiRequest<VideoRenderProgress>(endpoint, {
    method: 'GET',
    channelId: channel_id,
  })
  return response
}

export async function fetchT2REpisodes(channel_id?: string): Promise<T2REpisodesResponse> {
  const queryParam = channel_id ? `?channel_id=${encodeURIComponent(channel_id)}` : ''
  const response = await apiRequest<T2REpisodesResponse>(`/api/t2r/episodes${queryParam}`, {
    channelId: channel_id,
  })
  
  // Validate response with Zod
  const validationResult = T2REpisodesResponseSchema.safeParse(response)
  if (!validationResult.success) {
    // Log detailed validation errors
    logger.warn('[fetchT2REpisodes] Validation errors:', validationResult.error.issues)
    logger.debug('[fetchT2REpisodes] Actual response:', response)
    
    // Report to Sentry but don't break the app
    const errorMessage = `Invalid API response format: ${validationResult.error.issues.map(e => `${e.path.join('.')}: ${e.message}`).join('; ')}`
    handleError(new Error(errorMessage), {
      component: 't2rApi',
      action: 'fetchT2REpisodes',
      showToast: false,
    })
    
    // Return response anyway to avoid breaking the app
    // The app can handle partial/invalid data gracefully
    return response as T2REpisodesResponse
  }
  
  return validationResult.data
}

// Work Cursor API
export interface WorkCursorResponse {
  status: string
  channel_id: string
  work_cursor_date: string | null
  calculated: boolean
  timestamp: string
}

export async function getWorkCursor(channel_id?: string): Promise<WorkCursorResponse> {
  const queryParam = channel_id ? `?channel_id=${encodeURIComponent(channel_id)}` : ''
  return apiRequest<WorkCursorResponse>(`/api/t2r/schedule/work-cursor${queryParam}`, {
    channelId: channel_id,
  })
}

export async function updateWorkCursor(
  channel_id?: string,
  new_cursor_date?: string
): Promise<WorkCursorResponse> {
  const queryParam = channel_id ? `?channel_id=${encodeURIComponent(channel_id)}` : ''
  const dateParam = new_cursor_date ? `&new_cursor_date=${encodeURIComponent(new_cursor_date)}` : ''
  return apiRequest<WorkCursorResponse>(`/api/t2r/schedule/work-cursor/update${queryParam}${dateParam}`, {
    method: 'POST',
    channelId: channel_id,
  })
}

// Initialize Schedule
export interface InitializeScheduleRequest {
  channel_id: string
  days: number  // Number of days to initialize (default: 7)
}

export interface InitializeScheduleResponse {
  status: 'initialized' | 'error'
  channel_id?: string
  days?: number
  episodes_created?: number
  folders_created?: boolean
  content_ready?: boolean
  timestamp?: string
  errors?: string[]
}

export async function initializeSchedule(
  channelId: string,
  days: number
): Promise<InitializeScheduleResponse> {
  return apiRequest<InitializeScheduleResponse>(
    `/api/t2r/schedule/initialize?channel_id=${encodeURIComponent(channelId)}`,
    {
      method: 'POST',
      body: JSON.stringify({ days }),
      channelId,
    }
  )
}

// Create Episode
export interface CreateEpisodeRequest {
  channel_id: string
  date: string  // ISO date string (YYYY-MM-DD)
  start_generation?: boolean  // Whether to start generation workflow after creation
}

export interface CreateEpisodeResponse {
  status: 'ok' | 'error'
  channel_id?: string
  episode_id?: string
  schedule_date?: string
  output_dir?: string
  csv_path?: string
  episode?: any
  automation_queued?: boolean  // Indicates if automation was successfully queued
  errors?: string[]
  timestamp?: string
}

export async function createEpisode(request: CreateEpisodeRequest): Promise<CreateEpisodeResponse> {
  return apiRequest<CreateEpisodeResponse>('/api/t2r/schedule/create-episode', {
    method: 'POST',
    body: JSON.stringify(request),
    channelId: request.channel_id,
  })
}

// Resume Episode Workflow
export interface ResumeEpisodeRequest {
  channel_id: string
  episode_id: string
}

export interface ResumeEpisodeResponse {
  status: 'ok' | 'error'
  channel_id: string
  episode_id: string
  automation_queued: boolean
  message?: string
  errors?: string[]
  timestamp: string
}

/**
 * 恢复已存在episode的工作流
 * 
 * 对于只生成了playlist但后续阶段未执行的episode，手动将其加入自动化队列。
 * 这会触发 remix → cover → text assets 流程。
 * 
 * @param request - ResumeEpisodeRequest with channel_id and episode_id
 * @returns ResumeEpisodeResponse
 */
export async function resumeEpisode(request: ResumeEpisodeRequest): Promise<ResumeEpisodeResponse> {
  return apiRequest<ResumeEpisodeResponse>('/api/t2r/schedule/resume-episode', {
    method: 'POST',
    body: JSON.stringify(request),
    channelId: request.channel_id,
  })
}

// Reset Channel
export interface ResetChannelRequest {
  channel_id?: string
  confirmation?: string  // Must be "RESET" for safety
}

export interface ResetChannelResponse {
  status: 'reset_complete' | 'partial' | 'error'
  channel_id?: string
  deleted_files?: number
  deleted_dirs?: number
  schedule_empty?: boolean
  assets_reset?: boolean
  output_cleared?: boolean
  errors?: string[]
  message?: string
}

export async function resetChannel(request: ResetChannelRequest & { confirm?: boolean }): Promise<ResetChannelResponse> {
  // If confirm is true, set confirmation to "RESET"
  const requestBody = {
    channel_id: request.channel_id,
    confirmation: request.confirmation || (request.confirm === true ? 'RESET' : ''),
  }
  
  return apiRequest<ResetChannelResponse>('/api/t2r/reset/channel', {
    method: 'POST',
    body: JSON.stringify(requestBody),
  })
}

// API Health Check
export interface APIStatus {
  provider: string
  name: string
  configured: boolean
  available: boolean
  last_checked?: string
  error?: string
  response_time_ms?: number
}

export interface APIHealthResponse {
  status: 'ok' | 'partial' | 'error'
  apis: APIStatus[]
  timestamp: string
  error?: string
}

export async function checkAPIHealth(): Promise<APIHealthResponse> {
  return apiRequest<APIHealthResponse>('/api/t2r/api-health', {
    method: 'GET',
  })
}

// Regenerate Asset
export interface RegenerateAssetRequest {
  episode_id: string
  channel_id: string
  asset_type: 'captions' | 'description' | 'cover' | 'audio' | 'title'
  overwrite?: boolean
}

export interface RegenerateAssetResponse {
  status: 'ok' | 'error'
  asset_type?: string
  episode_id?: string
  file_path?: string
  message?: string
  errors?: string[]
  timestamp?: string
}

export async function regenerateAsset(request: RegenerateAssetRequest & { channelId?: string }): Promise<RegenerateAssetResponse> {
  const { channelId, ...restRequest } = request
  return apiRequest<RegenerateAssetResponse>('/api/t2r/regenerate-asset', {
    method: 'POST',
    body: JSON.stringify(restRequest),
    channelId: channelId || (request as any).channel_id,
  })
}

// Telemetry
export interface TelemetryEvent {
  event_type: 'stage_click' | 'stage_preview' | 'stage_open_folder'
  episode_id: string
  channel_id: string
  stage: string
  action: 'generate' | 'preview' | 'open_folder'
  metadata?: Record<string, any>
}

export interface TelemetryResponse {
  status: 'ok' | 'error'
  message?: string
  timestamp?: string
}

export async function logTelemetry(event: TelemetryEvent): Promise<TelemetryResponse> {
  return apiRequest<TelemetryResponse>('/api/t2r/telemetry', {
    method: 'POST',
    body: JSON.stringify(event),
  })
}

// Channel
export interface T2RChannel {
  id: string
  name: string
  isActive: boolean
  nextSchedule?: string
  queueCount?: number
  totalEpisodes?: number
  lockedCount?: number
}

export async function fetchT2RChannel(channel_id?: string): Promise<T2RChannel> {
  const queryParam = channel_id ? `?channel_id=${encodeURIComponent(channel_id)}` : ''
  return apiRequest<T2RChannel>(`/api/t2r/channel${queryParam}`)
}

export interface ChannelProfile {
  id: string
  name: string
  description?: string
  handle?: string
  avatar_url?: string
  channel_url?: string
  studio_url?: string
  youtube_metadata?: {
    video_count?: string
    view_count?: string
    subscriber_count?: string
    joined_date?: string
    custom_url?: string
  }
}

export async function fetchChannelProfile(channel_id?: string): Promise<ChannelProfile> {
  const queryParam = channel_id ? `?channel_id=${encodeURIComponent(channel_id)}` : ''
  return apiRequest<ChannelProfile>(`/api/t2r/channel/profile${queryParam}`)
}

export interface RenderQueueResponse {
  status: string
  channel_id: string
  results: { episode_id: string; queued: boolean }[]
  timestamp: string
}

export async function enqueueRenderJobs(channel_id: string, episode_ids: string[]): Promise<RenderQueueResponse> {
  return apiRequest<RenderQueueResponse>(`/api/t2r/render-queue/enqueue`, {
    method: 'POST',
    body: JSON.stringify({
      channel_id,
      episode_ids,
    }),
  })
}
