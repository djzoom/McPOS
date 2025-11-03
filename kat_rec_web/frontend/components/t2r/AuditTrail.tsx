'use client'

import { useState } from 'react'
import { Download, FileText } from 'lucide-react'
import { getAuditReport } from '@/services/t2rApi'

export function AuditTrail() {
  const [reportType, setReportType] = useState<'daily' | 'weekly' | 'custom'>('daily')
  const [format, setFormat] = useState<'json' | 'csv' | 'markdown'>('json')
  const [report, setReport] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)

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
          <button
            onClick={async () => {
              setIsLoading(true)
              try {
                const result = await getAuditReport({
                  report_type: reportType,
                  format,
                })
                setReport(result)
              } catch (error) {
                console.error('生成报告失败:', error)
                setReport({ error: String(error) })
              } finally {
                setIsLoading(false)
              }
            }}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 transition-colors"
          >
            <FileText className="w-4 h-4" />
            {isLoading ? '生成中...' : '生成报告'}
          </button>
          <button
            onClick={() => {
              if (!report) return
              const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = `audit_${reportType}_${new Date().toISOString().split('T')[0]}.${format}`
              a.click()
            }}
            disabled={!report}
            className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50 transition-colors"
          >
            <Download className="w-4 h-4" />
            导出
          </button>
        </div>

        {/* Report Display */}
        {report && !report.error && (
          <div className="mt-4 p-4 bg-dark-bg-secondary rounded border border-dark-border max-h-96 overflow-y-auto">
            <pre className="text-xs">{JSON.stringify(report, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  )
}

