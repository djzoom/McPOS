# Kat Rec Web 前端选型与架构方案

**版本**: v0.1（配合主界面信息架构 v1）  
**目标**: 支撑 10→100 频道的可扩展仪表板体系，兼顾实时状态、资产管理与高并发数据可视化。  
**最后更新**: 2025-11-10

---

## 一、总体设计目标

### 核心原则

1. **现代化、模块化、渐进增强**：以 React 组件体系为核心，兼顾 SPA 与微前端的可扩展性
2. **高性能与实时响应**：前后端解耦，通过 WebSocket 与增量 API 更新支持实时监控
3. **低耦合 + 可重用**：所有模块（频道卡、队列、排播、告警）均可独立开发与部署
4. **多租户可扩展**：为未来 100+ 频道的管理与分组提供虚拟化渲染与分区加载
5. **统一状态与接口层**：数据与状态源一致，前端只做渲染与轻逻辑

### 当前状态 vs 目标状态

| 维度 | 当前实现 | 目标架构 | 迁移优先级 |
|------|---------|---------|-----------|
| 框架版本 | Next.js 14 + React 18 | Next.js 15 + React 19 | P1 |
| 状态管理 | 本地 useState | Zustand + React Query | P1 |
| 实时通信 | 轮询（30s间隔） | WebSocket | P1 |
| 表格组件 | 原生HTML表格 | TanStack Table + React Virtuoso | P2 |
| 数据可视化 | 无 | Recharts + D3.js | P3 |
| 国际化 | 硬编码中文 | next-intl | P2 |
| 测试覆盖 | 无 | Vitest + Playwright | P2 |

---

## 二、前端选型

### 核心框架

#### Next.js 15 (App Router)
- **选择理由**：
  - 全栈渲染框架，支持 SSR + SSG + ISR
  - SEO 与首屏性能兼顾
  - 内置 API Routes，简化开发
  - 优秀的构建优化与代码分割

#### React 19 + TypeScript
- **选择理由**：
  - 组件化开发基础，保证类型安全与复用性
  - 服务端组件支持（React 19新特性）
  - 类型系统确保代码质量

**当前状态**: ✅ Next.js 14 + React 18（需升级）

### 状态管理

#### Zustand + React Query (TanStack Query)

**Zustand** - 轻量全局状态
- **用途**：频道选择、UI主题、告警计数等全局状态
- **优势**：体积小（~1KB），API简洁，性能优秀
- **适用场景**：
  ```typescript
  // 示例：频道选择状态
  interface ChannelStore {
    selectedChannelId: string | null
    setSelectedChannel: (id: string) => void
    theme: 'light' | 'dark'
    toggleTheme: () => void
  }
  ```

**React Query** - API 数据层缓存
- **用途**：API 数据缓存 + 失效重载机制
- **优势**：
  - 自动缓存与后台更新
  - 请求去重与重试机制
  - 乐观更新支持
- **适用场景**：
  ```typescript
  // 示例：歌库数据查询
  const { data: songs, isLoading } = useQuery({
    queryKey: ['songs', channelId],
    queryFn: () => fetchSongs(channelId),
    staleTime: 5 * 60 * 1000, // 5分钟缓存
    refetchInterval: 30000, // 30秒轮询（WebSocket替代后移除）
  })
  ```

**当前状态**: ❌ 未实现（需新增）

### 样式与主题

#### Tailwind CSS + ShadCN/UI

**Tailwind CSS**
- **用途**：原子化样式，保证一致间距与快速响应式布局
- **当前状态**: ✅ 已配置

**ShadCN/UI**
- **用途**：一致的组件基础库
- **组件库包含**：
  - Tabs（标签页）
  - Cards（卡片）
  - Modals（模态框）
  - DataTable（数据表格）
  - Dialogs、Dropdowns等
- **优势**：
  - 可定制主题（Tailwind配置）
  - 可访问性（ARIA支持）
  - 类型安全（TypeScript）
- **安装**：
  ```bash
  npx shadcn-ui@latest init
  npx shadcn-ui@latest add tabs card table dialog
  ```

**当前状态**: ⚠️ Tailwind已配置，ShadCN未集成

### 可视化层

#### Recharts + D3.js (小部分)

**Recharts**
- **用途**：轻量化图表与趋势可视化
- **图表类型**：
  - Line Chart（趋势线）
  - Bar Chart（柱状图）
  - Pie Chart（饼图）
  - Area Chart（面积图）
- **适用场景**：
  - 期数完成趋势
  - 各阶段耗时统计
  - 频道任务分布

