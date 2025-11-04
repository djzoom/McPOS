/**
 * Schedule Window Hook
 * 
 * Manages date range window (7/14/30 days) for schedule views.
 */
import { useCallback } from 'react'
import { useScheduleStore } from '@/stores/scheduleStore'

export type WindowSize = 7 | 14 | 30

/**
 * Hook to manage schedule date window
 */
export function useScheduleWindow() {
  const dateRange = useScheduleStore((state) => state.dateRange)
  const setDateRange = useScheduleStore((state) => state.setDateRange)
  
  const setWindow = useCallback(
    (days: WindowSize) => {
      setDateRange({ days })
    },
    [setDateRange]
  )
  
  return {
    dateRange,
    setWindow,
    days: Math.ceil(
      (new Date(dateRange.to).getTime() - new Date(dateRange.from).getTime()) /
        (1000 * 60 * 60 * 24)
    ) + 1,
  }
}
