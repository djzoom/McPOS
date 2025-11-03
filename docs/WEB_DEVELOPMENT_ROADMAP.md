# Kat Rec Web 前端开发实施路线图

**版本**: v1.0  
**目标**: 分阶段构建可扩展的 Web 控制中心前端  
**最后更新**: 2025-11-10

---

## 📋 总体概览

本路线图将前端开发分为**五个阶段**，既可按 Sprint（2周）迭代，也可按模块推进。每个阶段都有明确的交付物和验收指标。

### 开发原则

- ✅ **模块自治**：每个模块独立开发、可单独挂载测试
- ✅ **渐进增强**：从基础功能到高级特性，逐步完善
- ✅ **性能优先**：大规模场景（100频道）下的性能保证
- ✅ **体验至上**：实时响应、流畅动画、友好提示

---

## 🧱 阶段一：基础框架搭建（Week 1–2）

### 目标

**让前端整体跑起来、组件能渲染数据**

### 关键步骤

#### 1. 环境初始化

**技术栈配置**：
- Next.js 15 + TypeScript + Tailwind CSS
- ESLint + Prettier + Husky（代码规范与 Git Hook）
- Node.js 20+ / pnpm 包管理器

**初始化命令**：
```bash
# 创建 Next.js 项目
pnpm create next-app@latest kat-rec-web-frontend \
  --typescript \
  --tailwind \
  --app \
  --no-src-dir \
  --import-alias "@/*"

cd kat-rec-web-frontend

# 配置代码规范
pnpm add -D eslint-config-prettier prettier
pnpm add -D husky lint-staged
npx husky install
```

**配置文件**：

```json
// package.json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "format": "prettier --write .",
    "type-check": "tsc --noEmit"
  },
  "lint-staged": {
    "*.{ts,tsx}": ["eslint --fix", "prettier --write"],
    "*.{json,md}": ["prettier --write"]
  }
}
```

#### 2. 核心依赖安装

```bash
# 状态管理
pnpm add zustand @tanstack/react-query

# UI 组件库
pnpm add @tanstack/react-table react-virtuoso
pnpm add framer-motion recharts

# 国际化
pnpm add next-intl

# ShadCN UI（需要先初始化）
npx shadcn-ui@latest init
npx shadcn-ui@latest add button card table tabs dialog toast

# 开发依赖
pnpm add -D vitest @testing-library/react @playwright/test
```

#### 3. 目录结构搭建

```
frontend/
├── app/                      # Next.js App Router
│   ├── (dashboard)/         # 路由组
│   │   ├── page.tsx         # 主仪表板
│   │   ├── layout.tsx       # 布局
│   │   └── loading.tsx      # 加载状态
│   ├── layout.tsx           # 根布局
│   └── globals.css          # 全局样式
│
├── components/               # UI 组件
│   ├── MissionControl/      # 态势总览
│   ├── ChannelWorkbench/    # 频道工作盘
│   ├── OpsQueue/            # 操作队列
│   ├── Timeline/            # 时间线
│   ├── AlertsPanel/         # 告警面板
│   └── ui/                  # ShadCN 基础组件
│       ├── button.tsx
│       ├── card.tsx
│       └── table.tsx
│
├── stores/                   # Zustand 状态
│   ├── channelStore.ts
│   ├── opsQueueStore.ts
│   ├── timelineStore.ts
│   ├── alertStore.ts
│   └── uiStore.ts
│
├── services/                 # API 服务
│   ├── apiClient.ts         # Axios/Fetch 封装
│   ├── websocket.ts         # WebSocket 客户端
│   └── queries/             # React Query 查询
│       ├── channels.ts
│       ├── library.ts
│       └── episodes.ts
│
├── hooks/                    # 自定义 Hook
│   ├── useEventBus.ts       # WebSocket 事件总线
│   ├── useChannel.ts
│   └── useWebSocket.ts
│
├── utils/                    # 工具函数
│   ├── formatters.ts        # 数据格式化
│   ├── validators.ts        # 表单验证
│   └── constants.ts         # 常量定义
│
├── styles/                   # 样式配置
│   ├── tailwind.config.ts
│   └── theme.css            # CSS 变量
│
└── types/                    # TypeScript 类型
    ├── api.ts
    ├── channel.ts
    └── library.ts
```

