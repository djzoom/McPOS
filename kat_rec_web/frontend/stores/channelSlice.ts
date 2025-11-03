/**
 * Channel Store (Zustand)
 * 
 * Manages channel state with real-time WebSocket updates.
 */
import { create } from 'zustand'
import type { Channel } from '@/components/ChannelWorkbench/types'

interface ChannelState {
  channels: Channel[]
  setChannels: (channels: Channel[]) => void
  updateChannel: (channelId: string, updates: Partial<Channel>) => void
  updateChannelStatus: (channelId: string, status: string, progress?: number) => void
}

export const useChannelStore = create<ChannelState>((set) => ({
  channels: [],
  
  setChannels: (channels) => set({ channels }),
  
  updateChannel: (channelId, updates) =>
    set((state) => ({
      channels: state.channels.map((ch) =>
        ch.id === channelId ? { ...ch, ...updates } : ch
      ),
    })),
  
  updateChannelStatus: (channelId, status, progress) =>
    set((state) => ({
      channels: state.channels.map((ch) =>
        ch.id === channelId
          ? {
              ...ch,
              currentTask: {
                ...ch.currentTask,
                status,
                progress: progress ?? ch.currentTask?.progress,
              },
            }
          : ch
      ),
    })),
}))

