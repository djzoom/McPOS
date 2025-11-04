'use client'

import { useEffect } from 'react'
import { type ScheduleEvent } from '@/stores/scheduleStore'
import { planEpisode, runEpisode, startUpload, verifyUpload } from '@/services/t2rApi'
import { useScheduleStore } from '@/stores/scheduleStore'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Play, Upload, CheckCircle, FileText, AlertCircle, Image, Music, Type, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'

interface TaskPanelProps {
  event: ScheduleEvent
  isOpen: boolean
  onClose: () => void
}

/**
 * Task Panel - Side drawer for event operations
 */
export function TaskPanel({ event, isOpen, onClose }: TaskPanelProps) {
  const patchEvent = useScheduleStore((state) => state.patchEvent)
  const markEventStatus = useScheduleStore((state) => state.markEventStatus)
  
  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])
  
  // Optimistic update helper
  const updateEventOptimistically = (updates: Partial<ScheduleEvent>) => {
    patchEvent(event.id, updates)
  }
  
  // Plan operation
  const handlePlan = async () => {
    const originalStatus = event.status
    try {
      updateEventOptimistically({ status: 'planned' })
      const loadingToast = toast.loading('正在计划...', { id: `plan-${event.id}` })
      
      const result = await planEpisode({
        episode_id: event.id,
      })
      
      if (result.status === 'ok') {
        markEventStatus(event.id, 'planned')
        toast.success('计划成功', { id: `plan-${event.id}` })
      } else {
        markEventStatus(event.id, originalStatus)
        const errorMsg = result.errors?.join(', ') || '计划失败'
        toast.error(errorMsg, { id: `plan-${event.id}`, duration: 5000 })
        console.error('Plan error:', result.errors)
      }
    } catch (error: any) {
      markEventStatus(event.id, originalStatus)
      const errorMsg = error?.message || '计划失败：网络错误'
      toast.error(errorMsg, { id: `plan-${event.id}`, duration: 5000 })
      console.error('Plan error:', error)
    }
  }
  
  // Render operation
  const handleRender = async () => {
    const originalStatus = event.status
    try {
      updateEventOptimistically({ status: 'rendering' })
      toast.loading('正在启动渲染...', { id: `render-${event.id}` })
      
      const result = await runEpisode({
        episode_id: event.id,
      })
      
      if (result.status === 'ok') {
        markEventStatus(event.id, 'rendering')
        toast.success('渲染已启动，WebSocket 将实时更新进度', { 
          id: `render-${event.id}`,
          duration: 4000 
        })
      } else {
        markEventStatus(event.id, originalStatus)
        const errorMsg = result.errors?.join(', ') || '渲染失败'
        toast.error(errorMsg, { id: `render-${event.id}`, duration: 5000 })
        console.error('Render error:', result.errors)
      }
    } catch (error: any) {
      markEventStatus(event.id, originalStatus)
      const errorMsg = error?.message || '渲染失败：网络错误'
      toast.error(errorMsg, { id: `render-${event.id}`, duration: 5000 })
      console.error('Render error:', error)
    }
  }
  
  // Upload operation
  const handleUpload = async () => {
    if (!event.assets.audio) {
      toast.error('缺少视频文件，无法上传', { duration: 4000 })
      return
    }
    
    const originalStatus = event.status
    try {
      updateEventOptimistically({ status: 'uploaded' })
      toast.loading('正在启动上传...', { id: `upload-${event.id}` })
      
      const result = await startUpload({
        episode_id: event.id,
        video_file: event.assets.audio,
        metadata: {
          title: event.title,
          description: event.assets.description || '',
        },
      })
      
      if (result.status === 'ok') {
        markEventStatus(event.id, 'uploaded')
        toast.success('上传已启动，WebSocket 将实时更新进度', { 
          id: `upload-${event.id}`,
          duration: 4000 
        })
      } else {
        markEventStatus(event.id, originalStatus)
        const errorMsg = result.errors?.join(', ') || '上传失败'
        toast.error(errorMsg, { id: `upload-${event.id}`, duration: 5000 })
        console.error('Upload error:', result.errors)
      }
    } catch (error: any) {
      markEventStatus(event.id, originalStatus)
      const errorMsg = error?.message || '上传失败：网络错误'
      toast.error(errorMsg, { id: `upload-${event.id}`, duration: 5000 })
      console.error('Upload error:', error)
    }
  }
  
  // Verify operation
  const handleVerify = async () => {
    // TODO: Extract video_id from event metadata (may need API to fetch)
    // For now, use a placeholder or require user input
    const videoId = event.kpis?.lastRunAt || ''
    
    if (!videoId) {
      toast.error('缺少视频 ID，无法验证。请先完成上传。', { duration: 5000 })
      return
    }
    
    const originalStatus = event.status
    try {
      toast.loading('正在验证上传结果...', { id: `verify-${event.id}` })
      
      const result = await verifyUpload({
        episode_id: event.id,
        video_id: videoId,
      })
      
      if (result.status === 'ok' && result.all_passed) {
        markEventStatus(event.id, 'verified')
        patchEvent(event.id, { issues: [] })
        toast.success('验证通过！所有检查项已通过。', { 
          id: `verify-${event.id}`,
          duration: 4000 
        })
      } else {
        markEventStatus(event.id, originalStatus)
        const issues = result.checks
          ?.filter((c) => c.status !== 'passed')
          .map((c) => c.message) || ['验证失败']
        patchEvent(event.id, { issues })
        
        const failedChecks = result.checks?.filter((c) => c.status !== 'passed') || []
        const errorMsg = failedChecks.length > 0
          ? `验证失败：${failedChecks.map((c) => c.name).join(', ')}`
          : '验证失败'
        
        toast.error(errorMsg, { id: `verify-${event.id}`, duration: 6000 })
        console.error('Verify failed:', failedChecks)
      }
    } catch (error: any) {
      markEventStatus(event.id, originalStatus)
      const errorMsg = error?.message || '验证失败：网络错误'
      toast.error(errorMsg, { id: `verify-${event.id}`, duration: 5000 })
      console.error('Verify error:', error)
    }
  }
  
  // Determine available actions based on status
  const canPlan = event.status === 'draft'
  const canRender = event.status === 'planned' || event.status === 'draft'
  const canUpload = event.status === 'ready' && !!event.assets.audio
  const canVerify = event.status === 'uploaded'
  
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50 z-40"
          />
          
          {/* Panel */}
          <motion.div
            layoutId={`event-${event.id}`}
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 bottom-0 w-full max-w-lg bg-dark-bg-secondary border-l border-dark-border shadow-2xl z-50 overflow-y-auto"
          >
            <div className="p-6">
              {/* Header */}
              <div className="flex items-start justify-between mb-6">
                <div className="flex-1">
                  <h2 className="text-2xl font-bold text-dark-text mb-2">{event.title}</h2>
                  <p className="text-sm text-dark-text-muted">{event.date}</p>
                </div>
                <button
                  onClick={onClose}
                  className="p-2 rounded-lg hover:bg-dark-bg-tertiary transition-colors"
                  aria-label="关闭"
                >
                  <X className="w-5 h-5 text-dark-text-muted" />
                </button>
              </div>
              
              {/* Status */}
              <div className="mb-6 p-4 rounded-lg bg-dark-bg-tertiary border border-dark-border">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-dark-text-muted">状态</span>
                  <span className="text-sm font-semibold text-dark-text">{event.status}</span>
                </div>
              </div>
              
              {/* Assets */}
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-dark-text-muted mb-3">资产</h3>
                <div className="space-y-2">
                  {[
                    { key: 'cover', label: '封面', icon: Image },
                    { key: 'audio', label: '音频', icon: Music },
                    { key: 'description', label: '描述', icon: FileText },
                    { key: 'captions', label: '字幕', icon: Type },
                  ].map(({ key, label, icon: Icon }) => {
                    const asset = event.assets[key as keyof typeof event.assets]
                    return (
                      <div
                        key={key}
                        className={`flex items-center gap-3 p-3 rounded-lg border ${
                          asset
                            ? 'bg-green-500/10 border-green-500/20'
                            : 'bg-dark-bg-tertiary border-dark-border'
                        }`}
                      >
                        <Icon
                          className={`w-5 h-5 ${
                            asset ? 'text-green-400' : 'text-dark-text-muted'
                          }`}
                        />
                        <div className="flex-1">
                          <p className="text-sm font-medium text-dark-text">{label}</p>
                          {asset && (
                            <p className="text-xs text-dark-text-muted truncate">{asset}</p>
                          )}
                        </div>
                        {asset ? (
                          <CheckCircle className="w-5 h-5 text-green-400" />
                        ) : (
                          <AlertCircle className="w-5 h-5 text-dark-text-muted" />
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
              
              {/* Issues */}
              {event.issues.length > 0 && (
                <div className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/20">
                  <h3 className="text-sm font-semibold text-red-400 mb-2">问题</h3>
                  <ul className="space-y-1">
                    {event.issues.map((issue, i) => (
                      <li key={i} className="text-sm text-red-300/80">
                        • {issue}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              {/* Actions */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-dark-text-muted mb-3">操作</h3>
                
                {canPlan && (
                  <button
                    onClick={handlePlan}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-primary hover:bg-primary/90 text-white rounded-lg transition-colors font-medium"
                  >
                    <Play className="w-4 h-4" />
                    计划 (Plan)
                  </button>
                )}
                
                {canRender && (
                  <button
                    onClick={handleRender}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-500 hover:bg-purple-500/90 text-white rounded-lg transition-colors font-medium"
                  >
                    <Play className="w-4 h-4" />
                    渲染 (Render)
                  </button>
                )}
                
                {canUpload && (
                  <button
                    onClick={handleUpload}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-cyan-500 hover:bg-cyan-500/90 text-white rounded-lg transition-colors font-medium"
                  >
                    <Upload className="w-4 h-4" />
                    上传 (Upload)
                  </button>
                )}
                
                {canVerify && (
                  <button
                    onClick={handleVerify}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-500 hover:bg-green-500/90 text-white rounded-lg transition-colors font-medium"
                  >
                    <CheckCircle className="w-4 h-4" />
                    验证 (Verify)
                  </button>
                )}
              </div>
              
              {/* KPIs */}
              {event.kpis && (
                <div className="mt-6 pt-6 border-t border-dark-border">
                  <h3 className="text-sm font-semibold text-dark-text-muted mb-3">指标</h3>
                  <div className="space-y-2 text-sm">
                    {event.kpis.successRate !== undefined && (
                      <div className="flex justify-between">
                        <span className="text-dark-text-muted">成功率</span>
                        <span className="text-dark-text font-medium">
                          {Math.round(event.kpis.successRate * 100)}%
                        </span>
                      </div>
                    )}
                    {event.kpis.lastRunAt && (
                      <div className="flex justify-between">
                        <span className="text-dark-text-muted">最后运行</span>
                        <span className="text-dark-text font-medium">
                          {new Date(event.kpis.lastRunAt).toLocaleDateString('zh-CN')}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
