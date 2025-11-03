export interface Episode {
  episode_id: string
  episode_number: number
  schedule_date: string
  title?: string
  status: 'pending' | 'remixing' | 'rendering' | 'uploading' | 'completed' | 'error'
  image_path?: string
  tracks_used?: string[]
  starting_track?: string
  youtube_video_id?: string
  metadata_updated_at?: string
}

export interface SummaryData {
  global_state?: {
    total_episodes: number
    completed: number
    error: number
    remixing: number
    rendering: number
    pending: number
  }
  stages?: {
    [key: string]: {
      avg_duration: number
      count: number
    }
  }
  period?: string
}