#### 4. 配置全局主题与 Tailwind Tokens

**`styles/theme.css`**：
```css
:root {
  /* 语义化颜色变量 */
  --color-primary: #4a9eff;
  --color-success: #4ade80;
  --color-error: #f87171;
  --color-warning: #fbbf24;
  --color-info: #60a5fa;
  
  /* 深色主题背景 */
  --bg-primary: #1a1a1a;
  --bg-secondary: #2a2a2a;
  --bg-tertiary: #333;
  
  /* 文字颜色 */
  --text-primary: #e0e0e0;
  --text-secondary: #aaa;
  --text-muted: #888;
  
  /* 边框 */
  --border-color: #333;
  --border-radius: 8px;
}

[data-theme="light"] {
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --text-primary: #1a1a1a;
  /* ... */
}
```

**`tailwind.config.ts`**：
```typescript
import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ['class'],
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: 'var(--color-primary)',
        success: 'var(--color-success)',
        error: 'var(--color-error)',
        warning: 'var(--color-warning)',
        background: {
          primary: 'var(--bg-primary)',
          secondary: 'var(--bg-secondary)',
          tertiary: 'var(--bg-tertiary)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
        },
      },
      borderRadius: {
        DEFAULT: 'var(--border-radius)',
      },
    },
  },
  plugins: [],
}

export default config
```

#### 5. 接通 FastAPI Mock 数据

**Mock API 服务** (`services/apiClient.ts`)：
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const apiClient = {
  async get<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${API_URL}${endpoint}`)
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`)
    }
    return response.json()
  },
  
  async post<T>(endpoint: string, data: unknown): Promise<T> {
    const response = await fetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`)
    }
    return response.json()
  },
}

// 本地 Mock 数据（开发环境）
export const mockData = {
  channels: [
    { id: 'CH-001', name: 'Channel A', isActive: true },
    { id: 'CH-002', name: 'Channel B', isActive: false },
  ],
  songs: [],
  images: [],
}
```

**React Query 配置** (`app/providers.tsx`)：
```typescript
'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30 * 1000, // 30秒
        refetchOnWindowFocus: false,
      },
    },
  }))
  
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
```

**CORS 配置确认**（FastAPI 后端）：
```python
# kat_rec_web/backend/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 验收标准

- ✅ Next.js 15 项目可运行（`pnpm dev`）
- ✅ TypeScript 类型检查通过
- ✅ ESLint/Prettier 配置生效
- ✅ Mock API 数据可正常获取
- ✅ 基础组件（Button、Card）可正常渲染
- ✅ 深色主题样式生效

### 交付物清单

- [x] Next.js 15 项目骨架
- [x] 完整的目录结构
- [x] Tailwind + 主题配置
- [x] ShadCN UI 基础组件集成
- [x] API 客户端封装（支持 Mock）
- [x] React Query 配置

---

## ⚙️ 阶段二：核心模块实现（Week 3–6）

### 目标

**实现全部核心模块 UI + 逻辑，每个模块独立可测试**

### 模块开发计划

| 模块 | 关键目标 | 状态依赖 | 技术难点 | 预计工时 |
|------|---------|---------|---------|---------|
| **Mission Control** | 成功率、失败数、容量与趋势展示 | `useChannelStore`<br>`useOpsQueueStore` | 数据聚合与刷新逻辑 | 5天 |
| **Channel Workbench** | 频道卡片 + 紧凑表格模式 | `useChannelStore` | 虚拟滚动、实时更新 | 7天 |
| **Ops Queue** | 任务队列可视化、优先级调整 | `useOpsQueueStore` | 并发排序、状态动画 | 6天 |
| **Timeline** | 今日排播时间轴与拖拽调整 | `useTimelineStore` | 时间计算、冲突检测 | 6天 |
| **Alerts Panel** | 告警实时推送与确认 | `useAlertStore` | WS 消息路由、去重逻辑 | 4天 |

### 模块1：Mission Control（态势总览）

**功能点**：
1. 健康指标卡片组（成功率、失败数、倒计时）
2. 队列状态与容量进度条
3. 7日趋势图（Recharts）

**实现示例**：
```typescript
// components/MissionControl/index.tsx
'use client'

import { useQuery } from '@tanstack/react-query'
import { useChannelStore } from '@/stores/channelStore'
import { HealthMetrics } from './HealthMetrics'
import { QueueStatus } from './QueueStatus'
import { TrendChart } from './TrendChart'

export function MissionControl() {
  const channels = useChannelStore(state => state.channels)
  
  // 聚合数据
  const successRate = calculateSuccessRate(channels)
  const failedCount = channels.filter(ch => ch.status === 'error').length
  const queueCapacity = calculateQueueCapacity()
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <HealthMetrics 
        successRate={successRate}
        failedCount={failedCount}
      />
      <QueueStatus capacity={queueCapacity} />
      <TrendChart period="7d" />
    </div>
  )
}
```

**测试要求**：
- ✅ 数据聚合逻辑正确
- ✅ 图表正常渲染
- ✅ 刷新按钮生效

---

### 模块2：Channel Workbench（频道工作盘）

**功能点**：
1. 卡片视图（默认，10频道舒适）
2. 紧凑表视图（100频道高密度）
3. 视图切换、搜索、筛选、排序
4. Pin 关键频道

**实现示例**：
```typescript
// components/ChannelWorkbench/index.tsx
'use client'

