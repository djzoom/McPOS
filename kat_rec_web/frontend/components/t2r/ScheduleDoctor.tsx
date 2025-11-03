'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Search, Filter, Lock, Unlock } from 'lucide-react'

export function ScheduleDoctor() {
  const [searchQuery, setSearchQuery] = useState('')

  return (
    <div className="space-y-6">
      <div className="card p-4">
        <h2 className="text-xl font-semibold mb-4">排播异常扫描</h2>
        
        {/* Search and Filters */}
        <div className="flex gap-4 mb-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-dark-text-muted" />
            <input
              type="text"
              placeholder="搜索期数..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-dark-bg-secondary border border-dark-border rounded text-dark-text-primary"
            />
          </div>
          <button className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors">
            一键锁定
          </button>
        </div>

        {/* Schedule Table */}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-dark-bg-tertiary">
              <tr>
                <th className="text-left py-2 px-4 text-sm font-semibold">期数 ID</th>
                <th className="text-left py-2 px-4 text-sm font-semibold">排播日期</th>
                <th className="text-left py-2 px-4 text-sm font-semibold">状态</th>
                <th className="text-left py-2 px-4 text-sm font-semibold">操作</th>
              </tr>
            </thead>
            <tbody>
              {/* Placeholder rows */}
              {[1, 2, 3].map((i) => (
                <tr key={i} className="border-b border-dark-border hover:bg-dark-bg-tertiary">
                  <td className="py-3 px-4 text-sm font-mono">2025110{i}</td>
                  <td className="py-3 px-4 text-sm">2025-11-0{i}</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-1 rounded text-xs bg-yellow-500/20 text-yellow-400">
                      待制作
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <button className="p-1.5 rounded hover:bg-dark-bg-secondary transition-colors">
                      <Lock className="w-4 h-4 text-dark-text-muted" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

