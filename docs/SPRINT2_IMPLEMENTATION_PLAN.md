# Sprint 2 实施计划 - 核心模块实现

**版本**: v1.0  
**时间**: Week 3–6（4周）  
**目标**: 完成五大核心模块的 UI 与逻辑  
**最后更新**: 2025-11-10

---

## 🎯 Sprint 2 目标

完成五大核心模块的 UI 与逻辑（可手动刷新数据）：
- ✅ Channel Workbench（频道工作盘）
- ✅ Mission Control（态势总览）
- ✅ Ops Queue（操作队列）
- ✅ Timeline（今日时间线）
- ✅ Alerts Panel（告警面板）

---

## 👥 角色分工

| 角色 | 负责模块 | 主要任务 |
|------|---------|---------|
| **前端 A** | Channel Workbench + Mission Control | UI组件、状态管理、数据展示 |
| **前端 B** | Ops Queue + Timeline + Alerts | 表格、拖拽、实时提醒 |
| **设计** | 所有模块 | Figma高保真样稿、组件状态图 |
| **后端 B** | API补全 | `/metrics/*` 与 `/api/library/*` 端点 |

---

## 📋 任务分解

### 前端 A：Channel Workbench + Mission Control

#### Task 1: Channel Workbench 基础组件

**目标**: 实现频道卡片和列表视图

**文件结构**：
```
components/ChannelWorkbench/
├── index.tsx              # 主组件
├── ChannelCard.tsx        # 频道卡片
├── ChannelTable.tsx        # 紧凑表视图
├── ViewControls.tsx        # 视图切换控制
└── types.ts                # 类型定义
```

**实现步骤**：

1. **创建类型定义** (`types.ts`):
```typescript
export interface Channel {
  id: string
  name: string
  description?: string
  isActive: boolean
  currentTask?: {
    id: string
    status: 'pending' | 'processing' | 'uploading' | 'completed' | 'failed'
    progress?: number
  }
  nextSchedule?: string
  queueCount?: number
  lastUpdate?: string
}

export type ViewMode = 'card' | 'table'
export type DensityMode = 'comfortable' | 'standard' | 'compact'
```

2. **创建 ChannelCard 组件** (`ChannelCard.tsx`):
```typescript
'use client'

import { motion } from 'framer-motion'
import type { Channel } from './types'

interface ChannelCardProps {
  channel: Channel
  density?: 'comfortable' | 'standard' | 'compact'
  onSelect?: (channel: Channel) => void
}

export function ChannelCard({ channel, density = 'comfortable', onSelect }: ChannelCardProps) {
  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'processing': return 'bg-blue-500'
      case 'uploading': return 'bg-green-500'
      case 'failed': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  return (
    <motion.div
      className="card cursor-pointer hover:border-primary transition-all"
      onClick={() => onSelect?.(channel)}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-lg font-semibold">{channel.name}</h3>
        <div className={`w-3 h-3 rounded-full ${getStatusColor(channel.currentTask?.status)}`} />
      </div>
      
      {channel.description && (
        <p className="text-sm text-dark-text-muted mb-2">{channel.description}</p>
      )}
      
      <div className="flex items-center gap-4 text-sm">
        {channel.nextSchedule && (
          <span className="text-dark-text-muted">
            下次: {new Date(channel.nextSchedule).toLocaleString('zh-CN')}
          </span>
        )}
        {channel.queueCount !== undefined && (
          <span className="text-dark-text-muted">队列: {channel.queueCount}</span>
        )}
      </div>
    </motion.div>
  )
}
```