import { useState } from 'react'
import { useChannelStore } from '@/stores/channelStore'
import { ChannelCard } from './ChannelCard'
import { ChannelTable } from './ChannelTable'
import { ViewControls } from './ViewControls'

export function ChannelWorkbench() {
  const [viewMode, setViewMode] = useState<'card' | 'table'>('card')
  const [density, setDensity] = useState<'comfortable' | 'standard' | 'compact'>('comfortable')
  const channels = useChannelStore(state => state.channels)
  
  // 超过20个频道自动切换虚拟滚动
  const shouldVirtualize = channels.length > 20
  
  return (
    <div>
      <ViewControls 
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        density={density}
        onDensityChange={setDensity}
      />
      
      {viewMode === 'card' ? (
        <ChannelCardGrid 
          channels={channels}
          density={density}
          virtualized={shouldVirtualize}
        />
      ) : (
        <ChannelTable 
          channels={channels}
          density={density}
          virtualized={shouldVirtualize}
        />
      )}
    </div>
  )
}
```

**技术难点**：
- **虚拟滚动**：使用 React Virtuoso 实现
- **实时更新**：频道状态变更时平滑更新动画

**测试要求**：
- ✅ 视图切换流畅
- ✅ 搜索/筛选/排序功能正常
- ✅ 虚拟滚动性能达标（100频道流畅）

---

### 模块3：Ops Queue（操作队列）

**功能点**：
1. 队列列表展示（表格形式）
2. 任务状态可视化（进度条、状态标签）
3. 批量操作（重试、暂停、调整优先级）
4. 优先级拖拽排序

**实现示例**：
```typescript
// components/OpsQueue/index.tsx
'use client'

import { useOpsQueueStore } from '@/stores/opsQueueStore'
import { QueueTable } from './QueueTable'
import { BatchActions } from './BatchActions'