**D3.js**
- **用途**：复杂数据可视化（小部分）
- **适用场景**：自定义图表、数据流图

**当前状态**: ❌ 未实现

#### Framer Motion
- **用途**：动效层（组件过渡、数据刷新动画）
- **适用场景**：
  - 数据更新时的过渡动画
  - 模态框进入/退出动画
  - 列表项增删动画
- **示例**：
  ```typescript
  import { motion } from 'framer-motion'
  
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.3 }}
  >
    {content}
  </motion.div>
  ```

**当前状态**: ❌ 未实现

### 表格与虚拟化

#### TanStack Table + React Virtuoso

**TanStack Table**
- **用途**：强大的表格功能
- **功能**：
  - 排序、筛选、分页
  - 列拖拽与调整
  - 行选择
  - 服务端分页支持
- **适用场景**：
  - 歌库/图库列表
  - 期数列表
  - 任务队列

**React Virtuoso**
- **用途**：大规模数据虚拟滚动
- **适用场景**：
  - 频道数量 > 20 时自动启用
  - 支持数千条任务记录
- **优势**：
  - 只渲染可见区域
  - 支持动态高度
  - 性能优秀

**当前状态**: ❌ 未实现（当前使用原生HTML表格）

### 通信机制

#### RESTful + WebSocket

**REST API**（当前实现）
- **用途**：基础数据加载
- **端点**：
  - `/api/library/songs`
  - `/api/library/images`
  - `/api/status`
  - `/api/channel`

**WebSocket**（目标实现）
- **用途**：推送任务进度、告警、状态变更
- **实现方式**：通过 FastAPI WebSocket 端点
- **端点规划**：
  - `/ws/events` - 通用事件流
  - `/ws/alerts` - 告警推送
  - `/ws/channel/{channel_id}/status` - 频道状态实时更新
- **前端集成**：
  ```typescript
  import { useWebSocket } from '@/hooks/useWebSocket'
  
  const { data, isConnected } = useWebSocket('/ws/events', {
    onMessage: (event) => {
      // 更新React Query缓存
      queryClient.setQueryData(['status'], event.data)
    }
  })
  ```

**当前状态**: ⚠️ REST已实现，WebSocket未实现（当前使用30s轮询）

### 国际化与本地化

#### Next-intl

- **用途**：支持中英双语与时区本地化
- **配置**：
  ```typescript
  // messages/zh.json
  {
    "dashboard": {
      "title": "Kat Rec Web 控制中心",
      "songs": "歌库",
      "images": "图库"
    }
  }
  
  // messages/en.json
  {
    "dashboard": {
      "title": "Kat Rec Web Control Center",
      "songs": "Songs",
      "images": "Images"
    }
  }
  ```

**当前状态**: ❌ 未实现（硬编码中文）

---

## 三、前端架构层次

### 架构分层图

```
┌─────────────────────────────────────────────────────────┐
│ [用户界面层]                                              │
│   └── 组件系统                                            │
│        ├── ChannelCard / ChannelGrid                     │
│        ├── OpsQueue / QueueList                          │
│        ├── Timeline / ScheduleView                       │
│        ├── Alerts / NotificationCenter                   │
│        └── Libraries (Songs/Images/Programs)            │
│                                                          │
│ [状态与数据层]                                            │
│   ├── Zustand 全局状态                                   │
│   │     ├── UI 状态（侧边栏、主题）                       │
│   │     ├── 选中频道                                     │
│   │     └── 告警计数                                     │
│   │                                                      │
│   ├── React Query（API 数据缓存）                        │
│   │     ├── 频道列表缓存                                 │
│   │     ├── 歌库/图库缓存                                │
│   │     └── 期数状态缓存                                 │
│   │                                                      │
│   └── WebSocket 实时事件总线                             │
│         ├── 状态更新推送                                 │
│         ├── 告警推送                                     │
│         └── 任务进度推送                                 │
│                                                          │
│ [通信层]                                                  │
│   ├── REST API：/api/*                                   │
│   └── WS 通道：/ws/events, /ws/alerts                    │
│                                                          │
│ [后端 FastAPI 服务]                                       │
└─────────────────────────────────────────────────────────┘
```

### 数据流逻辑

#### 场景1：用户操作触发数据更新

```
用户点击"刷新歌库"
    ↓
Zustand 更新 loading 状态
    ↓
触发 React Query 失效
    ↓
重新调用 fetchSongs() API
    ↓
更新 React Query 缓存
    ↓
组件自动重新渲染
```

#### 场景2：后端状态变更实时推送

