'use client'

import { useState } from 'react'
import { FileText, Wand2 } from 'lucide-react'
import { useT2RDescStore } from '@/stores/t2rDescStore'

export function DescriptionLinter() {
  const { flags, suggestions, fixedDescription, setDescription } = useT2RDescStore()
  const [description, setLocalDescription] = useState('')

  return (
    <div className="space-y-6">
      <div className="card p-4">
        <h2 className="text-xl font-semibold mb-4">描述规范化</h2>
        
        {/* Description Input */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">描述内容</label>
          <textarea
            value={description}
            onChange={(e) => {
              setLocalDescription(e.target.value)
              setDescription(e.target.value)
            }}
            rows={10}
            className="w-full p-3 bg-dark-bg-secondary border border-dark-border rounded text-dark-text-primary font-mono text-sm"
            placeholder="输入描述文本..."
          />
        </div>

        {/* Actions */}
        <div className="flex gap-2 mb-4">
          <button className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors">
            <FileText className="w-4 h-4" />
            检查
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 transition-colors">
            <Wand2 className="w-4 h-4" />
            自动修正
          </button>
        </div>

        {/* Flags */}
        {flags.length > 0 && (
          <div className="space-y-2">
            <h3 className="font-semibold">检测到的问题：</h3>
            {flags.map((flag, idx) => (
              <div
                key={idx}
                className={`p-3 rounded border ${
                  flag.type === 'branding_misuse'
                    ? 'bg-red-500/10 border-red-500/20'
                    : flag.type === 'cc0_missing'
                    ? 'bg-yellow-500/10 border-yellow-500/20'
                    : 'bg-blue-500/10 border-blue-500/20'
                }`}
              >
                <div className="font-medium">{flag.type}</div>
                <div className="text-sm text-dark-text-muted">{flag.message}</div>
              </div>
            ))}
          </div>
        )}

        {/* Fixed Description */}
        {fixedDescription && (
          <div className="mt-4">
            <h3 className="font-semibold mb-2">修正后的描述：</h3>
            <div className="p-3 bg-dark-bg-secondary rounded border border-green-500/20">
              <pre className="whitespace-pre-wrap text-sm">{fixedDescription}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

