# Kat Rec Workbench 交互与数据流总览

## 📐 系统架构总览

```mermaid
graph TB
    subgraph "数据层"
        API[Backend APIs<br/>/api/t2r/*<br/>/api/mcrb/*]
        WS[WebSocket<br/>/ws/status]
    end
    
    subgraph "状态管理层 (Zustand)"
        Store[ScheduleStore<br/>SSOT 单一真实数据源]
        Store --> |channels<br/>events<br/>focusDate<br/>dateRange| Data[统一状态模型]
    end
    
    subgraph "数据加载层"
        Hydrator[useScheduleHydrator<br/>React Query]
        Bridge[useScheduleWebSocketBridge<br/>WebSocket Bridge]
    end
    
    subgraph "视图层"
        Overview[全局总览<br/>/mcrb/overview]
        Channel[频道看板<br/>/mcrb/channel/:id]
        TaskPanel[任务面板<br/>TaskPanel]
    end
    
    API -->|fetchT2REpisodes<br/>fetchT2RChannel| Hydrator
    Hydrator -->|hydrate()| Store
    WS -->|实时事件| Bridge
    Bridge -->|patchEvent()<br/>markEventStatus()| Store
    
    Store -->|visibleEvents()<br/>statusCounts()| Overview
    Store -->|visibleEvents(channelId)| Channel
    Store -->|selectedEvent| TaskPanel
    
    Overview -->|点击单元格| Channel
    Channel -->|Enter/点击| TaskPanel
    TaskPanel -->|Plan/Render/Upload/Verify| API
    
    style Store fill:#4a9eff,color:#fff
    style API fill:#4ade80,color:#fff
    style WS fill:#fbbf24,color:#000
```

## 🔄 数据流详解

### 1. 初始化数据流

```mermaid
sequenceDiagram
    participant App as 应用启动
    participant Hydrator as useScheduleHydrator
    participant Query as React Query
    participant API as Backend API
    participant Store as ScheduleStore
    
    App->>Hydrator: 组件挂载
    Hydrator->>Query: useQuery(['t2r-episodes'])
    Query->>API: GET /api/t2r/episodes
    API-->>Query: T2REpisodesResponse
    Hydrator->>Hydrator: transformEpisode()
    Hydrator->>Store: hydrate({ events, channels })
    Store->>Store: 更新 events, channels
    Note over Store: 状态变更触发组件重渲染
```

### 2. WebSocket 实时更新流

```mermaid
sequenceDiagram
    participant WS as WebSocket Server
    participant Bridge as useScheduleWebSocketBridge
    participant Store as ScheduleStore
    participant UI as 视图组件
    
    WS->>Bridge: runbook_stage_update
    Bridge->>Bridge: 解析事件类型
    Bridge->>Store: markEventStatus(eventId, 'rendering')
    Store->>Store: 更新事件状态
    Store->>UI: 状态变更通知
    UI->>UI: 自动重渲染
    Note over UI: Overview 和 Channel 视图<br/>同步更新
    
    WS->>Bridge: upload_progress
    Bridge->>Store: markEventStatus(eventId, 'uploaded')
    Bridge->>Store: patchEvent(eventId, { kpis })
    
    WS->>Bridge: verify_result
    Bridge->>Store: markEventStatus(eventId, 'verified')
    Bridge->>Store: patchEvent(eventId, { issues: [] })
```

### 3. 用户操作流

```mermaid
sequenceDiagram
    participant User as 用户
    participant Overview as 总览页面
    participant Channel as 频道看板
    participant TaskPanel as 任务面板
    participant API as Backend API
    participant Store as ScheduleStore
    
    User->>Overview: 点击单元格 (channelId, date)
    Overview->>Channel: router.push(/mcrb/channel/:id?focus=date)
    Channel->>Store: setFocus(channelId, date)
    Store->>Channel: 更新 focusDate
    
    User->>Channel: 方向键 ↑↓ 导航
    Channel->>Store: setFocus(channelId, newDate)
    Channel->>Channel: 滚动到聚焦卡片
    
    User->>Channel: Enter 或点击卡片
    Channel->>TaskPanel: 打开抽屉 (selectedEventId)
    
    User->>TaskPanel: 点击 "Plan" 按钮
    TaskPanel->>Store: 乐观更新 (status: 'planned')
    TaskPanel->>API: POST /api/t2r/plan
    API-->>TaskPanel: PlanResponse
    alt 成功
        TaskPanel->>Store: markEventStatus('planned')
    else 失败
        TaskPanel->>Store: markEventStatus('draft') (回滚)
    end
    
    Note over Store,API: 成功后 WebSocket 推送<br/>进一步确认状态
```