export function OpsQueue() {
  const queue = useOpsQueueStore(state => state.queue)
  const [selectedTasks, setSelectedTasks] = useState<string[]>([])
  
  return (
    <div>
      <BatchActions 
        selectedTasks={selectedTasks}
        onBatchRetry={() => {/* ... */}}
        onBatchPause={() => {/* ... */}}
      />
      
      <QueueTable 
        tasks={queue}
        selectedTasks={selectedTasks}
        onSelectTasks={setSelectedTasks}
        onPriorityChange={(taskId, priority) => {
          useOpsQueueStore.getState().updateQueueItem(taskId, { priority })
        }}
      />
    </div>
  )
}
```

**技术难点**：
- **并发排序**：拖拽调整优先级时实时更新队列顺序
- **状态动画**：任务状态变更时的过渡动画（Framer Motion）

**测试要求**：
- ✅ 队列列表正确渲染
- ✅ 批量操作功能正常
- ✅ 优先级调整实时生效

---

### 模块4：Timeline（今日时间线）

**功能点**：
1. 今日排期可视化（时间轴）
2. 拖拽改期功能
3. 冲突检测与预警
4. 拥堵预警

**实现示例**：
```typescript
// components/Timeline/index.tsx
'use client'

import { useTimelineStore } from '@/stores/timelineStore'
import { TimelineView } from './TimelineView'
import { ConflictDetector } from './ConflictDetector'

export function Timeline() {
  const episodes = useTimelineStore(state => state.episodes)
  const todayEpisodes = filterTodayEpisodes(episodes)
  
  // 冲突检测
  const conflicts = detectConflicts(todayEpisodes)
  const congestion = detectCongestion(todayEpisodes)
  
  return (
    <div>
      {conflicts.length > 0 && (
        <ConflictAlert conflicts={conflicts} />
      )}
      
      {congestion.length > 0 && (
        <CongestionWarning congestion={congestion} />
      )}
      
      <TimelineView 
        episodes={todayEpisodes}
        onDragEnd={(episodeId, newTime) => {
          // 更新期数时间
          useTimelineStore.getState().updateEpisode(episodeId, {
            schedule_time: newTime,
          })
        }}
      />
    </div>
  )
}
```

**技术难点**：
- **时间计算**：准确计算时间轴位置
- **冲突检测**：识别资源冲突（同一时间多个任务）

**测试要求**：
- ✅ 时间轴正确渲染
- ✅ 拖拽改期功能正常
- ✅ 冲突检测准确

---

### 模块5：Alerts Panel（告警面板）

**功能点**：
1. 告警列表展示
2. 实时推送接收
3. 告警确认/清除
4. 未读计数

**实现示例**：
```typescript
// components/AlertsPanel/index.tsx
'use client'

import { useAlertStore } from '@/stores/alertStore'
import { AlertList } from './AlertList'
import { AlertBadge } from './AlertBadge'

export function AlertsPanel() {
  const alerts = useAlertStore(state => state.alerts)
  const unreadCount = useAlertStore(state => state.unreadCount)
  const acknowledge = useAlertStore(state => state.acknowledge)
  
  return (
    <div>
      <AlertBadge count={unreadCount} />
      
      <AlertList 
        alerts={alerts}
        onAcknowledge={(alertId) => acknowledge(alertId)}
      />
    </div>
  )
}
```

**技术难点**：
- **WS 消息路由**：正确分发告警消息到对应组件
- **去重逻辑**：避免重复显示相同告警

**测试要求**：
- ✅ 告警列表正确渲染
- ✅ 实时推送功能正常
- ✅ 确认/清除功能生效

---

### 模块开发原则

**✅ 每个模块独立开发、可单独挂载测试**

**测试组件示例**：
```typescript
// components/MissionControl/MissionControl.test.tsx
import { render, screen } from '@testing-library/react'
import { MissionControl } from './index'

