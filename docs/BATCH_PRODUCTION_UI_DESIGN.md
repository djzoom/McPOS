# 批量制播管理前端架构设计

**版本**: 1.0  
**最后更新**: 2025-01-XX  
**适用范围**: Kat Rec 频道批量制播管理

---

## 📋 设计目标

设计一个高效的前端架构和UI，支持：

1. **批量排播初始化**：一次性生成未来数期（如12月整月）的排播表
2. **批量内容生成**：自动执行所有制播阶段（Init → Cover → Text → Remix → Render）
3. **批量上传排播**：控制API尽快上传并排播到YouTube
4. **实时状态监控**：实时查看每期的生成和上传进度
5. **智能调度**：优化资源使用，避免API限流

---

## 🏗️ 架构设计

### 1. 页面结构

```
/app/(t2r)/t2r/batch/
  ├── page.tsx                    # 批量制播管理主页面
  └── components/
      ├── BatchScheduleManager.tsx # 批量排播管理器（核心组件）
      ├── DateRangePicker.tsx     # 日期范围选择器
      ├── BatchOperationPanel.tsx  # 批量操作面板
      ├── EpisodeStatusGrid.tsx   # 期数状态网格
      ├── ProgressMonitor.tsx     # 进度监控面板
      └── UploadScheduler.tsx     # 上传排播调度器
```

### 2. 组件层次结构

```
BatchScheduleManager (主容器)
├── DateRangePicker (日期选择)
├── ChannelSelector (频道选择)
├── BatchOperationPanel (操作面板)
│   ├── InitializeButton (初始化排播)
│   ├── GenerateButton (批量生成)
│   └── UploadButton (批量上传)
├── EpisodeStatusGrid (期数状态展示)
│   └── EpisodeCard (单期卡片)
└── ProgressMonitor (进度监控)
    ├── OverallProgress (总体进度)
    └── StageProgress (阶段进度)
```

### 3. 状态管理

使用 **Zustand** 管理批量操作状态：

```typescript
interface BatchProductionState {
  // 选择状态
  selectedChannel: string | null
  dateRange: { start: Date; end: Date } | null
  selectedEpisodes: string[]
  
  // 操作状态
  isInitializing: boolean
  isGenerating: boolean
  isUploading: boolean
  
  // 进度状态
  episodeProgress: Map<string, EpisodeProgress>
  overallProgress: OverallProgress
  
  // 操作历史
  operationHistory: OperationLog[]
}
```

### 4. API 集成

#### 4.1 排播初始化

```typescript
POST /api/t2r/schedule/initialize
{
  channel_id: string
  days: number
  start_date?: string  // YYYY-MM-DD
}
```

#### 4.2 批量生成

```typescript
POST /api/t2r/automation/batch-generate
{
  channel_id: string
  days: number
  dry_run?: boolean
}
```

#### 4.3 批量上传

```typescript
POST /api/t2r/upload/batch-start
{
  channel_id: string
  episode_ids: string[]
  priority?: 'high' | 'normal' | 'low'
  auto_schedule?: boolean
}
```

#### 4.4 状态查询

```typescript
GET /api/t2r/schedule/episodes?channel_id={channel_id}
GET /api/t2r/batch/status?run_id={run_id}
```

### 5. WebSocket 实时更新

订阅以下事件：

- `batch_generate_started` - 批量生成开始
- `batch_generate_progress` - 批量生成进度
- `batch_generate_completed` - 批量生成完成
- `batch_upload_started` - 批量上传开始
- `batch_upload_progress` - 批量上传进度
- `batch_upload_completed` - 批量上传完成
- `episode_state_changed` - 单期状态变更

---

## 🎨 UI 设计

### 1. 主界面布局

```
┌─────────────────────────────────────────────────────────┐
│  批量制播管理 - Kat Records                              │
├─────────────────────────────────────────────────────────┤
│  [频道选择] [日期范围: 2025-12-01 ~ 2025-12-31]         │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  批量操作                                        │  │
│  │  [初始化排播] [批量生成] [批量上传] [暂停]      │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  总体进度: ████████░░ 80% (24/30)              │  │
│  │  [初始化] ████████░░ 80%                        │  │
│  │  [生成]   ██████████ 100%                        │  │
│  │  [上传]   ████░░░░░░ 40%                          │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  期数状态网格 (30期)                             │  │
│  │  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐                │  │
│  │  │12/1│ │12/2│ │12/3│ │12/4│ │12/5│ ...        │  │
│  │  │ ✓ │ │ ⏳ │ │ ✓ │ │ ❌ │ │ ✓ │                │  │
│  │  └───┘ └───┘ └───┘ └───┘ └───┘                │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  操作日志                                         │  │
│  │  2025-12-01 10:00:00 [初始化] 创建30期排播表     │  │
│  │  2025-12-01 10:05:00 [生成]   开始批量生成...    │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 2. 期数卡片设计

每个期数卡片显示：

- **期号**：`20251201`
- **排播日期**：`2025-12-01`
- **状态图标**：
  - ⏳ 待处理 (pending)
  - 🔄 进行中 (processing)
  - ✓ 已完成 (completed)
  - ❌ 失败 (failed)
- **阶段进度**：Init → Cover → Text → Remix → Render → Upload
- **操作按钮**：查看详情、重试、跳过

### 3. 日期范围选择器

支持：
- **快速选择**：本月、下月、整月（12月）
- **自定义范围**：开始日期 + 结束日期
- **间隔设置**：每N天一期（默认2天）

### 4. 批量操作流程

#### 4.1 初始化排播

```
用户点击 [初始化排播]
  ↓
选择日期范围（如：2025-12-01 ~ 2025-12-31）
  ↓
计算期数（30天，每2天一期 = 15期）
  ↓