## 🏗️ 组件层次结构

```mermaid
graph TD
    subgraph "路由层"
        Layout[app/(mcrb)/layout.tsx]
        OverviewPage[app/(mcrb)/mcrb/overview/page.tsx]
        ChannelPage[app/(mcrb)/mcrb/channel/[id]/page.tsx]
    end
    
    subgraph "布局组件"
        GlobalNav[GlobalNav<br/>频道选择器<br/>窗口切换器]
    end
    
    subgraph "总览视图"
        OverviewGrid[OverviewGrid<br/>热力图网格]
        StatusLegend[StatusLegend<br/>状态分布]
        CellTooltip[CellTooltip<br/>悬停提示]
    end
    
    subgraph "频道视图"
        ChannelTimeline[ChannelTimeline<br/>时间线卡片列表]
        TaskPanel[TaskPanel<br/>任务操作抽屉]
    end
    
    Layout --> GlobalNav
    Layout --> OverviewPage
    Layout --> ChannelPage
    
    OverviewPage --> OverviewGrid
    OverviewPage --> StatusLegend
    OverviewGrid --> CellTooltip
    
    ChannelPage --> ChannelTimeline
    ChannelPage --> TaskPanel
    
    style Layout fill:#2a2a2a,color:#fff
    style OverviewPage fill:#4a9eff,color:#fff
    style ChannelPage fill:#4ade80,color:#fff
```

## 📊 状态管理模型

### ScheduleStore 结构

```typescript
interface ScheduleStore {
  // 核心数据
  channels: string[]                    // 频道 ID 列表
  events: Record<string, ScheduleEvent[]>  // 按频道分组的事件
  selectedChannel: string | null
  focusDate: string | null              // 聚焦的日期
  dateRange: DateRange                  // 时间窗口
  
  // 派生数据（计算属性）
  visibleEvents(channelId?): ScheduleEvent[]
  channelSummaries(): ChannelSummary[]
  statusCounts(channelId?): Record<Status, number>
  
  // 操作方法
  hydrate(data): void                   // 初始化数据
  setDateRange(range): void             // 设置时间窗口
  setFocus(channelId, date): void      // 设置聚焦
  upsertEvents(channelId, events): void // 更新/插入事件
  patchEvent(eventId, updates): void   // 部分更新事件
  markEventStatus(eventId, status): void // 标记状态
}
```

### 事件数据模型

```mermaid
classDiagram
    class ScheduleEvent {
        +string id
        +string channelId
        +string date
        +string title
        +number durationSec
        +number? bpm
        +AssetBundle assets
        +ScheduleEventStatus status
        +string[] issues
        +KPIs? kpis
    }
    
    class AssetBundle {
        +string? cover
        +string? audio
        +string? description
        +string? captions
    }
    
    class KPIs {
        +number? successRate
        +string? lastRunAt
    }
    
    ScheduleEvent --> AssetBundle
    ScheduleEvent --> KPIs
```

## 🎯 交互路径

### 路径 1: 总览 → 频道看板

```mermaid
graph LR
    A[总览网格] -->|点击单元格<br/>channelId + date| B[频道看板]
    B -->|URL 更新<br/>?focus=date| C[聚焦事件卡片]
    C -->|自动滚动<br/>高亮显示| D[键盘导航就绪]
    
    style A fill:#4a9eff,color:#fff
    style B fill:#4ade80,color:#fff
```

### 路径 2: 键盘导航

```mermaid
stateDiagram-v2
    [*] --> 频道看板
    
    频道看板 --> 上移: ArrowUp
    频道看板 --> 下移: ArrowDown
    频道看板 --> 打开抽屉: Enter
    频道看板 --> 返回总览: ArrowLeft
    
    上移 --> 频道看板: 更新 focusDate
    下移 --> 频道看板: 更新 focusDate
    
    打开抽屉 --> 任务面板
    任务面板 --> 频道看板: ESC
    任务面板 --> 执行操作: Plan/Render/Upload/Verify
    
    执行操作 --> 任务面板: 操作完成
    执行操作 --> 更新Store: 乐观更新 + API调用
    更新Store --> 任务面板: 状态同步
```

### 路径 3: 任务操作流程

