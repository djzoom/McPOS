/**
 * T2R Schedule Store (Zustand)
 * 
 * Manages schedule master state, locking, and conflict analysis.
 */
import { create } from 'zustand'

export interface ScheduleEpisode {
  episode_id: string
  episode_number: number
  schedule_date: string
  image_path?: string
  status: string
  locked_at?: string
  lock_reason?: string
}

export interface ScheduleConflict {
  type: string
  asset: string
  episodes: string[]
  severity: 'info' | 'warning' | 'error'
}

interface T2RScheduleState {
  schedule: any | null
  episodes: ScheduleEpisode[]
  conflicts: ScheduleConflict[]
  lockedCount: number
  isLoading: boolean
  
  setSchedule: (schedule: any) => void
  setEpisodes: (episodes: ScheduleEpisode[]) => void
  setConflicts: (conflicts: ScheduleConflict[]) => void
  setLockedCount: (count: number) => void
  updateEpisode: (episodeId: string, updates: Partial<ScheduleEpisode>) => void
  setLoading: (loading: boolean) => void
}

export const useT2RScheduleStore = create<T2RScheduleState>((set) => ({
  schedule: null,
  episodes: [],
  conflicts: [],
  lockedCount: 0,
  isLoading: false,
  
  setSchedule: (schedule) => set({ schedule }),
  
  setEpisodes: (episodes) => set({ episodes }),
  
  setConflicts: (conflicts) => set({ conflicts }),
  
  setLockedCount: (lockedCount) => set({ lockedCount }),
  
  updateEpisode: (episodeId, updates) =>
    set((state) => ({
      episodes: state.episodes.map((ep) =>
        ep.episode_id === episodeId ? { ...ep, ...updates } : ep
      ),
    })),
  
  setLoading: (isLoading) => set({ isLoading }),
}))