```
后端任务完成
    ↓
WebSocket 推送事件
    ↓
useWebSocket Hook 接收
    ↓
更新 React Query 缓存
    ↓
相关组件（Queue/Timeline）自动更新
    ↓
可选：Framer Motion 过渡动画
```

#### 场景3：失败任务告警处理

```
任务失败
    ↓
WebSocket /ws/alerts 推送
    ↓
Alerts 模块弹出通知
    ↓
用户点击"重试"
    ↓
调用 /api/retry/{task_id}
    ↓
更新任务状态
```

---

## 四、代码组织

### 目录结构（目标）

```
kat_rec_web/frontend/
├── app/                      # Next.js App Router
│   ├── (dashboard)/          # 仪表板路由组
│   │   ├── page.tsx         # 主仪表板
│   │   ├── library/          # 资产库管理
│   │   ├── scheduler/       # 排播管理
│   │   └── analytics/       # 数据分析
│   ├── api/                  # API Routes（可选）
│   ├── layout.tsx           # 根布局
│   └── globals.css          # 全局样式
│
├── components/               # UI 组件
│   ├── ChannelCard/         # 频道卡片
│   │   ├── ChannelCard.tsx
│   │   └── ChannelGrid.tsx # 频道网格（虚拟化）
│   ├── OpsQueue/            # 操作队列
│   │   ├── QueueList.tsx
│   │   └── QueueItem.tsx
│   ├── Timeline/             # 时间线/排播视图
│   │   ├── TimelineView.tsx
│   │   └── EpisodeCard.tsx
│   ├── Alerts/               # 告警中心
│   │   ├── AlertCenter.tsx
│   │   └── AlertItem.tsx
│   └── Libraries/            # 资产库组件
│       ├── SongsLibrary.tsx
│       ├── ImagesLibrary.tsx
│       └── ProgramsLibrary.tsx
│
├── services/                 # API 封装层
│   ├── apiClient.ts          # Axios/Fetch 封装
│   ├── websocket.ts          # WebSocket 客户端
│   └── queries/              # React Query 查询定义
│       ├── channels.ts
│       ├── library.ts
│       └── episodes.ts
│
├── stores/                    # Zustand 状态
│   ├── channelStore.ts      # 频道选择状态
│   ├── uiStore.ts            # UI状态（侧边栏、主题）
│   └── alertStore.ts         # 告警状态
│
├── hooks/                     # 自定义 Hook
│   ├── useWebSocket.ts       # WebSocket Hook
│   ├── useChannel.ts         # 频道相关逻辑
│   └── useVirtualScroll.ts  # 虚拟滚动Hook
│
├── utils/                     # 工具函数
│   ├── formatters.ts         # 数据格式化
│   ├── validators.ts         # 表单验证
│   └── constants.ts         # 常量定义
│
├── styles/                    # 样式配置
│   ├── tailwind.config.js   # Tailwind 配置
│   └── theme.ts              # 主题Token配置
│
├── messages/                  # 国际化消息
│   ├── zh.json
│   └── en.json
│
└── types/                     # TypeScript 类型定义
    ├── api.ts                # API 响应类型
    ├── channel.ts            # 频道类型
    └── library.ts            # 资产库类型
```

**当前状态**: ⚠️ 部分目录已存在，需重构组织

---

## 五、性能优化策略

### 懒加载与分区渲染

**实现方式**：
```typescript
// 动态导入大型组件
const MissionControl = dynamic(() => import('@/components/MissionControl'), {
  loading: () => <Skeleton />,
  ssr: false // 如果不需要SSR
})

const ChannelWorkbench = dynamic(() => import('@/components/ChannelWorkbench'))
```

**模块加载策略**：
- 初始加载：Dashboard核心（ChannelCard、UploadStatus）
- 按需加载：Library、Scheduler、Analytics
- 懒加载：大型图表、虚拟化表格

### 虚拟滚动与批量渲染

**实现示例**：
```typescript
import { Virtuoso } from 'react-virtuoso'

// 频道数量 > 20 时自动启用
{channels.length > 20 ? (
  <Virtuoso
    data={channels}
    itemContent={(index, channel) => (
      <ChannelCard channel={channel} />
    )}
    style={{ height: '600px' }}
  />
) : (
  channels.map(channel => <ChannelCard key={channel.id} channel={channel} />)
)}
```

### 数据分片缓存

**React Query Key 命名规范**：
```typescript
// 按模块、频道、时间片命名
queryKey: ['library', 'songs', channelId, dateRange]
queryKey: ['episodes', channelId, status, page]
queryKey: ['metrics', 'summary', channelId, '24h']
```

### 渐进更新