describe('MissionControl', () => {
  it('renders health metrics', () => {
    render(<MissionControl />)
    expect(screen.getByText(/成功率/)).toBeInTheDocument()
  })
})
```

---

### 验收标准

- ✅ 所有核心模块 UI 完整
- ✅ 每个模块可独立挂载测试
- ✅ 数据绑定与状态管理正常
- ✅ 基础交互功能可用（点击、切换视图等）
- ✅ 单元测试覆盖核心逻辑

### 交付物清单

- [x] Mission Control 组件
- [x] Channel Workbench 组件
- [x] Ops Queue 组件
- [x] Timeline 组件
- [x] Alerts Panel 组件
- [x] 各模块单元测试

---

## 🔁 阶段三：实时通信与状态同步（Week 7–8）

### 目标

**实现 WebSocket 实时刷新 + 状态流联动，延迟 < 1s**

### 关键步骤

#### 1. 实现 WebSocket Client

**统一 Event Bus Hook** (`hooks/useEventBus.ts`)：
```typescript
import { useEffect } from 'react'
import { useChannelStore } from '@/stores/channelStore'
import { useOpsQueueStore } from '@/stores/opsQueueStore'
import { useTimelineStore } from '@/stores/timelineStore'
import { useAlertStore } from '@/stores/alertStore'
import { useWebSocketStore } from '@/stores/websocketStore'

export const useEventBus = () => {
  const setConnected = useWebSocketStore(state => state.setConnected)
  const queryClient = useQueryClient()
  
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/events')
    
    ws.onopen = () => {
      setConnected(true)
      console.log('WebSocket connected')
    }
    
    ws.onclose = () => {
      setConnected(false)
      // 延迟重连
      setTimeout(() => {
        // 重连逻辑
      }, 5000)
    }
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)
      
      // 统一事件分发
      switch (message.type) {
        case 'channel.update':
          useChannelStore.getState().updateChannel(
            message.channel_id,
            message.channel
          )
          break
          
        case 'queue.update':
          useOpsQueueStore.getState().updateQueueItem(
            message.task_id,
            message.data
          )
          break
          
        case 'episode.update':
          useTimelineStore.getState().updateEpisode(
            message.episode_id,
            message.data
          )
          break
          
        case 'alert.new':
          useAlertStore.getState().addAlert({
            type: message.alert_type,
            title: message.title,
            message: message.message,
            channelId: message.channel_id,
          })
          break
      }
      
      // 更新 React Query 缓存
      queryClient.invalidateQueries()
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setConnected(false)
    }
    
    return () => {
      ws.close()
    }
  }, [setConnected, queryClient])
}
```

**WebSocket Store** (`stores/websocketStore.ts`)：
```typescript
import { create } from 'zustand'

export interface WebSocketState {
  connected: boolean
  reconnectAttempts: number
  setConnected: (connected: boolean) => void
  incrementReconnectAttempts: () => void
  resetReconnectAttempts: () => void
}

export const useWebSocketStore = create<WebSocketState>()((set) => ({
  connected: false,
  reconnectAttempts: 0,
  
  setConnected: (connected) => set({ connected }),
  
  incrementReconnectAttempts: () => set((state) => ({
    reconnectAttempts: state.reconnectAttempts + 1,
  })),
  
  resetReconnectAttempts: () => set({ reconnectAttempts: 0 }),
}))
```

#### 2. 实现断线重连与回退策略

**重连逻辑**：
```typescript
// hooks/useWebSocketReconnect.ts
import { useEffect, useRef } from 'react'
import { useWebSocketStore } from '@/stores/websocketStore'

export const useWebSocketReconnect = (ws: WebSocket | null) => {
  const reconnectAttempts = useWebSocketStore(state => state.reconnectAttempts)
  const maxAttempts = 5
  
  useEffect(() => {
    if (!ws || ws.readyState === WebSocket.OPEN) return
    
    const reconnect = () => {
      if (reconnectAttempts >= maxAttempts) {
        console.error('Max reconnect attempts reached')
        return
      }
      
      // 指数退避：1s, 2s, 4s, 8s, 16s
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 16000)
      
      setTimeout(() => {
        useWebSocketStore.getState().incrementReconnectAttempts()
        // 重新连接逻辑
        connectWebSocket()
      }, delay)
    }
    
    if (ws.readyState === WebSocket.CLOSED) {
      reconnect()
    }
  }, [ws, reconnectAttempts])
}
```

**回退到轮询**：
```typescript
// hooks/usePollingFallback.ts
import { useQueryClient } from '@tanstack/react-query'
import { useWebSocketStore } from '@/stores/websocketStore'

