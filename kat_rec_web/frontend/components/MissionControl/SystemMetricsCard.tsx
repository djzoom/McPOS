'use client'

import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Activity, Cpu, HardDrive, Wifi } from 'lucide-react'

async function fetchSystemMetrics() {
  const res = await fetch('http://localhost:8000/metrics/system')
  if (!res.ok) throw new Error('Failed to fetch system metrics')
  return res.json()
}

async function fetchWSHealth() {
  const res = await fetch('http://localhost:8000/metrics/ws-health')
  if (!res.ok) throw new Error('Failed to fetch WS health')
  return res.json()
}

export function SystemMetricsCard() {
  const { data: systemMetrics, isLoading: loadingSystem } = useQuery({
    queryKey: ['system-metrics'],
    queryFn: fetchSystemMetrics,
    refetchInterval: 5000, // Refresh every 5s
  })

  const { data: wsHealth, isLoading: loadingWS } = useQuery({
    queryKey: ['ws-health'],
    queryFn: fetchWSHealth,
    refetchInterval: 5000,
  })

  if (loadingSystem || loadingWS) {
    return (
      <div className="card p-4">
        <div className="animate-pulse">加载中...</div>
      </div>
    )
  }

  return (
    <div className="card p-4">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Activity className="w-5 h-5 text-blue-400" />
        系统指标
      </h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <motion.div
          className="flex items-center gap-2"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
        >
          <Cpu className="w-6 h-6 text-purple-400" />
          <div>
            <div className="text-sm text-dark-text-muted">CPU</div>
            <div className="text-xl font-bold">
              {systemMetrics?.cpu_percent?.toFixed(1) || '0.0'}%
            </div>
          </div>
        </motion.div>

        <motion.div
          className="flex items-center gap-2"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1 }}
        >
          <HardDrive className="w-6 h-6 text-green-400" />
          <div>
            <div className="text-sm text-dark-text-muted">内存</div>
            <div className="text-xl font-bold">
              {systemMetrics?.memory_mb?.toFixed(0) || '0'} MB
            </div>
          </div>
        </motion.div>

        <motion.div
          className="flex items-center gap-2"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
        >
          <Wifi className="w-6 h-6 text-blue-400" />
          <div>
            <div className="text-sm text-dark-text-muted">WS 连接</div>
            <div className="text-xl font-bold">
              {wsHealth?.active_connections || 0}
            </div>
          </div>
        </motion.div>

        <motion.div
          className="flex items-center gap-2"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 }}
        >
          <Activity className="w-6 h-6 text-yellow-400" />
          <div>
            <div className="text-sm text-dark-text-muted">运行时间</div>
            <div className="text-xl font-bold">
              {systemMetrics?.uptime_sec
                ? `${Math.floor(systemMetrics.uptime_sec / 60)}m`
                : '0m'}
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

