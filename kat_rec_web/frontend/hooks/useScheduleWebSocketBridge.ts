/**
 * Schedule WebSocket Bridge
 * 
 * Bridges WebSocket events to ScheduleStore updates.
 * Listens for real-time status changes and updates events accordingly.
 */
import { useEffect, useRef } from 'react'
import { WSClient, type WSMessage } from '@/services/wsClient'
import { useScheduleStore } from '@/stores/scheduleStore'
import { useRunbookStore } from '@/stores/runbookStore'
import { normalizeStatus, type ScheduleEventStatus } from '@/lib/designTokens'
import { getWsBase } from '@/lib/apiBase'

const WS_URL = getWsBase()

/**
 * Hook to bridge WebSocket events to ScheduleStore
 */
export function useScheduleWebSocketBridge() {
  const clientRef = useRef<WSClient | null>(null)
  const patchEvent = useScheduleStore((state) => state.patchEvent)
  const markEventStatus = useScheduleStore((state) => state.markEventStatus)
  const addLog = useRunbookStore((state) => state.addLog)
  const setCurrentStage = useRunbookStore((state) => state.setCurrentStage)
  const setProgress = useRunbookStore((state) => state.setProgress)
  
  useEffect(() => {
    clientRef.current = new WSClient({
      url: `${WS_URL}/ws/status`,
      onMessage: (message: WSMessage) => {
        // Handle event-type messages
        if (message.type === 'event' && message.data) {
          const eventType = message.data.type || message.data.get?.('type')
          const data = message.data.data || message.data
          
          // T2R scan progress (updates lock status)
          if (eventType === 't2r_scan_progress') {
            if (data.episode_id && data.locked) {
              markEventStatus(data.episode_id, 'verified')
            }
          }
          
          // Runbook stage update (rendering, upload, etc.)
          if (eventType === 'runbook_stage_update' || eventType === 't2r_runbook_stage_update') {
            const episodeId = data.episode_id || data.episodeId
            if (episodeId) {
              // Map stage to status
              const stage = data.stage?.toLowerCase() || ''
              let status: ScheduleEventStatus = 'draft'
              
              if (stage.includes('plan') || stage.includes('planning')) {
                status = 'planned'
              } else if (stage.includes('remix')) {
                status = 'planned'
              } else if (stage.includes('render')) {
                status = 'rendering'
              } else if (stage.includes('upload')) {
                status = 'uploaded'
              } else if (stage.includes('verify') || stage.includes('completed')) {
                status = 'verified'
              } else if (stage.includes('error') || stage.includes('failed')) {
                status = 'failed'
              }
              
              // Update event status
              markEventStatus(episodeId, status)
              
              // Update KPIs
              patchEvent(episodeId, {
                kpis: {
                  lastRunAt: data.timestamp || new Date().toISOString(),
                },
              })
              
              // Update runbook store for UI
              setCurrentStage(data.stage as any)
              setProgress(data.progress || 0)
              addLog({
                timestamp: data.timestamp || new Date().toISOString(),
                stage: data.stage as any,
                message: data.message || '',
                level: (data.level || 'info') as 'info' | 'warning' | 'error',
              })
            }
          }
          
          // Upload progress
          if (eventType === 'upload_progress' || eventType === 't2r_upload_progress') {
            const episodeId = data.episode_id || data.episodeId
            if (episodeId) {
              markEventStatus(episodeId, 'uploaded')
              
              // Update progress in runbook store
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
            const episodeId = data.episode_id || data.episodeId
            if (episodeId) {
              const status: ScheduleEventStatus = data.all_passed ? 'verified' : 'failed'
              markEventStatus(episodeId, status)
              
              // Update issues if verification failed
              if (!data.all_passed && data.checks) {
                const issues = data.checks
                  .filter((check: any) => check.status === 'failed')
                  .map((check: any) => check.message)
                
                patchEvent(episodeId, { issues })
              }
              
              addLog({
                timestamp: data.timestamp || new Date().toISOString(),
                stage: 'verify',
                message: data.message || (data.all_passed ? 'Verification passed' : 'Verification failed'),
                level: data.all_passed ? 'info' : 'warning',
              })
            }
          }
          
          // Error events
          if (eventType === 'error' || eventType === 't2r_runbook_error') {
            const episodeId = data.episode_id || data.episodeId
            if (episodeId) {
              markEventStatus(episodeId, 'failed')
              
              const issues = [data.message || data.error || 'Unknown error']
              patchEvent(episodeId, { issues })
              
              addLog({
                timestamp: data.timestamp || new Date().toISOString(),
                stage: 'failed',
                message: data.message || data.error || 'Unknown error',
                level: 'error',
              })
            }
          }
        }
        
        // Handle status_update messages
        if (message.type === 'status_update' && message.data) {
          const data = message.data
          
          // Update episode status if episode_id is present
          if (data.episode_id && data.status) {
            const status = normalizeStatus(data.status) as ScheduleEventStatus
            markEventStatus(data.episode_id, status)
          }
        }
      },
      onError: (error) => {
        console.error('Schedule WebSocket error:', error)
      },
      onOpen: () => {
        console.log('✅ Schedule WebSocket connected')
      },
      onClose: () => {
        console.log('👋 Schedule WebSocket disconnected')
      },
    })
    
    clientRef.current.connect()
    
    return () => {
      clientRef.current?.disconnect()
    }
  }, [patchEvent, markEventStatus, addLog, setCurrentStage, setProgress])
  
  return {
    client: clientRef.current,
  }
}
