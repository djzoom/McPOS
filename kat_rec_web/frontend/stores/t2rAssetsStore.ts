/**
 * T2R Assets Store (Zustand)
 * 
 * Manages asset usage index and conflict detection.
 */
import { create } from 'zustand'

export interface AssetUsage {
  images: Record<string, string[]>
  songs: Record<string, string[]>
  episodes: Record<string, any>
}

export interface AssetConflict {
  type: 'image_reuse' | 'song_reuse' | 'duplicate'
  asset: string
  episodes: string[]
  severity: 'info' | 'warning' | 'error'
}

interface T2RAssetsState {
  assetUsage: AssetUsage | null
  conflicts: AssetConflict[]
  isLoading: boolean
  
  setAssetUsage: (usage: AssetUsage) => void
  setConflicts: (conflicts: AssetConflict[]) => void
  addConflict: (conflict: AssetConflict) => void
  setLoading: (loading: boolean) => void
}

export const useT2RAssetsStore = create<T2RAssetsState>((set) => ({
  assetUsage: null,
  conflicts: [],
  isLoading: false,
  
  setAssetUsage: (assetUsage) => set({ assetUsage }),
  
  setConflicts: (conflicts) => set({ conflicts }),
  
  addConflict: (conflict) =>
    set((state) => ({
      conflicts: [...state.conflicts, conflict],
    })),
  
  setLoading: (isLoading) => set({ isLoading }),
}))

