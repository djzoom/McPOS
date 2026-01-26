# GridProgressIndicator V2 当前运行逻辑

## ✅ 确认：当前运行的是 V2 版本

**版本标识**：
- 文件头部：`GridProgressIndicator V2`
- 版本号：`2.0`
- 阶段：`Phase E - Final Integration + Verification`

**使用位置**：
- `OverviewGrid.tsx`: 排播表网格中显示（`size="sm"`, `showLabel={false}`）
- `ChannelTimeline.tsx`: 时间线中显示（`size="md"`, `showLabel={true}`）
- `TaskPanel.tsx`: 任务面板中显示

## 当前运行的核心逻辑

### 1. 数据源订阅

```typescript
// 从 Zustand store 订阅三个数据源
const event = useScheduleStore(eventSelector)                    // ScheduleEvent
const assetStageReadiness = useScheduleStore(assetStageSelector) // AssetStageReadiness
const runbookSnapshot = useScheduleStore(
  (state) => state.runbookSnapshots[eventId] || null            // RunbookStageSnapshot
)
```

### 2. 失败检测

```typescript
const failurePipeline = detectPipelineFromStage(runbookSnapshot?.failedStage)
// 返回: 'asset' | 'upload' | 'verify' | null
```

### 3. Asset Stage 派生（优先级顺序）

```typescript
deriveAssetStage({
  explicit: assetStageOverride,        // 1. 显式覆盖（最高优先级）
  runbookStage: runbookSnapshot?.currentStage,  // 2. 从 runbook 阶段映射
  failurePipeline,                     // 3. 失败检测
  readiness: assetStageReadiness,      // 4. 从就绪状态回退
})
```

**映射规则**：
- `"remix|audio"` → `REMIX`
- `"cover|image"` → `COVER`
- `"text|title|description|caption"` → `TEXT`
- `"render"` → `RENDER`
- `"delivery|upload|publish|completed|done|verify"` → `DONE`
- `"init|playlist|prep.*"` → `INIT`
- `failurePipeline === 'asset'` → `FAILED`
- `readiness?.render.ready` → `DONE` (回退)

### 4. Upload State 派生（优先级顺序）

```typescript
derivedUploadState =
  uploadStateOverride ??              // 1. 显式覆盖
  event?.uploadState ??               // 2. 从 event 获取
  (failurePipeline === 'upload'       // 3. 失败检测
    ? { state: 'failed' }
    : undefined)
```

### 5. Verify Stage 派生（优先级顺序）

```typescript
deriveVerifyStage({
  uploadState: derivedUploadState?.state,  // 1. 从 uploadState 映射
  readiness: assetStageReadiness,           // 2. 从就绪状态
  failurePipeline,                         // 3. 失败检测
  runbookStage: runbookSnapshot?.currentStage, // 4. 从 runbook 阶段
})
```

**映射规则**：
- `uploadState === 'verifying'` → `'verifying'`
- `uploadState === 'verified'` → `'verified'`
- `readiness?.publish.verifyReady` → `'verified'`
- `failurePipeline === 'verify'` → `'failed'`
- `runbookStage.includes('verify')` → `'verifying'`

### 6. 资产就绪状态计算 (`calculateAssetStageReadiness`)

**Preparation 阶段**：
- `playlistReady`: `assetStates.playlist` 或 `event.playlistPath`
- `coverReady`: `assetStates.cover` 或 `event.assets.cover`
- `titleReady`: `assetStates.youtube_title` 或 `event.youtube_title_path` 或 `event.title`
- `descriptionReady`: `assetStates.description` 或 `event.assets.description`
- `captionsReady`: `assetStates.captions` 或 `event.assets.captions`
- `audioReady`: 需要同时有 `audio` 和 `timeline_csv`

**Render 阶段**：
- `videoReady`: `assetStates.video` 或 `event.assets.video` 或 `event.assets.video_path`
- `renderFlagReady`: `assetStates.render_complete_flag` 或 `event.assets.render_complete_flag`
- `render.ready = videoReady && renderFlagReady`