export const usePollingFallback = () => {
  const queryClient = useQueryClient()
  const wsConnected = useWebSocketStore(state => state.connected)
  
  useEffect(() => {
    if (wsConnected) return // WebSocket 连接时禁用轮询
    
    // 每30秒轮询一次
    const interval = setInterval(() => {
      queryClient.invalidateQueries()
    }, 30000)
    
    return () => clearInterval(interval)
  }, [wsConnected, queryClient])
}
```

#### 3. 状态变化动画

**任务状态动画** (`components/OpsQueue/QueueItem.tsx`)：
```typescript
import { motion } from 'framer-motion'

export const QueueItem = ({ task }) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return '#888'
      case 'processing': return '#4a9eff'
      case 'completed': return '#4ade80'
      case 'failed': return '#f87171'
      default: return '#888'
    }
  }
  
  return (
    <motion.tr
      initial={{ opacity: 0, x: -20 }}
      animate={{ 
        opacity: 1, 
        x: 0,
        backgroundColor: getStatusColor(task.status),
      }}
      transition={{ duration: 0.3 }}
      whileHover={{ scale: 1.02 }}
    >
      {/* 表格内容 */}
    </motion.tr>
  )
}
```

**失败闪烁动画**：
```typescript
<motion.div
  animate={{
    backgroundColor: ['#f87171', '#ef4444', '#f87171'],
  }}
  transition={{
    duration: 2,
    repeat: Infinity,
  }}
>
  任务失败
</motion.div>
```

### 验收标准

- ✅ WebSocket 连接成功
- ✅ 事件正确分发到对应 Store
- ✅ 断线自动重连（最多5次）
- ✅ 断线时自动回退到轮询
- ✅ 重连后全量刷新
- ✅ 状态变更动画流畅
- ✅ 延迟 < 1s（从后端推送到UI更新）

### 交付物清单

- [x] WebSocket 客户端实现
- [x] Event Bus Hook
- [x] 断线重连机制
- [x] 轮询回退策略
- [x] 状态变化动画
- [x] 集成测试

---

## 📊 阶段四：性能与体验优化（Week 9–10）

### 目标

**性能优化 + UX 细节，Lighthouse 90+**

### 优化策略

#### 1. 虚拟化优化

**频道列表虚拟滚动**：
```typescript
import { Virtuoso } from 'react-virtuoso'

export const ChannelCardGrid = ({ channels, density }) => {
  if (channels.length > 20) {
    return (
      <Virtuoso
        data={channels}
        itemContent={(index, channel) => (
          <ChannelCard channel={channel} density={density} />
        )}
        style={{ height: '600px' }}
        overscan={5} // 预渲染5个item
      />
    )
  }
  
  return channels.map(channel => (
    <ChannelCard key={channel.id} channel={channel} density={density} />
  ))
}
```

#### 2. 懒加载策略

**模块懒加载**：
```typescript
import dynamic from 'next/dynamic'
import { Suspense } from 'react'

const MissionControl = dynamic(() => import('@/components/MissionControl'), {
  loading: () => <MissionControlSkeleton />,
  ssr: false,
})

const ChannelWorkbench = dynamic(() => import('@/components/ChannelWorkbench'))

export default function Dashboard() {
  return (
    <div>
      <Suspense fallback={<MissionControlSkeleton />}>
        <MissionControl />
      </Suspense>
      
      <Suspense fallback={<ChannelWorkbenchSkeleton />}>
        <ChannelWorkbench />
      </Suspense>
    </div>
  )
}
```

**Intersection Observer 延迟加载**：
```typescript
import { useInView } from 'react-intersection-observer'

