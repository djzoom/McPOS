'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Play, Pause, RotateCw, Loader2 } from 'lucide-react'
import { controlTask } from '@/services/api'
import { useChannelStore } from '@/stores/channelSlice'
import type { Channel } from './types'

interface ChannelCardProps {
  channel: Channel
  density?: 'comfortable' | 'standard' | 'compact'
  onSelect?: (channel: Channel) => void
}

export function ChannelCard({ channel, density = 'comfortable', onSelect }: ChannelCardProps) {
  const [isLoading, setIsLoading] = useState(false)
  const updateChannelStatus = useChannelStore((state) => state.updateChannelStatus)

  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'processing':
        return 'bg-blue-500'
      case 'uploading':
        return 'bg-green-500'
      case 'failed':
        return 'bg-red-500'
      default:
        return 'bg-gray-500'
    }
  }

  const getDensityClass = () => {
    switch (density) {
      case 'compact':
        return 'p-3'
      case 'standard':
        return 'p-4'
      default:
        return 'p-6'
    }
  }

  const handleControl = async (action: 'start' | 'pause' | 'retry') => {
    if (isLoading) return

    setIsLoading(true)
    try {
      const response = await controlTask({
        channel_id: channel.id,
        action,
      })

      // Update channel status optimistically
      const newStatus = action === 'start' ? 'processing' : action === 'pause' ? 'paused' : 'processing'
      updateChannelStatus(channel.id, newStatus)

      console.log('Task control success:', response.message)
    } catch (error) {
      console.error('Task control failed:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const canStart = !channel.currentTask?.status || ['completed', 'failed', 'paused'].includes(channel.currentTask.status)
  const canPause = channel.currentTask?.status === 'processing' || channel.currentTask?.status === 'uploading'
  const canRetry = channel.currentTask?.status === 'failed'

  return (
    <motion.div
      className={`card hover:border-primary transition-all ${getDensityClass()}`}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 
          className={`font-semibold cursor-pointer ${density === 'compact' ? 'text-sm' : 'text-lg'}`}
          onClick={() => onSelect?.(channel)}
        >
          {channel.name}
        </h3>
        <div className={`w-3 h-3 rounded-full ${getStatusColor(channel.currentTask?.status)}`} />
      </div>

      {channel.description && density !== 'compact' && (
        <p className="text-sm text-dark-text-muted mb-2">{channel.description}</p>
      )}

      <div className={`flex items-center gap-4 mb-3 ${density === 'compact' ? 'text-xs' : 'text-sm'}`}>
        {channel.nextSchedule && (
          <span className="text-dark-text-muted">
            下次: {new Date(channel.nextSchedule).toLocaleString('zh-CN')}
          </span>
        )}
        {channel.queueCount !== undefined && (
          <span className="text-dark-text-muted">队列: {channel.queueCount}</span>
        )}
      </div>

      {/* Control Buttons */}
      <div className="flex items-center gap-2 pt-2 border-t border-dark-border" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={() => handleControl('start')}
          disabled={!canStart || isLoading}
          className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-500/20 text-blue-400 rounded hover:bg-blue-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          title="Start"
        >
          {isLoading ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <Play className="w-3 h-3" />
          )}
          <span>Start</span>
        </button>
        <button
          onClick={() => handleControl('pause')}
          disabled={!canPause || isLoading}
          className="flex items-center gap-1 px-2 py-1 text-xs bg-yellow-500/20 text-yellow-400 rounded hover:bg-yellow-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          title="Pause"
        >
          <Pause className="w-3 h-3" />
          <span>Pause</span>
        </button>
        <button
          onClick={() => handleControl('retry')}
          disabled={!canRetry || isLoading}
          className="flex items-center gap-1 px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded hover:bg-green-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          title="Retry"
        >
          <RotateCw className="w-3 h-3" />
          <span>Retry</span>
        </button>
      </div>
    </motion.div>
  )
}