```mermaid
flowchart TD
    Start[点击操作按钮] --> Optimistic{乐观更新 Store}
    Optimistic --> API[调用后端 API]
    API --> Success{API 成功?}
    
    Success -->|是| Confirm[确认更新状态]
    Success -->|否| Rollback[回滚到原状态]
    
    Confirm --> Toast[显示成功提示]
    Rollback --> ErrorToast[显示错误提示]
    
    Toast --> WS[等待 WebSocket 确认]
    WS --> FinalUpdate[最终状态同步]
    
    style Optimistic fill:#fbbf24,color:#000
    style Success fill:#4ade80,color:#fff
    style Rollback fill:#f87171,color:#fff
```

## 🔌 数据同步机制

### 三种数据源

```mermaid
graph LR
    subgraph "1. 初始加载"
        A1[React Query] -->|并行请求| A2[fetchT2REpisodes]
        A2 -->|hydrate| Store[ScheduleStore]
    end
    
    subgraph "2. 用户操作"
        B1[TaskPanel] -->|乐观更新| Store
        B1 -->|API 调用| B2[Backend API]
        B2 -->|响应| B1
        B1 -->|确认/回滚| Store
    end
    
    subgraph "3. 实时推送"
        C1[WebSocket] -->|事件流| C2[Bridge]
        C2 -->|patchEvent| Store
    end
    
    Store -->|统一状态| UI[所有视图组件]
    
    style Store fill:#4a9eff,color:#fff
    style A1 fill:#60a5fa,color:#fff
    style C1 fill:#fbbf24,color:#000
```

## 🎨 视觉状态映射

### 状态 → 颜色 → 视图

```mermaid
graph LR
    subgraph "状态类型"
        S1[draft]
        S2[planned]
        S3[rendering]
        S4[ready]
        S5[uploaded]
        S6[verified]
        S7[failed]
    end
    
    subgraph "颜色系统"
        C1[designTokens.ts<br/>statusColors]
        C2[HSL 颜色值<br/>+ 透明度]
        C3[资产完备度调整<br/>饱和度/亮度]
    end
    
    subgraph "视图应用"
        V1[OverviewGrid<br/>单元格背景]
        V2[ChannelTimeline<br/>卡片边框]
        V3[StatusLegend<br/>图例指示器]
    end
    
    S1 --> C1
    S2 --> C1
    S3 --> C1
    S4 --> C1
    S5 --> C1
    S6 --> C1
    S7 --> C1
    
    C1 --> C2
    C2 --> C3
    
    C3 --> V1
    C3 --> V2
    C3 --> V3
```

## 🔐 关键设计原则

### 1. SSOT (Single Source of Truth)
- **ScheduleStore** 是唯一的状态源
- 所有视图从 Store 读取，不保留本地状态
- API 响应和 WebSocket 事件都写入 Store

### 2. 乐观更新
- 用户操作立即更新 UI
- API 调用在后台进行
- 失败时回滚，成功时确认

### 3. 实时同步
- WebSocket 推送状态变更
- 总览和频道视图自动同步
- 无需手动刷新

### 4. 深链接支持
- URL 包含 channelId 和 focus 参数
- 支持书签和直接访问
- 导航状态持久化

## 📝 数据转换流程

```mermaid
flowchart TD
    A[Backend Episode] -->|T2REpisode| B[transformEpisode]
    B --> C{提取字段}
    C --> D[episode_id → id]
    C --> E[schedule_date → date]
    C --> F[status → normalizeStatus]
    C --> G[image_path → assets.cover]
    C --> H[output_file → assets.audio]
    
    D --> I[ScheduleEvent]
    E --> I
    F --> I
    G --> I
    H --> I
    
    I --> J[检查资产完备度]
    J --> K[calculateCompleteness]
    K --> L[complete/partial/missing]
    
    L --> M[getStatusColor]
    M --> N[HSL 颜色 + 透明度调整]
    N --> O[UI 渲染]
```

## 🚀 性能优化

### 虚拟化渲染
- OverviewGrid 支持大量日期列
- 使用表格固定列头和频道名
- 未来可集成 `react-virtuoso` 优化大数据量

### 选择器优化
- Zustand 选择器避免不必要的重渲染
- 组件只订阅需要的状态切片

### 请求缓存
- React Query 缓存 API 响应
- 30 秒 staleTime，60 秒自动刷新

---

**文档版本**: v1.0  
**最后更新**: 2025-11-03  
**维护者**: Kat Rec 开发团队