export const LazyComponent = () => {
  const { ref, inView } = useInView({
    triggerOnce: true,
    threshold: 0.1,
  })
  
  return (
    <div ref={ref}>
      {inView && <HeavyComponent />}
    </div>
  )
}
```

#### 3. 缓存与失效

**React Query 缓存策略**：
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000, // 30秒
      cacheTime: 5 * 60 * 1000, // 5分钟
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
  },
})
```

#### 4. 响应式优化

**断点配置**：
```typescript
// tailwind.config.ts
screens: {
  'sm': '640px',
  'md': '768px',
  'lg': '1024px',
  'xl': '1280px',
}
```

**移动端适配**：
```typescript
<div className="
  grid 
  grid-cols-1 
  md:grid-cols-2 
  lg:grid-cols-3
  gap-4
">
  {/* 卡片 */}
</div>
```

#### 5. 可用性增强

**Skeleton 加载**：
```typescript
export const ChannelCardSkeleton = () => (
  <div className="animate-pulse space-y-3">
    <div className="h-4 bg-gray-700 rounded w-3/4"></div>
    <div className="h-3 bg-gray-700 rounded w-1/2"></div>
    <div className="h-2 bg-gray-700 rounded w-full"></div>
  </div>
)
```

**Toast 错误提示**：
```typescript
import toast from 'react-hot-toast'

try {
  await retryTask(taskId)
  toast.success('任务已重新排队')
} catch (error) {
  toast.error('操作失败，请稍后重试')
}
```

**Theme 切换**：
```typescript
export const ThemeToggle = () => {
  const { theme, setTheme } = useUIStore()
  
  return (
    <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
      {theme === 'dark' ? '🌙' : '☀️'}
    </button>
  )
}
```

### 验收标准

- ✅ Lighthouse 性能分数 ≥ 90
- ✅ First Contentful Paint (FCP) < 1.8s
- ✅ Largest Contentful Paint (LCP) < 2.5s
- ✅ Time to Interactive (TTI) < 3.8s
- ✅ Cumulative Layout Shift (CLS) < 0.1
- ✅ 100频道场景下流畅（60fps）
- ✅ 移动端适配良好

### 交付物清单

- [x] 虚拟滚动实现
- [x] 懒加载策略
- [x] 缓存优化
- [x] 响应式布局
- [x] Skeleton 加载
- [x] Toast 提示
- [x] Theme 切换
- [x] 性能测试报告

---

## 🧩 阶段五：扩展与持续交付（Week 11+）

### 目标

**CI/CD + 监控 + 微前端雏形，稳定上线**

### 关键步骤

#### 1. 微前端拆分

**Module Federation 配置**（可选，频道规模 > 50 时）：
```javascript
// webpack.config.js
const ModuleFederationPlugin = require('@module-federation/nextjs-mf')

module.exports = {
  webpack: (config, options) => {
    config.plugins.push(
      new ModuleFederationPlugin({
        name: 'dashboard',
        remotes: {
          library: 'library@http://localhost:3001/remoteEntry.js',
          scheduler: 'scheduler@http://localhost:3002/remoteEntry.js',
        },
      })
    )
    return config
  },
}
```

#### 2. 测试体系

**单元测试** (`tests/components/ChannelCard.test.tsx`)：
```typescript
import { render, screen } from '@testing-library/react'
import { ChannelCard } from '@/components/ChannelWorkbench/ChannelCard'

describe('ChannelCard', () => {
  it('renders channel name', () => {
    render(<ChannelCard channel={{ id: '1', name: 'Test' }} />)
    expect(screen.getByText('Test')).toBeInTheDocument()
  })
})
```

**E2E 测试** (`tests/e2e/dashboard.spec.ts`)：
```typescript
import { test, expect } from '@playwright/test'

test('dashboard loads correctly', async ({ page }) => {
  await page.goto('http://localhost:3000')
  await expect(page.locator('h1')).toContainText('Kat Rec Web Control Center')
})
```

