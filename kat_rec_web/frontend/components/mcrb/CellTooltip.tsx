'use client'

import { useState, useRef, useEffect } from 'react'
import { type ScheduleEvent } from '@/stores/scheduleStore'

interface CellTooltipProps {
  event: ScheduleEvent
  count?: number
  children: React.ReactNode
}

export function CellTooltip({ event, count, children }: CellTooltipProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const timeoutRef = useRef<NodeJS.Timeout>()
  
  const handleMouseEnter = (e: React.MouseEvent) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    
    // Delay show for better UX
    timeoutRef.current = setTimeout(() => {
      setIsVisible(true)
      setPosition({ x: e.clientX, y: e.clientY })
    }, 300)
  }
  
  const handleMouseLeave = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    setIsVisible(false)
  }
  
  const handleMouseMove = (e: React.MouseEvent) => {
    if (isVisible) {
      setPosition({ x: e.clientX, y: e.clientY })
    }
  }
  
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])
  
  // Format duration
  const durationText =
    event.durationSec > 0
      ? `${Math.floor(event.durationSec / 60)}:${String(event.durationSec % 60).padStart(2, '0')}`
      : '—'
  
  // Format status
  const statusLabels: Record<string, string> = {
    draft: '草稿',
    planned: '已计划',
    rendering: '渲染中',
    ready: '就绪',
    uploaded: '已上传',
    verified: '已验证',
    failed: '失败',
  }
  
  return (
    <>
      <div
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onMouseMove={handleMouseMove}
      >
        {children}
      </div>
      
      {isVisible && (
        <div
          className="fixed z-50 pointer-events-none"
          style={{
            left: `${position.x + 10}px`,
            top: `${position.y + 10}px`,
            transform: 'translate(0, 0)',
          }}
        >
          <div className="bg-dark-bg-secondary border border-dark-border rounded-lg shadow-xl p-4 min-w-[200px] max-w-[320px]">
            <div className="space-y-2">
              <div>
                <h3 className="font-semibold text-dark-text mb-1">{event.title}</h3>
                {count && count > 1 && (
                  <p className="text-xs text-dark-text-muted mb-2">
                    {count} 个事件
                  </p>
                )}
              </div>
              
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-dark-text-muted">状态:</span>
                  <span className="text-dark-text font-medium">
                    {statusLabels[event.status] || event.status}
                  </span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-dark-text-muted">日期:</span>
                  <span className="text-dark-text">{event.date}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-dark-text-muted">时长:</span>
                  <span className="text-dark-text">{durationText}</span>
                </div>
                
                {event.issues.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-dark-border">
                    <span className="text-xs text-red-400">
                      {event.issues.length} 个问题
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
