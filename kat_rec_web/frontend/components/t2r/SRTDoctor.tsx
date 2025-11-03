'use client'

import { useState } from 'react'
import { Upload, Check, FileText } from 'lucide-react'
import { useT2RSrtStore } from '@/stores/t2rSrtStore'

export function SRTDoctor() {
  const { issues, fixResult, setIssues, setFixResult } = useT2RSrtStore()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  return (
    <div className="space-y-6">
      <div className="card p-4">
        <h2 className="text-xl font-semibold mb-4">SRT 字幕医生</h2>
        
        {/* File Upload */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">上传字幕文件</label>
          <div className="border-2 border-dashed border-dark-border rounded p-6 text-center">
            <Upload className="w-8 h-8 mx-auto mb-2 text-dark-text-muted" />
            <input
              type="file"
              accept=".srt"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              className="hidden"
              id="srt-upload"
            />
            <label
              htmlFor="srt-upload"
              className="cursor-pointer text-blue-400 hover:text-blue-300"
            >
              选择文件
            </label>
            {selectedFile && (
              <div className="mt-2 text-sm text-dark-text-muted">
                {selectedFile.name}
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2 mb-4">
          <button className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors">
            <Check className="w-4 h-4" />
            检查
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 transition-colors">
            <FileText className="w-4 h-4" />
            修复
          </button>
        </div>

        {/* Issues */}
        {issues.length > 0 && (
          <div className="space-y-2">
            <h3 className="font-semibold">检测到的问题：</h3>
            {issues.map((issue, idx) => (
              <div key={idx} className="p-3 rounded bg-yellow-500/10 border border-yellow-500/20">
                <div className="font-medium">{issue.type}</div>
                {issue.start && (
                  <div className="text-sm text-dark-text-muted">
                    {issue.start} → {issue.end}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Fix Result */}
        {fixResult && (
          <div className="mt-4 p-4 rounded bg-green-500/10 border border-green-500/20">
            <div className="font-medium mb-2">修复结果</div>
            {fixResult.diff && (
              <pre className="text-xs bg-dark-bg-secondary p-2 rounded overflow-x-auto">
                {fixResult.diff}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

