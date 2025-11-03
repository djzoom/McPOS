'use client'

import { motion } from 'framer-motion'

interface QueueStatusProps {
  current: number
  total: number
  capacityPercent: number
  estimatedTime?: string
}

export function QueueStatus({ current, total, capacityPercent, estimatedTime }: QueueStatusProps) {
  const getCapacityColor = () => {
    if (capacityPercent >= 90) return 'bg-red-500'
    if (capacityPercent >= 70) return 'bg-yellow-500'
    return 'bg-green-500'
  }

  return (
    <motion.div
      className="card"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
    >
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm text-dark-text-muted">队列状态</span>
        <span className="text-sm font-semibold">
          {current} / {total}
        </span>
      </div>

      {/* 进度条 */}
      <div className="w-full h-2 bg-dark-tertiary rounded-full overflow-hidden mb-2">
        <motion.div
          className={`h-full ${getCapacityColor()}`}
          initial={{ width: 0 }}
          animate={{ width: `${capacityPercent}%` }}
          transition={{ duration: 0.5 }}
        />
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-dark-text-muted">容量: {capacityPercent.toFixed(0)}%</span>
        {estimatedTime && (
          <span className="text-dark-text-muted">预计: {estimatedTime}</span>
        )}
      </div>

      <div className="mt-4 flex gap-2">
        <button className="text-xs px-3 py-1 bg-dark-tertiary hover:bg-dark-border rounded transition-colors">
          批量操作
        </button>
        <button className="text-xs px-3 py-1 bg-dark-tertiary hover:bg-dark-border rounded transition-colors">
          错峰调度
        </button>
        <button className="text-xs px-3 py-1 bg-dark-tertiary hover:bg-dark-border rounded transition-colors">
          调优先级
        </button>
      </div>
    </motion.div>
  )
}