调用 POST /api/t2r/schedule/initialize
  ↓
显示进度：创建文件夹、生成 playlist.csv
  ↓
完成：显示创建的期数列表
```

#### 4.2 批量生成

```
用户点击 [批量生成]
  ↓
检查：确保所有期数已初始化
  ↓
调用 POST /api/t2r/automation/batch-generate
  ↓
后台任务开始执行：
  - 遍历所有待生成期数
  - 对每期执行：Init → Cover → Text → Remix → Render
  - 实时更新进度（WebSocket）
  ↓
完成：所有期数内容生成完成
```

#### 4.3 批量上传

```
用户点击 [批量上传]
  ↓
选择上传策略：
  - 立即上传（尽快）
  - 按排播日期上传（按计划）
  - 智能调度（避免API限流）
  ↓
调用 POST /api/t2r/upload/batch-start
  ↓
上传队列开始处理：
  - 按优先级排序
  - 串行上传（避免限流）
  - 实时更新状态（WebSocket）
  ↓
完成：所有期数上传完成
```

---

## 🔄 工作流程

### 完整流程示例：生成12月整月内容

#### 步骤 1: 初始化排播表

1. 用户选择频道：`kat_lofi`
2. 选择日期范围：`2025-12-01` ~ `2025-12-31`
3. 设置间隔：每2天一期
4. 点击"初始化排播"
5. 系统创建15期排播表（12/1, 12/3, 12/5, ..., 12/31）

#### 步骤 2: 批量生成内容

1. 点击"批量生成"
2. 系统开始后台任务：
   - 对每期执行完整制播流程
   - 实时显示进度
   - 支持暂停/恢复
3. 预计时间：15期 × 5分钟/期 = 75分钟（可并行优化）

#### 步骤 3: 批量上传排播

1. 点击"批量上传"
2. 选择上传策略：**尽快上传**
3. 系统开始上传：
   - 按优先级排序（早日期优先）
   - 串行上传（避免YouTube API限流）
   - 自动计算发布时间（基于频道配置）
4. 预计时间：15期 × 2分钟/期 = 30分钟

---

## 🚀 性能优化

### 1. 并行生成

- **阶段内并行**：多期可以同时生成（如果资源允许）
- **阶段间串行**：单期内部阶段必须串行（依赖关系）

### 2. 智能调度

- **上传队列**：串行上传，避免API限流
- **优先级管理**：早日期优先，失败重试优先
- **资源控制**：限制并发数，避免系统过载

### 3. 增量更新

- **状态缓存**：缓存期数状态，减少API调用
- **WebSocket推送**：实时更新，无需轮询
- **增量渲染**：只更新变化的期数卡片

---

## 📊 状态定义

### 期数状态

```typescript
type EpisodeStatus = 
  | 'pending'      // 待处理
  | 'initializing' // 初始化中
  | 'generating'   // 生成中
  | 'generated'    // 已生成
  | 'uploading'    // 上传中
  | 'uploaded'     // 已上传
  | 'scheduled'    // 已排播
  | 'failed'       // 失败
```

### 阶段状态

```typescript
type StageStatus = 
  | 'pending'    // 待处理
  | 'running'    // 进行中
  | 'completed'  // 已完成
  | 'failed'     // 失败
  | 'skipped'    // 已跳过
```

---

## 🔧 技术实现

### 1. 组件库

- **UI框架**：React + Next.js
- **状态管理**：Zustand
- **样式**：Tailwind CSS + GlassPanel组件
- **日期选择**：react-datepicker 或自定义组件
- **实时通信**：WebSocket (已有实现)
- **数据获取**：React Query (TanStack Query)

### 2. 关键Hook

```typescript
// 批量操作Hook
useBatchProduction(channelId, dateRange)

// 期数状态Hook
useEpisodeStatus(episodeId)

// 进度监控Hook
useProgressMonitor(runId)

// WebSocket订阅Hook
useBatchEvents(channelId)
```

### 3. 错误处理

- **重试机制**：失败操作自动重试（最多3次）
- **错误提示**：友好的错误信息展示
- **日志记录**：详细的操作日志

---

## 📝 API 扩展需求

### 1. 批量上传API

需要新增：

```typescript
POST /api/t2r/upload/batch-start
{
  channel_id: string
  episode_ids: string[]
  priority?: 'high' | 'normal' | 'low'
  auto_schedule?: boolean  // 是否自动计算发布时间
}
```

### 2. 批量状态查询

```typescript
GET /api/t2r/batch/status?run_id={run_id}
{
  run_id: string
  status: 'running' | 'completed' | 'failed'
  progress: {
    total: number
    completed: number
    failed: number
  }
  episodes: EpisodeStatus[]
}
```

### 3. 操作控制

```typescript
POST /api/t2r/batch/pause?run_id={run_id}
POST /api/t2r/batch/resume?run_id={run_id}
POST /api/t2r/batch/cancel?run_id={run_id}
```

---

## ✅ 验收标准

1. ✅ 可以一次性初始化12月整月（31天）的排播表
2. ✅ 可以批量生成所有期数的完整内容
3. ✅ 可以批量上传并自动排播到YouTube
4. ✅ 实时显示每期的生成和上传进度
5. ✅ 支持暂停、恢复、取消操作
6. ✅ 错误处理和重试机制完善
7. ✅ UI响应流畅，用户体验良好

---

## 📚 参考文档

- [频道制播流程技术规范](./CHANNEL_PRODUCTION_SPEC.md)
- [上传验证生命周期](./LIFECYCLE_UPLOAD_VERIFY.md)
- [状态流分析](./STATEFLOW_V4_COMPLETE_ANALYSIS.md)

---

**文档维护**: 本文档应与前端实现同步更新。

