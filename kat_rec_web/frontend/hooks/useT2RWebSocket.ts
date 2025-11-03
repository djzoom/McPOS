/**
 * T2R WebSocket Hook
 * 
 * Manages WebSocket connections for T2R-specific events.
 */
import { useEffect, useRef } from 'react'
import { WSClient, type WSMessage } from '@/services/wsClient'
import { useT2RScheduleStore } from '@/stores/t2rScheduleStore'
import { useT2RAssetsStore } from '@/stores/t2rAssetsStore'
import { useT2RSrtStore } from '@/stores/t2rSrtStore'
import { useRunbookStore } from '@/stores/runbookStore'
import { getWsBase } from '@/lib/apiBase'

const WS_URL = getWsBase()

export function useT2RWebSocket() {
  const statusClientRef = useRef<WSClient | null>(null)
  const updateEpisode = useT2RScheduleStore((state) => state.updateEpisode)
  const addConflict = useT2RAssetsStore((state) => state.addConflict)
  const setFixResult = useT2RSrtStore((state) => state.setFixResult)
  const addLog = useRunbookStore((state) => state.addLog)
  const setCurrentStage = useRunbookStore((state) => state.setCurrentStage)
  const setProgress = useRunbookStore((state) => state.setProgress)

  useEffect(() => {
    statusClientRef.current = new WSClient({
      url: `${WS_URL}/ws/status`,
      onMessage: (message: WSMessage) => {
        // Handle T2R-specific events
        if (message.type === 'status_update' && message.data) {
          // Handle regular status updates
          return
        }
        
        if (message.type === 'event' && message.data) {
          const eventType = message.data.type || message.data.get?.('type')
          
          const data = message.data.data || message.data
          
          // T2R scan progress
          if (eventType === 't2r_scan_progress') {
            if (data.locked_count !== undefined) {
              useT2RScheduleStore.getState().setLockedCount(data.locked_count)
            }
            if (data.conflicts) {
              useT2RScheduleStore.getState().setConflicts(data.conflicts)
            }
          }
          
          // T2R fix applied
          if (eventType === 't2r_fix_applied') {
            if (data.srt_fix) {
              setFixResult(data.srt_fix)
            }
          }
          
          // Runbook stage update
          if (eventType === 'runbook_stage_update') {
            setCurrentStage(data.stage)
            setProgress(data.progress || 0)
            addLog({
              timestamp: data.timestamp || new Date().toISOString(),
              stage: data.stage,
              message: data.message || '',
              level: data.level || 'info',
            })
          }
          
          // Upload progress
          if (eventType === 'upload_progress') {
            addLog({
              timestamp: data.timestamp || new Date().toISOString(),
              stage: 'upload',
              message: `Upload progress: ${data.progress}%`,
              level: 'info',
            })
            setProgress(data.progress || 0)
          }
          
          // Verify result
          if (eventType === 'verify_result') {
            addLog({
              timestamp: data.timestamp || new Date().toISOString(),
              stage: 'verify',
              message: data.message || 'Verification completed',
              level: data.all_passed ? 'info' : 'warning',
            })
          }
        }
      },
      onError: (error) => {
        console.error('T2R WebSocket error:', error)
      },
      onOpen: () => {
        console.log('✅ T2R WebSocket connected')
      },
      onClose: () => {
        console.log('👋 T2R WebSocket disconnected')
      },
    })

    statusClientRef.current.connect()

    return () => {
      statusClientRef.current?.disconnect()
    }
  }, [updateEpisode, addConflict, setFixResult, addLog, setCurrentStage, setProgress])

  return {
    client: statusClientRef.current,
  }
}

