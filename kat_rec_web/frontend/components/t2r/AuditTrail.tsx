'use client'

import { useState } from 'react'
import { Download, FileText } from 'lucide-react'

export function AuditTrail() {
  const [reportType, setReportType] = useState<'daily' | 'weekly' | 'custom'>('daily')
  const [format, setFormat] = useState<'json' | 'csv' | 'markdown'>('json')

  return (
    <div className="space-y-6">
      <div className="card p-4">
        <h2 className="text-xl font-semibold mb-4">审计报告</h2>
        
        {/* Report Options */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium mb-2">报告类型</label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value as any)}
              className="w-full px-3 py-2 bg-dark-bg-secondary border border-dark-border rounded text-dark-text-primary"
            >
              <option value="daily">日报</option>
              <option value="weekly">周报</option>
              <option value="custom">自定义</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">导出格式</label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value as any)}
              className="w-full px-3 py-2 bg-dark-bg-secondary border border-dark-border rounded text-dark-text-primary"
            >
              <option value="json">JSON</option>
              <option value="csv">CSV</option>
              <option value="markdown">Markdown</option>
            </select>
          </div>
        </div>

        {/* Generate Button */}
        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors">
            <FileText className="w-4 h-4" />
            生成报告
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 transition-colors">
            <Download className="w-4 h-4" />
            导出
          </button>
        </div>
      </div>
    </div>
  )
}

