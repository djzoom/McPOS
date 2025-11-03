'use client'

import { useState } from 'react'
import { CheckCircle, XCircle, Search } from 'lucide-react'
import { verifyUpload } from '@/services/t2rApi'

export function PostUploadVerify() {
  const [videoId, setVideoId] = useState('')
  const [episodeId, setEpisodeId] = useState('')
  const [verifyResult, setVerifyResult] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)

  return (
    <div className="space-y-6">
      <div className="card p-4">
        <h2 className="text-xl font-semibold mb-4">上传后验证</h2>
        
        {/* Episode ID Input */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">期数 ID</label>
          <input
            type="text"
            value={episodeId}
            onChange={(e) => setEpisodeId(e.target.value)}
            placeholder="例如: 20251102"
            className="w-full px-3 py-2 bg-dark-bg-secondary border border-dark-border rounded text-dark-text-primary mb-2"
          />
        </div>

        {/* Video ID Input */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">视频 ID</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={videoId}
              onChange={(e) => setVideoId(e.target.value)}
              placeholder="YouTube video ID"
              className="flex-1 px-3 py-2 bg-dark-bg-secondary border border-dark-border rounded text-dark-text-primary"
            />
            <button
              onClick={async () => {
                if (!episodeId || !videoId) return
                setIsLoading(true)
                try {
                  const result = await verifyUpload({
                    episode_id: episodeId,
                    video_id: videoId,
                    platform: 'youtube',
                  })
                  setVerifyResult(result)
                } catch (error) {
                  console.error('验证失败:', error)
                  setVerifyResult({ error: String(error) })
                } finally {
                  setIsLoading(false)
                }
              }}
              disabled={isLoading || !episodeId || !videoId}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 transition-colors"
            >
              <Search className="w-4 h-4" />
              {isLoading ? '验证中...' : '验证'}
            </button>
          </div>
        </div>

        {/* Verification Results */}
        {verifyResult && (
          <div className="space-y-2">
            <h3 className="font-semibold">验证结果：</h3>
            {verifyResult.checks?.map((check: any, idx: number) => (
              <div
                key={idx}
                className={`p-3 rounded flex items-center gap-2 ${
                  check.status === 'passed'
                    ? 'bg-green-500/10 border border-green-500/20'
                    : 'bg-yellow-500/10 border border-yellow-500/20'
                }`}
              >
                {check.status === 'passed' ? (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                ) : (
                  <XCircle className="w-5 h-5 text-yellow-400" />
                )}
                <div>
                  <div className="font-medium">{check.name}</div>
                  <div className="text-sm text-dark-text-muted">{check.message}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

