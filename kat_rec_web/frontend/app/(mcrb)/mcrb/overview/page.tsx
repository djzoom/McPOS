'use client'

import { useRouter } from 'next/navigation'
import { useScheduleStore } from '@/stores/scheduleStore'
import { OverviewGrid } from '@/components/mcrb/OverviewGrid'
import { StatusLegend } from '@/components/mcrb/StatusLegend'
import { useScheduleWindow } from '@/hooks/useScheduleWindow'

export default function OverviewPage() {
  const router = useRouter()
  const channels = useScheduleStore((state) => state.channels)
  const visibleEvents = useScheduleStore((state) => state.visibleEvents())
  const statusCounts = useScheduleStore((state) => state.statusCounts())
  const { dateRange } = useScheduleWindow()
  
  const handleCellClick = (channelId: string, date: string) => {
    router.push(`/mcrb/channel/${channelId}?focus=${date}`)
  }
  
  const isEmpty = channels.length === 0 || visibleEvents.length === 0
  
  return (
    <div className="max-w-[1920px] mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">排播总览</h1>
        <p className="text-dark-text-muted">
          {dateRange.from} 至 {dateRange.to}
        </p>
      </div>
      
      {/* Status Summary */}
      <div className="mb-6">
        <StatusLegend counts={statusCounts} />
      </div>
      
      {/* Grid */}
      <div className="bg-dark-bg-secondary rounded-xl border border-dark-border overflow-hidden">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="text-6xl mb-4 opacity-50">📅</div>
            <h2 className="text-xl font-semibold mb-2 text-dark-text-muted">
              暂无排播数据
            </h2>
            <p className="text-sm text-dark-text-muted">
              等待数据加载或创建新的排播计划
            </p>
          </div>
        ) : (
          <OverviewGrid
            channels={channels}
            dateRange={dateRange}
            events={visibleEvents}
            onCellClick={handleCellClick}
          />
        )}
      </div>
    </div>
  )
}
