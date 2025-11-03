'use client'

import { useState } from 'react'
import { Play, FileText, Settings } from 'lucide-react'
import { useRunbookStore } from '@/stores/runbookStore'

export function PlanAndRun() {
  const { currentStage, progress, logs, isRunning } = useRunbookStore()
  const [episodeId, setEpisodeId] = useState('')

  return (
    <div className="space-y-6">
      <div className="card p-4">
        <h2 className="text-xl font-semibold mb-4">计划与执行</h2>
        
        {/* Plan Section */}
        <div className="mb-6">
          <label className="block text-sm font-medium mb-2">期数 ID</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={episodeId}
              onChange={(e) => setEpisodeId(e.target.value)}
              placeholder="例如: 20251102"
              className="flex-1 px-3 py-2 bg-dark-bg-secondary border border-dark-border rounded text-dark-text-primary"
            />
            <button className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors">
              <FileText className="w-4 h-4" />
              生成 Recipe
            </button>
          </div>
        </div>

        {/* Run Section */}
        <div className="border-t border-dark-border pt-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">执行 Runbook</h3>
            <button
              disabled={!episodeId || isRunning}
              className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50 transition-colors"
            >
              <Play className="w-4 h-4" />
              一键执行
            </button>
          </div>

          {/* Progress */}
          {isRunning && (
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-dark-text-muted">当前阶段: {currentStage}</span>
                <span className="text-sm text-dark-text-muted">{Math.round(progress)}%</span>
              </div>
              <div className="w-full bg-dark-bg-secondary rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Logs */}
          {logs.length > 0 && (
            <div className="mt-4 p-3 bg-dark-bg-secondary rounded max-h-60 overflow-y-auto">
              {logs.map((log, idx) => (
                <div key={idx} className="text-xs mb-1">
                  <span className="text-dark-text-muted">{log.timestamp}</span>
                  <span className={`ml-2 ${
                    log.level === 'error' ? 'text-red-400' :
                    log.level === 'warning' ? 'text-yellow-400' :
                    'text-dark-text-secondary'
                  }`}>
                    [{log.level}] {log.message}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

