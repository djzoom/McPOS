/**
 * T2R SRT Store (Zustand)
 * 
 * Manages subtitle inspection and fix state.
 */
import { create } from 'zustand'

export interface SRTIssue {
  type: 'overlap' | 'gap' | 'encoding'
  line1?: number
  line2?: number
  start?: string
  end?: string
  gap_duration?: string
  severity: 'info' | 'warning' | 'error'
}

export interface SRTFixResult {
  fixed: boolean
  diff?: string
  output_path?: string
  changes?: Array<{
    line: number
    action: string
    old: string
    new: string
  }>
}

interface T2RSrtState {
  currentEpisode: string | null
  issues: SRTIssue[]
  fixResult: SRTFixResult | null
  isLoading: boolean
  
  setCurrentEpisode: (episodeId: string | null) => void
  setIssues: (issues: SRTIssue[]) => void
  setFixResult: (result: SRTFixResult | null) => void
  setLoading: (loading: boolean) => void
}

export const useT2RSrtStore = create<T2RSrtState>((set) => ({
  currentEpisode: null,
  issues: [],
  fixResult: null,
  isLoading: false,
  
  setCurrentEpisode: (currentEpisode) => set({ currentEpisode }),
  
  setIssues: (issues) => set({ issues }),
  
  setFixResult: (fixResult) => set({ fixResult }),
  
  setLoading: (isLoading) => set({ isLoading }),
}))

