'use client'

import { useState } from 'react'
import { ChannelOverview } from '@/components/t2r/ChannelOverview'
import { ScheduleDoctor } from '@/components/t2r/ScheduleDoctor'
import { AssetHealth } from '@/components/t2r/AssetHealth'
import { SRTDoctor } from '@/components/t2r/SRTDoctor'
import { DescriptionLinter } from '@/components/t2r/DescriptionLinter'
import { PlanAndRun } from '@/components/t2r/PlanAndRun'
import { PostUploadVerify } from '@/components/t2r/PostUploadVerify'
import { AuditTrail } from '@/components/t2r/AuditTrail'
import { useT2RWebSocket } from '@/hooks/useT2RWebSocket'

type TabId = 
  | 'overview'
  | 'schedule'
  | 'assets'
  | 'srt'
  | 'desc'
  | 'plan'
  | 'verify'
  | 'audit'

export default function RealityBoard() {
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  
  // Initialize T2R WebSocket connections
  useT2RWebSocket()

  const tabs = [
    { id: 'overview' as TabId, label: '频道总览', icon: '📊' },
    { id: 'schedule' as TabId, label: '排播医生', icon: '📅' },
    { id: 'assets' as TabId, label: '资产健康', icon: '🖼️' },
    { id: 'srt' as TabId, label: 'SRT 医生', icon: '📝' },
    { id: 'desc' as TabId, label: '描述检查', icon: '✍️' },
    { id: 'plan' as TabId, label: '计划与执行', icon: '⚙️' },
    { id: 'verify' as TabId, label: '上传验证', icon: '✅' },
    { id: 'audit' as TabId, label: '审计报告', icon: '📋' },
  ]

  return (
    <main className="min-h-screen p-8 bg-dark-bg-primary">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold mb-2">Mission Control: Reality Board</h1>
        <p className="text-dark-text-muted mb-6">全面接管真实频道资源管理</p>

        {/* Tab Navigation */}
        <div className="flex gap-2 mb-6 border-b border-dark-border overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 px-4 font-semibold transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? 'text-white border-b-2 border-blue-500'
                  : 'text-dark-text-muted hover:text-dark-text-primary'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="space-y-6">
          {activeTab === 'overview' && <ChannelOverview />}
          {activeTab === 'schedule' && <ScheduleDoctor />}
          {activeTab === 'assets' && <AssetHealth />}
          {activeTab === 'srt' && <SRTDoctor />}
          {activeTab === 'desc' && <DescriptionLinter />}
          {activeTab === 'plan' && <PlanAndRun />}
          {activeTab === 'verify' && <PostUploadVerify />}
          {activeTab === 'audit' && <AuditTrail />}
        </div>
      </div>
    </main>
  )
}

