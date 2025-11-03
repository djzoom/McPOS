'use client'

import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { HealthMetrics } from './HealthMetrics'
import { QueueStatus } from './QueueStatus'
import { TrendChart } from './TrendChart'
import { fetchSummary, fetchEpisodes, type Episode as ApiEpisode, type SummaryData } from '@/services/api'
import type { Episode } from './types'

function calculateSuccessRate(episodes: Episode[]): number {
  const completed = episodes.filter((ep) => ep.status === 'completed').length
  const failed = episodes.filter((ep) => ep.status === 'error').length
  const total = completed + failed

  if (total === 0) return 0
  return (completed / total) * 100
}

// 使用固定种子生成趋势数据，避免 hydration 错误
function generateTrendData(days: number = 7): Array<{ date: string; value: number }> {
  const data = []
  const now = new Date()
  // 使用日期作为种子，确保每次同一天生成相同的数据
  const seed = Math.floor(now.getTime() / (1000 * 60 * 60 * 24)) // 每天的种子

  // 简单的伪随机数生成器（基于种子）
  function seededRandom(seed: number, index: number): number {
    const x = Math.sin((seed + index) * 12.9898) * 43758.5453
    return x - Math.floor(x)
  }

  for (let i = days - 1; i >= 0; i--) {
    const date = new Date(now)
    date.setDate(date.getDate() - i)
    const value = 80 + seededRandom(seed, i) * 20 // 80-100之间的值
    data.push({
      date: date.toISOString(),
      value: Math.round(value * 10) / 10, // 保留一位小数
    })
  }

  return data
}

export function MissionControl() {
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['summary'],
    queryFn: () => fetchSummary('24h'),
    staleTime: 30 * 1000,
  })

  const { data: episodesData, isLoading: episodesLoading } = useQuery({
    queryKey: ['episodes'],
    queryFn: () => fetchEpisodes(),
    staleTime: 30 * 1000,
  })

  // 使用 useMemo 和 useState 确保趋势数据在客户端和服务器端一致
  // 使用固定种子确保同一天生成相同的数据，避免 hydration 错误
  const trendData = useMemo(() => generateTrendData(7), [])

  if (summaryLoading || episodesLoading) {
    return (
      <div className="card text-center py-8">
        <div className="text-dark-text-muted">加载中...</div>
      </div>
    )
  }

  // Convert API episodes to component Episode type
  const episodes: Episode[] = (episodesData?.episodes || []).map((ep: ApiEpisode): Episode => ({
    episode_id: ep.episode_id,
    episode_number: ep.episode_number ?? 0,
    schedule_date: ep.schedule_date ?? '',
    status: ep.status,
    title: undefined,
    image_path: undefined,
    tracks_used: undefined,
    starting_track: undefined,
    youtube_video_id: undefined,
    metadata_updated_at: undefined,
  }))
  
  const successRate = calculateSuccessRate(episodes)
  const failedCount = episodes.filter((ep) => ep.status === 'error').length

  // 找到下一个待制作的期数
  const nextEpisode = episodes.find((ep) => ep.status === 'pending' || ep.status === 'remixing')

  const queueCurrent = summary?.global_state?.total_episodes || 0
  const queueTotal = 50 // 假设最大队列容量
  const queueCapacity = (queueCurrent / queueTotal) * 100

  const handleRetry = () => {
    // TODO: 实现批量重试逻辑
    console.log('批量重试失败任务')
  }

  return (
    <div className="space-y-6">
      {/* 健康指标 */}
      <HealthMetrics
        successRate={successRate}
        failedCount={failedCount}
        nextSchedule={nextEpisode?.schedule_date}
        onRetry={handleRetry}
      />

      {/* 队列状态 */}
      <QueueStatus
        current={queueCurrent}
        total={queueTotal}
        capacityPercent={queueCapacity}
        estimatedTime="4h 32m"
      />

      {/* 趋势图 */}
      <TrendChart data={trendData} title="7日成功率趋势" />
    </div>
  )
}