**策略**：
1. **首次加载**：SSR 提供快照数据
2. **后续更新**：WebSocket 增量推送
3. **缓存失效**：按模块设置不同的 staleTime

```typescript
// SSR 数据预加载
export async function getServerSideProps() {
  const initialData = await fetchStatus()
  return { props: { initialData } }
}

// 客户端增量更新
const { data } = useQuery({
  queryKey: ['status'],
  queryFn: fetchStatus,
  initialData: props.initialData, // 使用SSR数据
  staleTime: 1000, // 1秒后失效，触发WebSocket更新
})
```

### 批量 API 合并请求

**当前实现**：
```typescript
// 并行请求多个端点
const [statusData, channelData] = await Promise.all([
  fetchStatus(),
  fetchChannel()
])
```

**优化方案**：
- 使用 `/metrics/summary` 组合数据，减少网络开销
- 后端提供批量查询端点：`/api/batch?endpoints=status,channel,library`

---

## 六、微前端与扩展性

### 微前端架构规划

**当频道规模 >50 时，可拆分为独立微前端子应用**：

#### 方案A：Module Federation（推荐）

```
kat-rec-dashboard (主应用)
├── /dashboard      # 仪表板核心（宿主）
├── /library        # 资产库管理（微前端）
├── /scheduler      # 排播管理（微前端）
└── /analytics      # 数据分析（微前端）
```

**优势**：
- 独立部署与版本管理
- 共享依赖（React、组件库）
- 运行时集成

#### 方案B：Nx Monorepo

```
kat-rec-workspace/
├── apps/
│   ├── dashboard/
│   ├── library/
│   └── scheduler/
├── libs/
│   ├── shared-components/
│   ├── shared-utils/
│   └── shared-types/
```

**优势**：
- 代码共享与依赖管理
- 统一构建与测试
- 更好的开发体验

### 主题与品牌层可重用

**未来支持为不同频道品牌加载独立主题**：

```typescript
// Theme Tokens 配置
const themes = {
  default: {
    primary: '#4a9eff',
    background: '#1a1a1a',
    // ...
  },
  channel_a: {
    primary: '#ff6b6b',
    background: '#f8f9fa',
    // ...
  }
}

// 动态加载主题
const theme = useChannelTheme(selectedChannelId)
```

---

## 七、测试与部署

### 测试栈

#### 单元测试
- **Vitest**：快速、兼容Vite
- **React Testing Library**：组件测试

```typescript
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ChannelCard from '@/components/ChannelCard'

describe('ChannelCard', () => {
  it('renders channel name', () => {
    render(<ChannelCard channel={{ id: '1', name: 'Test Channel' }} />)
    expect(screen.getByText('Test Channel')).toBeInTheDocument()
  })
})
```

#### 端到端测试
- **Playwright**：跨浏览器E2E测试

```typescript
import { test, expect } from '@playwright/test'

test('dashboard loads correctly', async ({ page }) => {
  await page.goto('http://localhost:3000')
  await expect(page.locator('h1')).toContainText('Kat Rec Web Control Center')
})
```

**当前状态**: ❌ 未实现

### 构建与部署

#### 构建
- **Vercel**（推荐）：零配置部署，自动优化
- **Docker multi-stage build**（备选）：容器化部署

```dockerfile
# Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
CMD ["npm", "start"]
```

#### 持续集成
- **GitHub Actions**：自动化流水线
  ```yaml
  # .github/workflows/ci.yml
  - Lint: ESLint检查
  - Type Check: TypeScript类型检查
  - Test: Vitest单元测试
  - E2E: Playwright端到端测试
  - Deploy: 自动部署到Vercel
  ```

#### 监控
- **Sentry**：错误追踪与性能监控
- **Vercel Analytics**：Web Vitals监控

**当前状态**: ⚠️ 部分实现（Docker配置存在）

---

## 八、推荐依赖清单

### 核心依赖

