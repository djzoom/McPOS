export interface Channel {
  id: string
  name: string
  description?: string
  isActive: boolean
  currentTask?: {
    id: string
    status: 'pending' | 'processing' | 'uploading' | 'completed' | 'failed'
    progress?: number
  }
  nextSchedule?: string
  queueCount?: number
  lastUpdate?: string
}

export type ViewMode = 'card' | 'table'
export type DensityMode = 'comfortable' | 'standard' | 'compact'

