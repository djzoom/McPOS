'use client'

import { type ScheduleEventStatus, statusColors } from '@/lib/designTokens'
import { type ScheduleStore } from '@/stores/scheduleStore'

type StatusCounts = ReturnType<ScheduleStore['statusCounts']>

interface StatusLegendProps {
  counts: StatusCounts
}

export function StatusLegend({ counts }: StatusLegendProps) {
  const statusLabels: Record<ScheduleEventStatus, string> = {
    draft: '草稿',
    planned: '已计划',
    rendering: '渲染中',
    ready: '就绪',
    uploaded: '已上传',
    verified: '已验证',
    failed: '失败',
  }
  
  const total = Object.values(counts).reduce((sum, count) => sum + count, 0)
  
  if (total === 0) {
    return null
  }
  
  return (
    <div className="flex flex-wrap items-center gap-4">
      <span className="text-sm font-medium text-dark-text-muted">状态分布:</span>
      {Object.entries(counts).map(([status, count]) => {
        if (count === 0) return null
        
        const color = statusColors[status as ScheduleEventStatus]
        return (
          <div
            key={status}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-dark-bg-tertiary border border-dark-border"
          >
            <div
              className="w-3 h-3 rounded-full"
              style={{
                backgroundColor: color.base,
                opacity: color.opacity.bg,
              }}
            />
            <span className="text-sm text-dark-text">
              {statusLabels[status as ScheduleEventStatus]}
            </span>
            <span className="text-sm font-semibold text-dark-text-muted">
              {count}
            </span>
          </div>
        )
      })}
      <div className="ml-auto text-sm text-dark-text-muted">
        总计: <span className="font-semibold text-dark-text">{total}</span>
      </div>
    </div>
  )
}
