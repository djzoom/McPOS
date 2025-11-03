/**
 * T2R Description Store (Zustand)
 * 
 * Manages description linting and normalization state.
 */
import { create } from 'zustand'

export interface DescFlag {
  type: 'branding_misuse' | 'cc0_missing' | 'seo_weak'
  message: string
}

export interface DescSuggestion {
  type: string
  issue: string
  fix: string
}

interface T2RDescState {
  currentEpisode: string | null
  originalDescription: string
  fixedDescription: string | null
  flags: DescFlag[]
  suggestions: DescSuggestion[]
  isLoading: boolean
  
  setCurrentEpisode: (episodeId: string | null) => void
  setDescription: (description: string) => void
  setFixedDescription: (description: string | null) => void
  setFlags: (flags: DescFlag[]) => void
  setSuggestions: (suggestions: DescSuggestion[]) => void
  setLoading: (loading: boolean) => void
}

export const useT2RDescStore = create<T2RDescState>((set) => ({
  currentEpisode: null,
  originalDescription: '',
  fixedDescription: null,
  flags: [],
  suggestions: [],
  isLoading: false,
  
  setCurrentEpisode: (currentEpisode) => set({ currentEpisode }),
  
  setDescription: (originalDescription) => set({ originalDescription }),
  
  setFixedDescription: (fixedDescription) => set({ fixedDescription }),
  
  setFlags: (flags) => set({ flags }),
  
  setSuggestions: (suggestions) => set({ suggestions }),
  
  setLoading: (isLoading) => set({ isLoading }),
}))

