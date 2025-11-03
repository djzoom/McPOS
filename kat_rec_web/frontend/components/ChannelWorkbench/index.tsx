'use client'

import { useState, useMemo, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Virtuoso } from 'react-virtuoso'
import { ChannelCard } from './ChannelCard'
import { ViewControls } from './ViewControls'
import { fetchChannels, type Channel as ApiChannel } from '@/services/api'
import { useChannelStore } from '@/stores/channelSlice'
import type { ViewMode, DensityMode } from './types'

// Use Channel type from API service
type Channel = ApiChannel

export function ChannelWorkbench() {
  const [viewMode, setViewMode] = useState<ViewMode>('card')
  const [density, setDensity] = useState<DensityMode>('comfortable')
  const [searchQuery, setSearchQuery] = useState('')

  const { data: fetchedChannels = [], isLoading, error } = useQuery<Channel[]>({
    queryKey: ['channels'],
    queryFn: fetchChannels,
    staleTime: 30 * 1000,
  })

  // Sync fetched data to Zustand store
  const { channels, setChannels } = useChannelStore()
  useEffect(() => {
    if (fetchedChannels.length > 0) {
      // Merge with existing channels to preserve WebSocket updates
      setChannels(fetchedChannels)
    }
  }, [fetchedChannels, setChannels])

  // Use channels from store (includes real-time updates)
  const displayChannels = channels.length > 0 ? channels : fetchedChannels

  const filteredChannels = useMemo(() => {
    if (!searchQuery) return displayChannels
    const query = searchQuery.toLowerCase()
    return displayChannels.filter(
      (ch) =>
        ch.name.toLowerCase().includes(query) || ch.id.toLowerCase().includes(query)
    )
  }, [displayChannels, searchQuery])

  const shouldVirtualize = filteredChannels.length > 20

  if (isLoading) {
    return (
      <div className="card text-center py-8">
        <div className="text-dark-text-muted">加载中...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card text-center py-8">
        <div className="text-red-400">加载失败，请稍后重试</div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <ViewControls
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        density={density}
        onDensityChange={setDensity}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      {viewMode === 'card' ? (
        shouldVirtualize ? (
          <div style={{ height: '600px' }}>
            <Virtuoso
              data={filteredChannels}
              itemContent={(index, channel) => (
                <div className="mb-4">
                  <ChannelCard key={channel.id} channel={channel} density={density} />
                </div>
              )}
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredChannels.map((channel) => (
              <ChannelCard key={channel.id} channel={channel} density={density} />
            ))}
          </div>
        )
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-dark-tertiary">
                <tr>
                  <th className="text-left py-2 px-4 text-sm font-semibold">ID</th>
                  <th className="text-left py-2 px-4 text-sm font-semibold">名称</th>
                  <th className="text-left py-2 px-4 text-sm font-semibold">状态</th>
                  <th className="text-left py-2 px-4 text-sm font-semibold">下次发片</th>
                  <th className="text-left py-2 px-4 text-sm font-semibold">队列</th>
                </tr>
              </thead>
              <tbody>
                {filteredChannels.map((channel) => (
                  <tr
                    key={channel.id}
                    className="border-b border-dark-border hover:bg-dark-tertiary cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4 text-sm font-mono">{channel.id}</td>
                    <td className="py-3 px-4 text-sm">{channel.name}</td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          channel.isActive
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-gray-500/20 text-gray-400'
                        }`}
                      >
                        {channel.isActive ? '运行中' : '已停止'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-sm text-dark-text-muted">
                      {channel.nextSchedule
                        ? new Date(channel.nextSchedule).toLocaleString('zh-CN')
                        : '-'}
                    </td>
                    <td className="py-3 px-4 text-sm text-dark-text-muted">
                      {channel.queueCount ?? 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredChannels.length === 0 && (
              <div className="text-center py-8 text-dark-text-muted">
                没有找到匹配的频道
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

