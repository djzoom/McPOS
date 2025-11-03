'use client'

interface UploadStatusProps {
  status: any
}

export default function UploadStatus({ status }: UploadStatusProps) {
  if (!status) {
    return (
      <div className="card">
        <h2 className="text-xl font-semibold mb-4">Upload Status</h2>
        <div className="text-dark-text-muted">Loading...</div>
      </div>
    )
  }

  const redisConnected = status.redis?.connected || false
  const queueLength = status.redis?.queue?.queue_length || 0

  return (
    <div className="card">
      <h2 className="text-xl font-semibold mb-4">Upload Status</h2>
      <div className="space-y-3">
        <div>
          <span className="text-dark-text-muted">System:</span>
          <span className={`ml-2 px-2 py-1 rounded text-sm ${
            status.status === 'running'
              ? 'bg-green-600/20 text-green-400' 
              : 'bg-yellow-600/20 text-yellow-400'
          }`}>
            {status.status}
          </span>
        </div>
        <div>
          <span className="text-dark-text-muted">Redis:</span>
          <span className={`ml-2 px-2 py-1 rounded text-sm ${
            redisConnected
              ? 'bg-green-600/20 text-green-400' 
              : 'bg-red-600/20 text-red-400'
          }`}>
            {redisConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <div>
          <span className="text-dark-text-muted">Queue:</span>
          <span className="ml-2 font-mono">{queueLength} tasks</span>
        </div>
        {status.version && (
          <div className="mt-4 pt-4 border-t border-dark-border text-sm text-dark-text-muted">
            Version {status.version}
          </div>
        )}
      </div>
    </div>
  )
}