3. **创建 ChannelTable 组件** (`ChannelTable.tsx`):
```typescript
'use client'

import { useMemo } from 'react'
import { Virtuoso } from 'react-virtuoso'
import type { Channel } from './types'

interface ChannelTableProps {
  channels: Channel[]
  onSelect?: (channel: Channel) => void
}

export function ChannelTable({ channels, onSelect }: ChannelTableProps) {
  const shouldVirtualize = channels.length > 20

  const TableRow = ({ channel }: { channel: Channel }) => (
    <tr 
      className="border-b border-dark-border hover:bg-dark-tertiary cursor-pointer"
      onClick={() => onSelect?.(channel)}
    >
      <td className="py-3 px-4">{channel.id}</td>
      <td className="py-3 px-4">{channel.name}</td>
      <td className="py-3 px-4">
        <span className={`px-2 py-1 rounded text-xs ${
          channel.isActive ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'
        }`}>
          {channel.isActive ? '运行中' : '已停止'}
        </span>
      </td>
      <td className="py-3 px-4">{channel.nextSchedule || '-'}</td>
      <td className="py-3 px-4">{channel.queueCount || 0}</td>
    </tr>
  )

  if (shouldVirtualize) {
    return (
      <div className="overflow-auto" style={{ height: '600px' }}>
        <table className="w-full">
          <thead className="bg-dark-tertiary sticky top-0">
            <tr>
              <th className="text-left py-2 px-4">ID</th>
              <th className="text-left py-2 px-4">名称</th>
              <th className="text-left py-2 px-4">状态</th>
              <th className="text-left py-2 px-4">下次发片</th>
              <th className="text-left py-2 px-4">队列</th>
            </tr>
          </thead>
        </table>
        <Virtuoso
          data={channels}
          itemContent={(index, channel) => <TableRow key={channel.id} channel={channel} />}
          style={{ height: '600px' }}
        />
      </div>
    )
  }

  return (
    <table className="w-full">
      <thead className="bg-dark-tertiary">
        <tr>
          <th className="text-left py-2 px-4">ID</th>
          <th className="text-left py-2 px-4">名称</th>
          <th className="text-left py-2 px-4">状态</th>
          <th className="text-left py-2 px-4">下次发片</th>
          <th className="text-left py-2 px-4">队列</th>
        </tr>
      </thead>
      <tbody>
        {channels.map(channel => (
          <TableRow key={channel.id} channel={channel} />
        ))}
      </tbody>
    </table>
  )
}
```

4. **创建主组件** (`index.tsx`):
```typescript
'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChannelCard } from './ChannelCard'
import { ChannelTable } from './ChannelTable'
import { ViewControls } from './ViewControls'
import { fetchChannels } from '@/services/api'
import type { ViewMode, DensityMode } from './types'

export function ChannelWorkbench() {
  const [viewMode, setViewMode] = useState<ViewMode>('card')
  const [density, setDensity] = useState<DensityMode>('comfortable')
  const [searchQuery, setSearchQuery] = useState('')

  const { data: channels = [], isLoading } = useQuery({
    queryKey: ['channels'],
    queryFn: fetchChannels,
    staleTime: 30 * 1000,
  })

  const filteredChannels = useMemo(() => {
    if (!searchQuery) return channels
    return channels.filter(ch => 
      ch.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ch.id.toLowerCase().includes(searchQuery.toLowerCase())
    )
  }, [channels, searchQuery])

  if (isLoading) {
    return <div className="text-center py-8">Loading...</div>
  }

  return (
    <div className="space-y-4">
      <ViewControls
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        density={density}
        onDensityChange={setDensity}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />
      
      {viewMode === 'card' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredChannels.map(channel => (
            <ChannelCard 
              key={channel.id} 
              channel={channel} 
              density={density}
            />
          ))}
        </div>
      ) : (
        <ChannelTable channels={filteredChannels} />
      )}
    </div>
  )
}
```

---

#### Task 2: Mission Control 组件

**目标**: 实现态势总览指标展示

**文件结构**：
```
components/MissionControl/
├── index.tsx              # 主组件
├── HealthMetrics.tsx      # 健康指标卡片
├── QueueStatus.tsx        # 队列状态
├── TrendChart.tsx         # 趋势图表
└── types.ts
```

**实现步骤**：

1. **创建 HealthMetrics 组件**:
```typescript
'use client'

import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface HealthMetricsProps {
  successRate: number
  failedCount: number
  nextSchedule?: string
  onRetry?: () => void
}

export function HealthMetrics({ 
  successRate, 
  failedCount, 
  nextSchedule,
  onRetry 
}: HealthMetricsProps) {
  const trend = successRate > 95 ? 'up' : 'down'
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* 成功率卡片 */}
      <motion.div 
        className="card"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-dark-text-muted">成功率</span>
          {trend === 'up' ? (
            <TrendingUp className="w-4 h-4 text-green-400" />
          ) : (
            <TrendingDown className="w-4 h-4 text-red-400" />
          )}
        </div>
        <div className="text-3xl font-bold mb-2">{successRate.toFixed(1)}%</div>
        <div className="text-sm text-dark-text-muted">较昨日 ↑ 2.3%</div>
      </motion.div>

      {/* 失败任务卡片 */}
      <motion.div 
        className="card"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-dark-text-muted">失败任务</span>
          {failedCount > 0 && (
            <button 
              onClick={onRetry}
              className="text-xs px-2 py-1 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30"
            >
              批量重试
            </button>
          )}
        </div>
        <div className={`text-3xl font-bold mb-2 ${failedCount > 0 ? 'text-red-400' : 'text-green-400'}`}>
          {failedCount}
        </div>
        <div className="text-sm text-dark-text-muted">待处理</div>
      </motion.div>

      {/* 下次发片卡片 */}
      {nextSchedule && (
        <motion.div 
          className="card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <div className="text-sm text-dark-text-muted mb-2">下次发片</div>
          <div className="text-2xl font-bold mb-2">
            {new Date(nextSchedule).toLocaleTimeString('zh-CN', { 
              hour: '2-digit', 
              minute: '2-digit' 
            })}
          </div>
          <div className="text-sm text-dark-text-muted">
            {calculateCountdown(nextSchedule)}
          </div>
        </motion.div>
      )}
    </div>
  )
}

function calculateCountdown(targetDate: string): string {
  const now = new Date()
  const target = new Date(targetDate)
  const diff = target.getTime() - now.getTime()
  
  if (diff <= 0) return '已到期'
  
  const hours = Math.floor(diff / (1000 * 60 * 60))
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
  
  return `${hours}h ${minutes}m`
}
```

