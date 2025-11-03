'use client'

interface ChannelCardProps {
  channel: any
}

export default function ChannelCard({ channel }: ChannelCardProps) {
  if (!channel) {
    return (
      <div className="card">
        <h2 className="text-xl font-semibold mb-4">Channel</h2>
        <div className="text-dark-text-muted">Loading...</div>
      </div>
    )
  }

  return (
    <div className="card">
      <h2 className="text-xl font-semibold mb-4">Channel</h2>
      <div className="space-y-3">
        <div>
          <span className="text-dark-text-muted">ID:</span>
          <span className="ml-2 font-mono">{channel.id}</span>
        </div>
        <div>
          <span className="text-dark-text-muted">Name:</span>
          <span className="ml-2">{channel.name}</span>
        </div>
        {channel.description && (
          <div>
            <span className="text-dark-text-muted">Description:</span>
            <span className="ml-2">{channel.description}</span>
          </div>
        )}
        <div>
          <span className="text-dark-text-muted">Status:</span>
          <span className={`ml-2 px-2 py-1 rounded text-sm ${
            channel.is_active 
              ? 'bg-green-600/20 text-green-400' 
              : 'bg-red-600/20 text-red-400'
          }`}>
            {channel.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>
        {channel.config && (
          <div className="mt-4 pt-4 border-t border-dark-border">
            <h3 className="text-sm font-semibold mb-2 text-dark-text-muted">Config</h3>
            <div className="text-sm space-y-1">
              <div>Privacy: <span className="font-mono">{channel.config.upload_privacy}</span></div>
              <div>Schedule: <span className="font-mono">{channel.config.schedule_interval_days}</span> days</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