#### 3. CI/CD

**GitHub Actions** (`.github/workflows/ci.yml`)：
```yaml
name: CI

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: pnpm/action-setup@v2
      - run: pnpm install
      - run: pnpm lint
  
  type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: pnpm/action-setup@v2
      - run: pnpm install
      - run: pnpm type-check
  
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: pnpm/action-setup@v2
      - run: pnpm install
      - run: pnpm test
  
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: pnpm/action-setup@v2
      - run: pnpm install
      - run: pnpm build
      - run: pnpm start &
      - run: pnpm test:e2e
  
  deploy:
    needs: [lint, type-check, test, e2e]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - uses: pnpm/action-setup@v2
      - run: pnpm install
      - run: pnpm build
      - uses: vercel/action@v20
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
```

#### 4. 监控与日志

**Sentry 集成**：
```typescript
import * as Sentry from '@sentry/nextjs'

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 1.0,
})
```

**Vercel Analytics**：
```typescript
import { Analytics } from '@vercel/analytics/react'

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  )
}
```

#### 5. 未来增强

**Watchlist 功能**：
```typescript
export const useWatchlistStore = create((set) => ({
  watchlists: [],
  createWatchlist: (name) => {/* ... */},
  addChannelToWatchlist: (watchlistId, channelId) => {/* ... */},
}))
```

**权限系统**：
```typescript
export const useAuthStore = create((set) => ({
  user: null,
  permissions: [],
  hasPermission: (permission) => {/* ... */},
}))
```

### 验收标准

- ✅ CI/CD 流水线正常
- ✅ 测试覆盖率 ≥ 80%
- ✅ Sentry 错误追踪正常
- ✅ Vercel Analytics 数据收集正常
- ✅ 生产环境稳定运行

### 交付物清单

- [x] 微前端拆分（可选）
- [x] 完整测试体系
- [x] CI/CD 配置
- [x] 监控集成
- [x] 生产部署文档

---

## 📈 阶段成果清单总结

| 阶段 | 交付物 | 验收指标 | 状态 |
|------|--------|---------|------|
| **阶段1** | 可运行 Next.js 骨架 | SSR + Mock API 连通 | ⏳ |
| **阶段2** | 全部核心模块 UI + 逻辑 | 模块自测通过 | ⏳ |
| **阶段3** | WS 实时刷新 + 状态流联动 | < 1s 延迟 | ⏳ |
| **阶段4** | 性能优化 + UX 细节 | Lighthouse 90+ | ⏳ |
| **阶段5** | CI/CD + 监控 + 微前端雏形 | 稳定上线 | ⏳ |

---

## 💡 开发建议

### 代码规范

- 使用 TypeScript 严格模式
- 组件命名：PascalCase
- 文件命名：kebab-case 或 PascalCase
- 使用 ESLint + Prettier 保持代码风格一致

### Git 工作流

- **主分支**：`main`（生产环境）
- **开发分支**：`develop`（集成测试）
- **功能分支**：`feature/模块名`（按模块开发）
- **提交信息**：使用 Conventional Commits 格式

### 代码审查

- 每个 PR 至少需要 1 人审查
- 核心模块需要 2 人审查
- 确保测试覆盖和文档更新

---

## 附录：相关文档

- [前端架构方案](./WEB_FRONTEND_ARCHITECTURE.md) - 技术选型与架构演进
- [产品设计愿景](./WEB_PRODUCT_DESIGN_VISION.md) - 总导演式设计主张
- [数据流与状态管理设计](./WEB_STATE_MANAGEMENT_DESIGN.md) - Zustand状态模型
- [交互设计与数据规范](./WEB_DASHBOARD_DESIGN_SPEC.md) - 详细交互规范

---

**文档维护**: 本文档应随开发进度持续更新。  
**反馈渠道**: 如有疑问或建议，请联系前端开发团队。

