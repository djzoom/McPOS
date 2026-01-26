 # GridProgressIndicator V2 逻辑说明

## 概述

`GridProgressIndicator` 是一个三管道进度指示器，用于在排播表中显示每个节目的制作进度。它由三个独立的进度条组成：

1. **Asset (资产制作)**: 从初始化到渲染完成
2. **Upload (上传)**: 视频上传到 YouTube
3. **Verify (验证)**: 上传后的验证

## 架构设计

### 三个独立管道

```
Asset Pipeline:  INIT → REMIX → COVER → TEXT → RENDER → DONE
Upload Pipeline: pending → queued → uploading → uploaded
Verify Pipeline: verifying → verified
```

### 数据源

GridProgressIndicator 从以下数据源获取状态：

1. **`runbookSnapshot`**: 来自 WebSocket 的实时执行状态
   - `currentStage`: 当前执行阶段（如 "remix.in_progress", "render.queue"）
   - `failedStage`: 失败的阶段（如果有）

2. **`event`**: 来自 schedule store 的节目事件数据
   - `uploadState`: 上传状态（state, video_id, error 等）
   - `assets`: 资产文件路径和状态

3. **`assetStageReadiness`**: 计算得出的资产就绪状态
   - `preparation`: 准备阶段（playlist, cover, title, description, captions, audio）
   - `render`: 渲染阶段（video, render_complete_flag）
   - `publish`: 发布阶段（upload, verify）

## 状态派生逻辑

### Asset Stage 派生 (`deriveAssetStage`)

优先级顺序：

1. **显式覆盖** (`assetStageOverride`): 如果传入，直接使用
2. **失败检测**: 如果 `failurePipeline === 'asset'`，返回 `'FAILED'`
3. **Runbook 阶段映射**: 从 `runbookSnapshot.currentStage` 映射到 Asset Stage
4. **就绪状态回退**: 如果 `readiness?.render.ready`，返回 `'DONE'`
5. **未定义**: 如果没有匹配，返回 `undefined`（显示 Skeleton）

#### Runbook 阶段映射 (`mapStageNameToAssetStage`)

```typescript
// 阶段名称（不区分大小写）→ Asset Stage
- "failed" → FAILED
- "delivery|upload|publish|completed|done|verify" → DONE
- "render" → RENDER
- "text|title|description|caption" → TEXT
- "cover|image" → COVER
- "remix|audio" → REMIX
- "init|playlist|prep.*" → INIT
```

### Upload State 派生

优先级顺序：

1. **显式覆盖** (`uploadStateOverride`): 如果传入，直接使用
2. **事件状态** (`event?.uploadState`): 从 schedule event 获取
3. **失败检测**: 如果 `failurePipeline === 'upload'`，返回 `{ state: 'failed' }`
4. **未定义**: 如果没有匹配，返回 `undefined`（显示 Skeleton）

### Verify Stage 派生 (`deriveVerifyStage`)

优先级顺序：

1. **显式覆盖** (`verifyStateOverride?.state`): 如果传入，直接使用
2. **上传状态映射**: 从 `uploadState` 映射
   - `'verifying'` → `'verifying'`
   - `'verified'` → `'verified'`
3. **就绪状态**: 如果 `readiness?.publish.verifyReady`，返回 `'verified'`
4. **失败检测**: 如果 `failurePipeline === 'verify'`，返回 `'failed'`
5. **Runbook 阶段**: 如果 `runbookStage` 包含 "verify"，返回 `'verifying'`
6. **未定义**: 如果没有匹配，返回 `undefined`（显示 Skeleton）

## 资产就绪状态计算 (`calculateAssetStageReadiness`)

### Preparation 阶段

检查以下资产是否就绪：

- **playlist**: `assetStates.playlist` 或 `event.playlistPath`
- **cover**: `assetStates.cover` 或 `event.assets.cover`
- **title**: `assetStates.youtube_title` 或 `event.youtube_title_path` 或 `event.title`
- **description**: `assetStates.description` 或 `event.assets.description`
- **captions**: `assetStates.captions` 或 `event.assets.captions`
- **audio**: 需要同时有 `audio` 和 `timeline_csv`
  - `assetStates.audio` + `assetStates.timeline_csv`
  - 或 `event.assets.audio` (包含 `_full_mix.mp3`) + `event.assets.timeline_csv` (包含 `_full_mix_timeline.csv`)

### Render 阶段

