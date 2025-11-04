'use client'

import { ReactNode } from 'react'
import { useScheduleHydrator } from '@/hooks/useScheduleHydrator'
import { useScheduleWebSocketBridge } from '@/hooks/useScheduleWebSocketBridge'
import { GlobalNav } from '@/components/mcrb/GlobalNav'

export default function MCRBLayout({ children }: { children: ReactNode }) {
  // Initialize data hydration and WebSocket bridge
  useScheduleHydrator()
  useScheduleWebSocketBridge()
  
  return (
    <div className="min-h-screen bg-dark-bg-primary">
      <GlobalNav />
      <main>{children}</main>
    </div>
  )
}
