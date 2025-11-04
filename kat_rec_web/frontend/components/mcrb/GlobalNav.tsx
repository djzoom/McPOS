'use client'

import { useRouter, usePathname } from 'next/navigation'
import { useScheduleStore } from '@/stores/scheduleStore'
import { useScheduleWindow, type WindowSize } from '@/hooks/useScheduleWindow'
import { Calendar, ArrowLeft, LayoutGrid } from 'lucide-react'

export function GlobalNav() {
  const router = useRouter()
  const pathname = usePathname()
  const channels = useScheduleStore((state) => state.channels)
  const selectedChannel = useScheduleStore((state) => state.selectedChannel)
  const setSelectedChannel = useScheduleStore((state) => state.setSelectedChannel)
  const { days, setWindow } = useScheduleWindow()
  
  const isOverview = pathname === '/mcrb/overview'
  const isChannel = pathname?.startsWith('/mcrb/channel/')
  
  const handleBack = () => {
    if (isChannel) {
      router.push('/mcrb/overview')
    }
  }
  
  const handleWindowChange = (windowSize: WindowSize) => {
    setWindow(windowSize)
  }
  
  return (
    <nav className="border-b border-dark-border bg-dark-bg-secondary">
      <div className="max-w-[1920px] mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Left: Navigation */}
          <div className="flex items-center gap-4">
            {isChannel && (
              <button
                onClick={handleBack}
                className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-dark-bg-tertiary transition-colors text-dark-text-muted hover:text-dark-text"
                aria-label="返回总览"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="text-sm font-medium">返回</span>
              </button>
            )}
            
            <button
              onClick={() => router.push('/mcrb/overview')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                isOverview
                  ? 'bg-primary/20 text-primary border border-primary/30'
                  : 'hover:bg-dark-bg-tertiary text-dark-text-muted hover:text-dark-text'
              }`}
            >
              <LayoutGrid className="w-4 h-4" />
              <span className="text-sm font-medium">总览</span>
            </button>
            
            {/* Channel selector */}
            {channels.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-dark-text-muted">频道:</span>
                <select
                  value={selectedChannel || channels[0]}
                  onChange={(e) => {
                    const channelId = e.target.value
                    setSelectedChannel(channelId)
                    if (isChannel && pathname !== `/mcrb/channel/${channelId}`) {
                      router.push(`/mcrb/channel/${channelId}`)
                    }
                  }}
                  className="px-3 py-1.5 rounded-lg bg-dark-bg-tertiary border border-dark-border text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  {channels.map((channelId) => (
                    <option key={channelId} value={channelId}>
                      {channelId}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          
          {/* Right: Window size selector */}
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-dark-text-muted" />
            <span className="text-sm text-dark-text-muted">窗口:</span>
            <div className="flex gap-1">
              {([7, 14, 30] as WindowSize[]).map((windowSize) => (
                <button
                  key={windowSize}
                  onClick={() => handleWindowChange(windowSize)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    days === windowSize
                      ? 'bg-primary text-white'
                      : 'bg-dark-bg-tertiary text-dark-text-muted hover:bg-dark-border hover:text-dark-text'
                  }`}
                >
                  {windowSize}天
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </nav>
  )
}
