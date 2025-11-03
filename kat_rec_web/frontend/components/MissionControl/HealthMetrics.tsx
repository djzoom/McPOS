'use client'

import { motion } from 'framer-motion'
import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface HealthMetricsProps {
  successRate: number
  failedCount: number
  nextSchedule?: string
  onRetry?: () => void
}

function calculateCountdown(targetDate: string): string {
  const now = new Date()
  const target = new Date(targetDate)
  const diff = target.getTime() - now.getTime()

  if (diff <= 0) return '已到期'

  const hours = Math.floor(diff / (1000 * 60 * 60))
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))

  return `${hours}h ${minutes}m`
}

// 格式化时间为 HH:mm，避免使用 toLocaleTimeString 导致的 hydration 错误
function formatTime(dateString: string): string {
  const date = new Date(dateString)
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  return `${hours}:${minutes}`
}

export function HealthMetrics({
  successRate,
  failedCount,
  nextSchedule,
  onRetry,
}: HealthMetricsProps) {
  const trend = successRate > 95 ? 'up' : 'down'
  const [countdown, setCountdown] = useState<string>('')
  const [isMounted, setIsMounted] = useState(false)

  // 只在客户端计算倒计时，避免 hydration 错误
  useEffect(() => {
    setIsMounted(true)
    if (nextSchedule) {
      const updateCountdown = () => {
        setCountdown(calculateCountdown(nextSchedule))
      }
      updateCountdown()
      const interval = setInterval(updateCountdown, 60000) // 每分钟更新
      return () => clearInterval(interval)
    }
  }, [nextSchedule])

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* 成功率卡片 */}
      <motion.div
        className="card"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-dark-text-muted">成功率</span>
          {trend === 'up' ? (
            <TrendingUp className="w-4 h-4 text-green-400" />
          ) : (
            <TrendingDown className="w-4 h-4 text-red-400" />
          )}
        </div>
        <div className="text-3xl font-bold mb-2">{successRate.toFixed(1)}%</div>
        <div className="text-sm text-dark-text-muted">较昨日 ↑ 2.3%</div>
      </motion.div>

      {/* 失败任务卡片 */}
      <motion.div
        className="card"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-dark-text-muted">失败任务</span>
          {failedCount > 0 && (
            <button
              onClick={onRetry}
              className="text-xs px-2 py-1 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors"
            >
              批量重试
            </button>
          )}
        </div>
        <div
          className={`text-3xl font-bold mb-2 ${failedCount > 0 ? 'text-red-400' : 'text-green-400'}`}
        >
          {failedCount}
        </div>
        <div className="text-sm text-dark-text-muted">待处理</div>
      </motion.div>

      {/* 下次发片卡片 */}
      {nextSchedule && isMounted && (
        <motion.div
          className="card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <div className="text-sm text-dark-text-muted mb-2">下次发片</div>
          <div className="text-2xl font-bold mb-2">{formatTime(nextSchedule)}</div>
          <div className="text-sm text-dark-text-muted">{countdown || '计算中...'}</div>
        </motion.div>
      )}
    </div>
  )
}