2. **创建 TrendChart 组件** (使用 Recharts):
```typescript
'use client'

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface TrendChartProps {
  data: Array<{ date: string; value: number }>
  title: string
}

export function TrendChart({ data, title }: TrendChartProps) {
  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis 
            dataKey="date" 
            stroke="#888"
            tick={{ fill: '#888' }}
          />
          <YAxis 
            stroke="#888"
            tick={{ fill: '#888' }}
          />
          <Tooltip 
            contentStyle={{ 
              backgroundColor: '#2a2a2a', 
              border: '1px solid #333',
              borderRadius: '8px'
            }}
          />
          <Line 
            type="monotone" 
            dataKey="value" 
            stroke="#4a9eff" 
            strokeWidth={2}
            dot={{ fill: '#4a9eff', r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
```

---

### 前端 B：Ops Queue + Timeline + Alerts

#### Task 3: Ops Queue 组件

**目标**: 实现任务队列表格和优先级操作

**文件结构**：
```
components/OpsQueue/
├── index.tsx              # 主组件
├── QueueTable.tsx         # 队列表格
├── BatchActions.tsx       # 批量操作
└── PrioritySelector.tsx    # 优先级选择
```

**关键功能**：
- TanStack Table 实现表格功能
- 拖拽调整优先级
- 批量操作（重试、暂停、删除）
- 状态动画（Framer Motion）

#### Task 4: Timeline 组件

**目标**: 实现今日时间线和拖拽改期

**文件结构**：
```
components/Timeline/
├── index.tsx              # 主组件
├── TimelineView.tsx       # 时间轴视图
├── EpisodeCard.tsx        # 期数卡片
└── ConflictDetector.tsx   # 冲突检测
```

**关键功能**：
- 时间轴可视化
- 拖拽调整期数时间
- 冲突检测与预警
- 拥堵预警

#### Task 5: Alerts Panel 组件

**目标**: 实现告警面板和 Toast 提示

**文件结构**：
```
components/AlertsPanel/
├── index.tsx              # 主组件
├── AlertList.tsx          # 告警列表
├── AlertBadge.tsx         # 未读徽章
└── Toast.tsx              # Toast 组件（或使用 react-hot-toast）
```

**关键功能**：
- 实时告警展示
- 告警确认/清除
- Toast 通知集成

---

### 设计：Figma 高保真样稿

#### Task 6: 设计稿交付

**交付物**：
1. **高保真设计稿**：
   - Mission Control 完整页面
   - Channel Workbench 卡片/表格视图
   - Ops Queue 表格视图
   - Timeline 时间轴视图
   - Alerts Panel 告警列表

2. **组件状态图**：
   - 各个组件的不同状态（loading、error、empty、normal）
   - 交互状态（hover、active、disabled）

3. **响应式设计**：
   - 桌面端（≥1024px）
   - 平板端（768-1023px）
   - 移动端（<768px）

**设计规范**：
- 使用已定义的 CSS 变量（主题色）
- 遵循 Tailwind 间距系统
- 深色主题优先

---

### 后端 B：API 补全

#### Task 7: 补全 `/metrics/*` 端点

**需要实现的端点**：

1. **`/metrics/summary`** (已部分实现，需要完善):
```python
@router.get("/summary")
async def get_summary(period: str = "24h") -> Dict:
    """
    获取指标摘要
    
    返回：
    - global_state: 全局状态统计
    - stages: 各阶段耗时统计
    - trends: 趋势数据（7日）
    """
    # 从 schedule_master.json 读取数据
    # 计算成功率、失败数等
    # 返回格式化数据
    pass
```

