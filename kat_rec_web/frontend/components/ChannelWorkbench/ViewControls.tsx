'use client'

import type { ViewMode, DensityMode } from './types'

interface ViewControlsProps {
  viewMode: ViewMode
  onViewModeChange: (mode: ViewMode) => void
  density: DensityMode
  onDensityChange: (density: DensityMode) => void
  searchQuery: string
  onSearchChange: (query: string) => void
}

export function ViewControls({
  viewMode,
  onViewModeChange,
  density,
  onDensityChange,
  searchQuery,
  onSearchChange,
}: ViewControlsProps) {
  return (
    <div className="flex flex-wrap items-center gap-4 mb-4">
      {/* 视图切换 */}
      <div className="flex items-center gap-2 border border-dark-border rounded-lg p-1">
        <button
          onClick={() => onViewModeChange('card')}
          className={`px-3 py-1 rounded text-sm transition-colors ${
            viewMode === 'card'
              ? 'bg-primary text-white'
              : 'text-dark-text-muted hover:text-dark-text'
          }`}
        >
          卡片
        </button>
        <button
          onClick={() => onViewModeChange('table')}
          className={`px-3 py-1 rounded text-sm transition-colors ${
            viewMode === 'table'
              ? 'bg-primary text-white'
              : 'text-dark-text-muted hover:text-dark-text'
          }`}
        >
          表格
        </button>
      </div>

      {/* 密度切换 */}
      <select
        value={density}
        onChange={(e) => onDensityChange(e.target.value as DensityMode)}
        className="px-3 py-1 bg-dark-card border border-dark-border rounded text-sm text-dark-text"
      >
        <option value="comfortable">舒适</option>
        <option value="standard">标准</option>
        <option value="compact">紧凑</option>
      </select>

      {/* 搜索 */}
      <input
        type="text"
        placeholder="搜索频道..."
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        className="flex-1 min-w-[200px] px-4 py-2 bg-dark-card border border-dark-border rounded text-sm text-dark-text placeholder-dark-text-muted focus:outline-none focus:border-primary"
      />
    </div>
  )
}

