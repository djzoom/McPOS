'use client'

import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { scanSchedule } from '@/services/t2rApi'
import { useT2RScheduleStore } from '@/stores/t2rScheduleStore'
import { useT2RAssetsStore } from '@/stores/t2rAssetsStore'
import { motion } from 'framer-motion'
import { Lock, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react'

export function ChannelOverview() {
  const { lockedCount, conflicts, setLockedCount, setConflicts, setLoading } = useT2RScheduleStore()
  const { assetUsage } = useT2RAssetsStore()
  const [totalEpisodes, setTotalEpisodes] = useState(0)
  const [duplicateImages, setDuplicateImages] = useState(0)

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['t2r-scan'],
    queryFn: () => scanSchedule(),
    enabled: false, // Manual trigger
  })

  useEffect(() => {
    if (data?.status === 'ok') {
      setLockedCount(data.summary?.locked_count || data.data?.locked_count || 0)
      // Convert API conflicts to store conflicts format
      const apiConflicts = data.summary?.conflicts || data.data?.conflicts || []
      const storeConflicts = apiConflicts.map((c: any) => ({
        type: c.type || 'unknown',
        asset: c.asset || '',
        episodes: c.episodes || [],
        severity: 'warning' as const, // Default severity
      }))
      setConflicts(storeConflicts)
      // Update asset usage from scan result
      if (data.summary?.asset_usage) {
        const assetUsageData = {
          images: data.summary.asset_usage.images || {},
          songs: data.summary.asset_usage.songs || {},
          episodes: data.summary.asset_usage.episodes || {},
        }
        useT2RAssetsStore.getState().setAssetUsage(assetUsageData)
        // Extract metadata
        setTotalEpisodes(data.summary.asset_usage.total_episodes || 0)
        setDuplicateImages(data.summary.asset_usage.duplicate_images || 0)
      }
    }
  }, [data, setLockedCount, setConflicts])

  const handleScan = () => {
    setLoading(true)
    refetch().finally(() => setLoading(false))
  }

  return (
    <div className="space-y-6">
      {/* Actions */}
      <div className="card p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">频道资源扫描</h2>
          <button
            onClick={handleScan}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            执行扫描
          </button>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <motion.div
          className="card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center gap-3">
            <Lock className="w-8 h-8 text-blue-400" />
            <div>
              <div className="text-2xl font-bold">{lockedCount}</div>
              <div className="text-sm text-dark-text-muted">已锁定</div>
            </div>
          </div>
        </motion.div>

        <motion.div
          className="card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-8 h-8 text-yellow-400" />
            <div>
              <div className="text-2xl font-bold">{conflicts.length}</div>
              <div className="text-sm text-dark-text-muted">冲突检测</div>
            </div>
          </div>
        </motion.div>

        <motion.div
          className="card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <div className="flex items-center gap-3">
            <CheckCircle className="w-8 h-8 text-green-400" />
            <div>
              <div className="text-2xl font-bold">
                {totalEpisodes}
              </div>
              <div className="text-sm text-dark-text-muted">总期数</div>
            </div>
          </div>
        </motion.div>

        <motion.div
          className="card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <div className="flex items-center gap-3">
            <RefreshCw className="w-8 h-8 text-purple-400" />
            <div>
              <div className="text-2xl font-bold">
                {duplicateImages}
              </div>
              <div className="text-sm text-dark-text-muted">重复图片</div>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Conflicts List */}
      {conflicts.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">冲突列表</h3>
          <div className="space-y-2">
            {conflicts.map((conflict, idx) => (
              <div
                key={idx}
                className="p-3 rounded bg-yellow-500/10 border border-yellow-500/20"
              >
                <div className="flex items-center gap-2 mb-1">
                  <AlertTriangle className="w-4 h-4 text-yellow-400" />
                  <span className="font-medium">{conflict.type}</span>
                </div>
                <div className="text-sm text-dark-text-muted">
                  资源: {conflict.asset}
                </div>
                <div className="text-sm text-dark-text-muted">
                  期数: {conflict.episodes.join(', ')}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