2. **`/metrics/episodes`** (已部分实现，需要完善):
```python
@router.get("/episodes")
async def get_episodes(
    status: Optional[str] = None,
    limit: int = 100
) -> Dict:
    """
    获取期数列表
    
    查询参数：
    - status: 筛选状态（pending, completed, error等）
    - limit: 返回数量限制
    """
    # 从 schedule_master.json 读取
    # 支持状态筛选
    # 返回格式化数据
    pass
```

3. **`/metrics/events`** (需要实现):
```python
@router.get("/events")
async def get_events(
    limit: int = 50,
    since: Optional[str] = None
) -> Dict:
    """
    获取最近事件流
    
    查询参数：
    - limit: 返回数量
    - since: 起始时间（ISO格式）
    """
    # 从日志或数据库读取事件
    # 支持时间筛选
    # 返回格式化数据
    pass
```

#### Task 8: 补全 `/api/library/*` 端点

**需要实现的端点**：

1. **`/api/library/songs`** (已实现，需要增强):
```python
@router.get("/songs")
async def list_songs(
    channel_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
) -> List[Dict]:
    """
    获取歌曲列表
    
    查询参数：
    - channel_id: 频道ID（未来支持）
    - search: 搜索关键词
    - limit: 返回数量限制
    """
    # 支持搜索功能
    # 支持分页
    # 返回格式化数据
    pass
```

2. **`/api/library/images`** (已实现，需要增强):
```python
@router.get("/images")
async def list_images(
    channel_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
) -> List[Dict]:
    """
    获取图片列表
    
    查询参数：
    - channel_id: 频道ID（未来支持）
    - search: 搜索关键词
    - limit: 返回数量限制
    """
    # 支持搜索功能
    # 支持分页
    # 返回格式化数据
    pass
```

---

## 🔄 React Query 集成

### 数据缓存配置

**创建 Query Client Provider** (`app/providers.tsx`):
```typescript
'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30 * 1000, // 30秒
        cacheTime: 5 * 60 * 1000, // 5分钟
        refetchOnWindowFocus: false,
        retry: 1,
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

**在 layout 中使用** (`app/layout.tsx`):
```typescript
import { Providers } from './providers'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  )
}
```

---

## ✅ 验收条件

### 功能验收

- [x] **Channel Workbench**: 
  - [ ] 卡片视图正常渲染
  - [ ] 表格视图正常渲染
  - [ ] 视图切换功能正常
  - [ ] 搜索/筛选功能正常

- [x] **Mission Control**:
  - [ ] 健康指标正确计算和显示
  - [ ] 趋势图表正常渲染
  - [ ] 数据刷新功能正常

- [x] **Ops Queue**:
  - [ ] 队列表格正常渲染
  - [ ] 批量操作功能正常
  - [ ] 优先级调整功能正常

- [x] **Timeline**:
  - [ ] 时间轴正常渲染
  - [ ] 拖拽改期功能正常
  - [ ] 冲突检测功能正常

- [x] **Alerts Panel**:
  - [ ] 告警列表正常渲染
  - [ ] Toast 提示功能正常
  - [ ] 告警确认功能正常

### 代码质量验收

- [ ] 所有组件通过 TypeScript 类型检查
- [ ] ESLint 检查无错误
- [ ] Prettier 格式化通过
- [ ] 组件有适当的错误处理

### 样式验收

- [ ] 各模块样式符合 Figma 设计稿
- [ ] 响应式布局正常工作
- [ ] 动画效果流畅

### 测试验收

- [ ] 基础 E2E 测试通过
- [ ] 关键功能有单元测试覆盖

---

## 📅 时间安排

| 周次 | 任务 | 负责人 |
|------|------|--------|
| **Week 3** | Channel Workbench + Mission Control 基础实现 | 前端 A |
| **Week 3** | Ops Queue 基础实现 | 前端 B |
| **Week 4** | Timeline + Alerts 基础实现 | 前端 B |
| **Week 4** | API 端点补全 | 后端 B |
| **Week 5** | React Query 集成 + 数据同步 | 前端 A + B |
| **Week 5** | 设计稿交付与样式调整 | 设计 |
| **Week 6** | 测试、优化、验收 | 全员 |

---

## 📚 参考文档

- [产品设计愿景](./WEB_PRODUCT_DESIGN_VISION.md) - 设计规范
- [交互设计与数据规范](./WEB_DASHBOARD_DESIGN_SPEC.md) - 详细交互规范
- [开发规范](./DEVELOPMENT_STANDARDS.md) - 代码规范

---

**文档维护**: 本文档应随开发进度持续更新。  
**问题反馈**: 如有疑问，请联系对应负责人。