| 模块 | 依赖 | 用途 | 版本 | 状态 |
|------|------|------|------|------|
| **框架** | Next.js | SSR/SSG/ISR 统一框架 | 15.x | ⚠️ 需升级（当前14.x） |
| | React | UI框架 | 19.x | ⚠️ 需升级（当前18.x） |
| | TypeScript | 类型系统 | 5.x | ✅ 已配置 |
| **状态** | Zustand | 轻量全局状态 | ^4.4.x | ❌ 需新增 |
| | @tanstack/react-query | API数据缓存 | ^5.x | ❌ 需新增 |
| **样式** | Tailwind CSS | 原子化样式 | ^3.x | ✅ 已配置 |
| | shadcn/ui | 组件库 | latest | ❌ 需新增 |
| **动画** | framer-motion | 动效与状态切换 | ^11.x | ❌ 需新增 |
| **表格** | @tanstack/react-table | 表格功能 | ^8.x | ❌ 需新增 |
| | react-virtuoso | 虚拟滚动 | ^4.x | ❌ 需新增 |
| **图表** | recharts | 指标趋势展示 | ^2.x | ❌ 需新增 |
| **国际化** | next-intl | 中英切换与时区本地化 | ^3.x | ❌ 需新增 |
| **测试** | vitest | 单元测试 | ^1.x | ❌ 需新增 |
| | @testing-library/react | 组件测试 | ^14.x | ❌ 需新增 |
| | @playwright/test | E2E测试 | ^1.x | ❌ 需新增 |
| **工具** | axios | HTTP客户端 | ^1.x | ✅ 已配置 |

### 安装命令

```bash
# 核心依赖
npm install next@latest react@latest react-dom@latest
npm install zustand @tanstack/react-query
npm install framer-motion
npm install @tanstack/react-table react-virtuoso
npm install recharts
npm install next-intl

# ShadCN UI（需要先初始化）
npx shadcn-ui@latest init
npx shadcn-ui@latest add tabs card table dialog dropdown

# 开发依赖
npm install -D vitest @testing-library/react @playwright/test
```

---

## 九、迁移路径

### 阶段1：基础升级（P1，2周）

1. **升级框架版本**
   - Next.js 14 → 15
   - React 18 → 19
   - 测试兼容性

2. **引入状态管理**
   - 安装 Zustand + React Query
   - 重构现有 useState 为 Zustand
   - 重构 API 调用为 React Query

3. **WebSocket 集成**
   - 后端实现 WebSocket 端点
   - 前端集成 useWebSocket Hook
   - 替换30s轮询为实时推送

### 阶段2：组件库与表格（P2，2周）

1. **集成 ShadCN UI**
   - 初始化 ShadCN
   - 替换现有组件为 ShadCN 组件
   - 统一设计语言

2. **表格优化**
   - 集成 TanStack Table
   - 添加排序、筛选、分页功能
   - 频道数 > 20 时启用虚拟滚动

3. **国际化**
   - 集成 next-intl
   - 提取所有硬编码文本
   - 实现中英切换

### 阶段3：可视化与动画（P3，1周）

1. **数据可视化**
   - 集成 Recharts
   - 实现指标趋势图表
   - 添加数据分析视图

2. **动画效果**
   - 集成 Framer Motion
   - 添加数据更新动画
   - 优化用户体验

### 阶段4：测试与监控（P2，1周）

1. **测试覆盖**
   - 配置 Vitest
   - 编写单元测试
   - 配置 Playwright E2E测试

2. **监控集成**
   - 集成 Sentry
   - 配置错误追踪
   - 性能监控

### 阶段5：微前端准备（P3，未来）

1. **架构评估**
   - 评估频道规模
   - 决定微前端方案
   - 规划拆分策略

---

## 十、总结

### 架构核心理念

- **清晰分层**：UI层、状态层、通信层分离
- **组件自治**：每个模块可独立开发与部署
- **事件驱动**：WebSocket实时推送，React Query缓存更新
- **虚拟化渲染**：大规模数据场景下的性能保证

### 短期目标（10频道阶段）

- ✅ 实现 SSR + WS 实时更新
- ✅ 高性能表格与虚拟滚动
- ✅ 统一组件库与设计语言

### 中期目标（100频道阶段）

- ⏳ 引入微前端与多实例分流
- ⏳ 维持 <1s UI 更新延迟
- ⏳ 支持多租户与品牌主题

### 长期目标

- 🔮 形成统一的 Kat Rec Dashboard Framework
- 🔮 可复用到其他品牌与频道体系
- 🔮 开源或商业化组件库

---

## 附录：相关文档

- [数据流与状态管理设计](./WEB_STATE_MANAGEMENT_DESIGN.md) - Zustand状态模型与数据流
- [交互设计与数据规范](./WEB_DASHBOARD_DESIGN_SPEC.md) - 产品与设计规范
- [架构文档](./ARCHITECTURE.md) - 系统整体架构
- [库管理指南](./LIBRARY_MANAGEMENT.md) - 歌库/图库管理
- [排播表指南](./SCHEDULE_MASTER_GUIDE.md) - 期数管理

---

**文档维护**: 本文档应随技术选型和架构演进持续更新。  
**反馈渠道**: 如有疑问或建议，请联系前端架构团队。

