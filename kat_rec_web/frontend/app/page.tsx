'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ChannelCard from '@/components/ChannelCard'
import UploadStatus from '@/components/UploadStatus'
import LibraryTabs from '@/components/LibraryTabs'
import { MissionControl } from '@/components/MissionControl'
import { ChannelWorkbench } from '@/components/ChannelWorkbench'
import { SystemFeed } from '@/components/SystemFeed'
import { useWebSocket } from '@/hooks/useWebSocket'
import { fetchStatus, fetchChannel } from '@/services/api'

export default function Dashboard() {
  const [activeSection, setActiveSection] = useState<'overview' | 'channels' | 'library'>(
    'overview'
  )
  
  // Initialize WebSocket connections
  useWebSocket()

  const { data: status } = useQuery({
    queryKey: ['status'],
    queryFn: fetchStatus,
    staleTime: 30 * 1000,
  })

  const { data: channel } = useQuery({
    queryKey: ['channel'],
    queryFn: () => fetchChannel(),
    staleTime: 30 * 1000,
  })

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold mb-8">Kat Rec Web Control Center</h1>

        {/* 导航标签 */}
        <div className="flex gap-4 mb-6 border-b border-dark-border">
          <button
            onClick={() => setActiveSection('overview')}
            className={`pb-3 px-4 font-semibold transition-colors ${
              activeSection === 'overview'
                ? 'text-white border-b-2 border-blue-500'
                : 'text-dark-text-muted hover:text-dark-text'
            }`}
          >
            总览
          </button>
          <button
            onClick={() => setActiveSection('channels')}
            className={`pb-3 px-4 font-semibold transition-colors ${
              activeSection === 'channels'
                ? 'text-white border-b-2 border-blue-500'
                : 'text-dark-text-muted hover:text-dark-text'
            }`}
          >
            频道工作盘
          </button>
          <button
            onClick={() => setActiveSection('library')}
            className={`pb-3 px-4 font-semibold transition-colors ${
              activeSection === 'library'
                ? 'text-white border-b-2 border-blue-500'
                : 'text-dark-text-muted hover:text-dark-text'
            }`}
          >
            资产库
          </button>
        </div>

        {/* 内容区域 */}
        {activeSection === 'overview' && (
          <div className="space-y-6">
            {/* 状态卡片 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <ChannelCard channel={channel} />
              <UploadStatus status={status} />
            </div>

            {/* Mission Control */}
            <div>
              <h2 className="text-2xl font-semibold mb-4">Mission Control</h2>
              <MissionControl />
            </div>
          </div>
        )}

        {activeSection === 'channels' && (
          <div>
            <h2 className="text-2xl font-semibold mb-4">频道工作盘</h2>
            <ChannelWorkbench />
          </div>
        )}

        {activeSection === 'library' && (
          <div>
            <h2 className="text-2xl font-semibold mb-4">资产库</h2>
            <LibraryTabs />
          </div>
        )}
      </div>

      {/* System Feed */}
      <SystemFeed />
    </main>
  )
}