**Publish 阶段**：
- `uploadReady`: `renderDone && (event.assets.uploaded_at || event.assets.uploaded || assetStates.upload_log)`
- `verifyReady`: `uploadReady && (event.assets.verified_at || event.assets.verified || upload_log.state === 'verified')`
- `publish.ready = uploadReady && verifyReady`

### 7. 视觉渲染

**三个 ProgressLine 组件**：
```typescript
<ProgressLine variant="asset" state={derivedAssetStage} />
<ProgressLine variant="upload" state={derivedUploadState?.state} />
<ProgressLine variant="verify" state={derivedVerifyStage} />
```

**状态为 undefined/null 时**：
- 显示 `SkeletonLine`（灰色闪烁动画）

**状态有值时**：
- 显示对应颜色的进度条
- 应用相应的动画（flow, pulse, glow, flash）

## 数据流

```
WebSocket 事件
    ↓
useWebSocket hook
    ↓
scheduleStore 更新
    ├─ patchEvent(event)           → event
    ├─ setRunbookSnapshot(...)     → runbookSnapshot
    └─ calculateAssetStageReadiness → assetStageReadiness
    ↓
GridProgressIndicator 订阅
    ├─ eventSelector
    ├─ assetStageSelector
    └─ runbookSnapshot selector
    ↓
状态派生
    ├─ deriveAssetStage()
    ├─ deriveUploadState
    └─ deriveVerifyStage()
    ↓
ProgressLine 渲染
    ├─ Asset Pipeline
    ├─ Upload Pipeline
    └─ Verify Pipeline
```

## 关键特性

### ✅ 已实现

1. **三个独立管道**：Asset → Upload → Verify
2. **实时更新**：通过 WebSocket 实时接收状态
3. **智能派生**：从多个数据源智能派生状态
4. **失败检测**：自动检测失败并显示在相应管道
5. **就绪状态**：基于实际文件存在性计算
6. **动画反馈**：不同阶段使用不同动画
7. **Skeleton 加载**：数据未加载时显示骨架屏

### 📊 测试状态

- ✅ 所有 8 个测试用例通过
- ✅ Phase E 验证完成
- ✅ 动画系统优化完成

## 实际运行示例

### 在 OverviewGrid 中

```tsx
<GridProgressIndicator 
  eventId={primaryEvent.id} 
  size="sm" 
  showLabel={false} 
/>
```

**显示效果**：
- 三个小尺寸进度条（无标签）
- 实时反映节目制作进度

### 在 ChannelTimeline 中

```tsx
<GridProgressIndicator 
  eventId={event.id} 
  size="md" 
  showLabel={true} 
/>
```

**显示效果**：
- 三个中等尺寸进度条（带标签）
- 显示 "ASSET REMIX"、"UPLOAD uploading" 等标签

## 状态映射表

### Asset Stage 映射

| Runbook Stage | Asset Stage | 颜色 | 动画 |
|--------------|-------------|------|------|
| `prep.*`, `init`, `playlist` | `INIT` | 灰色 | 无 |
| `remix`, `audio` | `REMIX` | 天蓝色渐变 | flow-subtle |
| `cover`, `image` | `COVER` | 琥珀色 | pulse |
| `text`, `title`, `description`, `caption` | `TEXT` | 粉色 | glow |
| `render` | `RENDER` | 紫色渐变 | flow-strong |
| `delivery`, `upload`, `publish`, `completed`, `done` | `DONE` | 绿色 | 无 |
| `failed` (asset pipeline) | `FAILED` | 红色 | flash (2次) |

### Upload State 映射

| Upload State | 颜色 | 动画 |
|-------------|------|------|
| `pending` | 灰色 | 无 |
| `queued` | 天蓝色渐变 | flow-subtle |
| `uploading` | 蓝色渐变 | flow-strong |
| `uploaded` | 蓝色 | pulse |
| `failed` | 红色 | flash (2次) |

### Verify Stage 映射

| Verify Stage | 颜色 | 动画 |
|-------------|------|------|
| `verifying` | 琥珀色 | pulse |
| `verified` | 绿色 | 无 |
| `failed` | 红色 | flash (2次) |

## 总结

**当前运行的是 GridProgressIndicator V2**，具有完整的三管道架构、实时状态更新、智能状态派生和优化的动画系统。所有核心功能已实现并通过测试，正在生产环境中使用。