检查以下资产是否就绪：

- **video**: `assetStates.video` 或 `event.assets.video` 或 `event.assets.video_path`
- **render_complete_flag**: `assetStates.render_complete_flag` 或 `event.assets.render_complete_flag`

`render.ready = videoReady && renderFlagReady`

### Publish 阶段

检查以下状态：

- **uploadReady**: `renderDone && (event.assets.uploaded_at || event.assets.uploaded || assetStates.upload_log)`
- **verifyReady**: `uploadReady && (event.assets.verified_at || event.assets.verified || upload_log.state === 'verified')`

`publish.ready = uploadReady && verifyReady`

## 失败检测 (`detectPipelineFromStage`)

从 `runbookSnapshot.failedStage` 检测失败发生在哪个管道：

- **verify**: 如果包含 "verify"
- **upload**: 如果包含 "upload|delivery|publish"
- **asset**: 如果包含 "remix|audio|cover|title|description|caption|text|render|init|playlist|prep.*"

## 视觉状态

### Asset Stage 视觉

| Stage | 颜色 | 动画 |
|-------|------|------|
| INIT | `bg-slate-400/50` | 无 |
| REMIX | `bg-gradient-to-r from-sky-500 via-sky-300 to-sky-500` | `animate-progress-flow-subtle` |
| COVER | `bg-amber-400` | `animate-progress-pulse` |
| TEXT | `bg-pink-400` | `animate-progress-glow` |
| RENDER | `bg-gradient-to-r from-purple-500 via-fuchsia-500 to-purple-500` | `animate-progress-flow-strong` |
| DONE | `bg-lime-300` | 无 |
| FAILED | `bg-red-500` | `animate-progress-flash` |

### Upload State 视觉

| State | 颜色 | 动画 |
|-------|------|------|
| pending | `bg-slate-400/50` | 无 |
| queued | `bg-gradient-to-r from-sky-500 via-blue-400 to-sky-500` | `animate-progress-flow-subtle` |
| uploading | `bg-gradient-to-r from-blue-600 via-sky-500 to-blue-600` | `animate-progress-flow-strong` |
| uploaded | `bg-blue-400` | `animate-progress-pulse` |
| failed | `bg-red-500` | `animate-progress-flash` |

### Verify Stage 视觉

| Stage | 颜色 | 动画 |
|-------|------|------|
| verifying | `bg-amber-400` | `animate-progress-pulse` |
| verified | `bg-lime-300` | 无 |
| failed | `bg-red-500` | `animate-progress-flash` |

## Skeleton 状态

如果某个管道的状态为 `undefined`，会显示 `SkeletonLine`：

- 灰色背景
- 闪烁动画 (`animate-progress-shimmer`)
- 表示数据尚未加载或状态未知

## 使用示例

### 在 OverviewGrid 中使用

```tsx
<GridProgressIndicator
  eventId={event.id}
  size="md"
  showLabel={true}
/>
```

### 在 TaskPanel 中使用

```tsx
<GridProgressIndicator
  eventId={episodeId}
  size="sm"
  showLabel={false}
/>
```

## 数据流

```
WebSocket 事件
    ↓
useWebSocket hook
    ↓
scheduleStore (patchEvent, setRunbookSnapshot)
    ↓
GridProgressIndicator (通过 selectors 订阅)
    ↓
deriveAssetStage / deriveUploadState / deriveVerifyStage
    ↓
ProgressLine (渲染视觉状态)
```

## 关键特性

1. **实时更新**: 通过 WebSocket 实时接收状态更新
2. **状态派生**: 从多个数据源智能派生状态，确保准确性
3. **失败检测**: 自动检测失败并显示在相应管道
4. **就绪状态**: 基于实际文件存在性计算就绪状态
5. **动画反馈**: 不同阶段使用不同动画，提供视觉反馈
6. **Skeleton 加载**: 数据未加载时显示骨架屏

## 相关文件

- `kat_rec_web/frontend/components/mcrb/GridProgressIndicator.tsx`: 主组件
- `kat_rec_web/frontend/components/mcrb/ProgressLine.tsx`: 进度条组件
- `kat_rec_web/frontend/components/mcrb/SkeletonLine.tsx`: 骨架屏组件
- `kat_rec_web/frontend/stores/scheduleStore.ts`: 状态管理和就绪状态计算
- `kat_rec_web/frontend/hooks/useWebSocket.ts`: WebSocket 连接和事件处理

