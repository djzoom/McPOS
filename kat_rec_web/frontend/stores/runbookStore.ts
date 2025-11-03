/**
 * Runbook Store (Zustand)
 * 
 * Manages episode execution stages and logs.
 */
import { create } from 'zustand'

export type RunbookStage = 'idle' | 'planning' | 'remix' | 'render' | 'upload' | 'verify' | 'completed' | 'failed'

export interface RunbookLog {
  timestamp: string
  stage: RunbookStage
  message: string
  level: 'info' | 'warning' | 'error'
}

export interface RunbookState {
  runId: string | null
  episodeId: string | null
  currentStage: RunbookStage
  progress: number
  logs: RunbookLog[]
  stages: string[]
  isRunning: boolean
  
  setRunId: (runId: string | null) => void
  setEpisodeId: (episodeId: string | null) => void
  setCurrentStage: (stage: RunbookStage) => void
  setProgress: (progress: number) => void
  addLog: (log: RunbookLog) => void
  setStages: (stages: string[]) => void
  setIsRunning: (isRunning: boolean) => void
  reset: () => void
}

const initialState = {
  runId: null,
  episodeId: null,
  currentStage: 'idle' as RunbookStage,
  progress: 0,
  logs: [],
  stages: [],
  isRunning: false,
}

export const useRunbookStore = create<RunbookState>((set) => ({
  ...initialState,
  
  setRunId: (runId) => set({ runId }),
  
  setEpisodeId: (episodeId) => set({ episodeId }),
  
  setCurrentStage: (currentStage) => set({ currentStage }),
  
  setProgress: (progress) => set({ progress }),
  
  addLog: (log) =>
    set((state) => ({
      logs: [...state.logs, log].slice(-100), // Keep last 100 logs
    })),
  
  setStages: (stages) => set({ stages }),
  
  setIsRunning: (isRunning) => set({ isRunning }),
  
  reset: () => set(initialState),
}))

