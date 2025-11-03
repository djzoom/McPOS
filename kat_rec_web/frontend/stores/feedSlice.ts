/**
 * System Feed Store (Zustand)
 * 
 * Manages system event feed for real-time activity logging.
 */
import { create } from 'zustand'

export interface FeedEvent {
  id: string
  timestamp: string
  level: 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS'
  message: string
  channel_id?: string
  stage?: string
}

interface FeedState {
  events: FeedEvent[]
  maxEvents: number
  isMuted: boolean
  addEvent: (event: Omit<FeedEvent, 'id'>) => void
  clearEvents: () => void
  toggleMute: () => void
}

export const useFeedStore = create<FeedState>((set, get) => ({
  events: [],
  maxEvents: 100,
  isMuted: false,
  
  addEvent: (event) => {
    const newEvent: FeedEvent = {
      ...event,
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    }
    
    set((state) => {
      const events = [newEvent, ...state.events].slice(0, state.maxEvents)
      return { events }
    })
  },
  
  clearEvents: () => set({ events: [] }),
  
  toggleMute: () => set((state) => ({ isMuted: !state.isMuted })),
}))

