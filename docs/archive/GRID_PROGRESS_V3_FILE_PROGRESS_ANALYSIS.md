# GridProgress V3 文件进度集成分析

**日期**: 2025-01-XX  
**问题**: GridProgress V3 无法真正反映文件生成进度的现实

## 问题描述

GridProgress V3 目前只显示离散的状态（INIT, REMIX, COVER, TEXT, RENDER, DONE），无法显示文件生成过程中的实时进度百分比（0-100%）。

## 后端实现状态

### ✅ 已实现：FileProgressTracker

**文件**: `kat_rec_web/backend/t2r/utils/file_progress_tracker.py`

**功能**:
- 跟踪单个文件或一组文件的生成进度（0-100%）
- 通过 WebSocket 广播 `artifacts.file_progress` 数据
- 支持文件级别的状态：`pending`, `generating`, `completed`, `failed`

**WebSocket 事件格式**:
```json
{
  "type": "runbook_stage_update",
  "data": {
    "episode_id": "20251117",
    "stage": "prep.remix",
    "status": "in_progress",
    "progress": 45,
    "artifacts": {
      "file_progress": {
        "total_files": 3,
        "completed_files": 1,
        "files": {
          "full_mix.mp3": {
            "status": "generating",
            "progress": 45,
            "started_at": "2025-01-XXT12:34:56.789Z",
            "completed_at": null,
            "error": null
          },
          "full_mix_timeline.csv": {
            "status": "completed",
            "progress": 100,
            "started_at": "2025-01-XXT12:34:00.000Z",
            "completed_at": "2025-01-XXT12:34:30.000Z"
          }
        }
      }
    }
  }
}
```

**使用场景**:
- `_init_episode()`: 跟踪 playlist 文件生成
- `_prepare_episode_parallel()`: 跟踪音频、封面、文本文件生成
- `_render_episode()`: 跟踪视频渲染进度

## 前端实现状态

### ❌ 未实现：文件进度数据提取

**问题 1**: WebSocket 事件处理未提取 `artifacts.file_progress`

**文件**: `kat_rec_web/frontend/hooks/useWebSocket.ts`

**当前状态**:
- ✅ 处理 `runbook_stage_update` 事件
- ✅ 提取 `progress` 字段（0-100）
- ❌ **未提取** `artifacts.file_progress` 数据
- ❌ **未存储** 文件进度到 store

**问题 2**: Store 中未存储文件进度数据

**文件**: `kat_rec_web/frontend/stores/scheduleStore.ts`

**当前状态**:
- ✅ `RunbookStageSnapshot` 存储 `currentStage`, `failedStage`
- ❌ **未存储** `progress` 字段
- ❌ **未存储** `file_progress` 数据

**问题 3**: `useEpisodePipelineStateV3` 未读取文件进度

**文件**: `kat_rec_web/frontend/hooks/useEpisodePipelineStateV3.ts`

**当前状态**:
- ✅ 派生离散状态（INIT, REMIX, COVER, TEXT, RENDER, DONE）
- ❌ **未读取** 文件进度百分比
- ❌ **未返回** 进度数据给组件

**问题 4**: `ProgressLineV3` 无法显示进度百分比

**文件**: `kat_rec_web/frontend/components/mcrb/ProgressLineV3.tsx`

**当前状态**:
- ✅ 显示状态动画（flow, pulse, glow, flash）
- ❌ **无法显示** 进度百分比（0-100%）
- ❌ **无宽度动画** 基于进度百分比

## 设计对比

### Codex 原始设计意图

根据 `GridProgressV3.mdx` 文档：

> **V3 核心原则**:
> 1. **纯状态驱动**: 无猜测逻辑，无百分比计算
> 2. **单一数据源**: 所有状态从 store selectors 派生

**问题**: 这个设计原则与后端提供的文件进度数据冲突。

### 实际需求

1. **后端已经提供了文件进度百分比**（0-100%）
2. **前端应该显示这些实时进度**，而不是只显示离散状态
3. **用户需要看到文件生成的实际进度**，而不是猜测

## 修复方案

### 方案 1: 扩展 V3 架构（推荐）

**原则**: 保持 V3 的"纯状态驱动"原则，但**从后端数据源读取进度**，而不是猜测。

#### Step 1: 扩展 RunbookStageSnapshot

**文件**: `kat_rec_web/frontend/stores/scheduleStore.ts`

```typescript
export interface RunbookStageSnapshot {
  currentStage: string | null
  episodeId: string | null
  failedStage?: string | null
  errorMessage?: string | null
  // ✅ 新增：进度百分比
  progress?: number // 0-100
  // ✅ 新增：文件进度数据
  fileProgress?: {
    total_files: number
    completed_files: number
    files: Record<string, {
      status: 'pending' | 'generating' | 'completed' | 'failed'
      progress: number // 0-100
      started_at?: string
      completed_at?: string
      error?: string
    }>
  }
}
```

#### Step 2: 在 WebSocket 处理中提取文件进度

**文件**: `kat_rec_web/frontend/hooks/useWebSocket.ts`

在 `runbook_stage_update` 事件处理中：

```typescript
// 提取 artifacts.file_progress
const fileProgress = data.artifacts?.file_progress

// 更新 runbook snapshot
callbacks.setRunbookSnapshot(episodeId, {
  currentStage: normalizedStage,
  episodeId,
  failedStage: data.error ? normalizedStage : undefined,
  errorMessage: typeof data.error === 'string' ? data.error : undefined,
  progress: data.progress, // ✅ 新增
  fileProgress: fileProgress, // ✅ 新增
})
```

#### Step 3: 扩展 useEpisodePipelineStateV3

**文件**: `kat_rec_web/frontend/hooks/useEpisodePipelineStateV3.ts`

```typescript
export interface EpisodePipelineStateV3 {
  assetStage: AssetStage
  uploadState: UploadState
  verifyState: VerifyState
  missingAssets: string[]
  lastUpdated?: number
  // ✅ 新增：进度数据
  progress?: number // 0-100 (from runbook snapshot)
  fileProgress?: RunbookStageSnapshot['fileProgress'] // 文件级别进度
}
```

在 hook 中读取：

```typescript
const runbookState = useScheduleStore((state) => 
  eventId ? state.runbookSnapshots[eventId] || null : null
)

return useMemo(() => {
  // ... existing logic ...
  
  return {
    assetStage,
    uploadState,
    verifyState,
    missingAssets,
    progress: runbookState?.progress, // ✅ 新增
    fileProgress: runbookState?.fileProgress, // ✅ 新增
    lastUpdated: Date.now(),
  }
}, [eventId, event, readiness, runbookState])
```

#### Step 4: 扩展 ProgressLineV3 支持进度百分比

**文件**: `kat_rec_web/frontend/components/mcrb/ProgressLineV3.tsx`

```typescript
interface ProgressLineV3Props {
  assetStage?: AssetStage
  uploadState?: UploadState
  verifyState?: VerifyState
  size?: 'sm' | 'md' | 'cell'
  // ✅ 新增：进度百分比（0-100）
  progress?: number
}

export function ProgressLineV3({
  assetStage,
  uploadState,
  verifyState,
  size = 'md',
  progress, // ✅ 新增
}: ProgressLineV3Props) {
  // ... existing code ...
  
  if (assetStage) {
    const styleClass = ASSET_STAGE_STYLES[assetStage]
    const variant = getAssetVariant(assetStage)
    
    // ✅ 如果有进度百分比，使用宽度动画
    const widthStyle = progress !== undefined 
      ? { width: `${Math.max(0, Math.min(100, progress))}%` }
      : { width: '100%' }
    
    return (
      <div className={baseContainerClass} style={{ backgroundColor: 'rgba(148, 163, 184, 0.15)' }}>
        <motion.div
          className={`absolute inset-0 ${roundedClass} ${styleClass}`}
          initial={shouldReduceMotion ? undefined : (variant.initial as any)}
          animate={shouldReduceMotion ? undefined : { ...variant.animate, ...widthStyle } as any}
          exit={shouldReduceMotion ? undefined : (variant.exit as any)}
          transition={variant.transition}
          style={{ transformOrigin: 'left', ...widthStyle }}
        />
      </div>
    )
  }
  
  // ... similar for uploadState and verifyState ...
}
```

#### Step 5: 在 GridProgressIndicatorV3 中传递进度

**文件**: `kat_rec_web/frontend/components/mcrb/GridProgressIndicatorV3.tsx`

```typescript
const { assetStage, uploadState, verifyState, progress, fileProgress } = useEpisodePipelineStateV3(eventId)

// 根据当前阶段映射进度
const assetProgress = assetStage && progress !== undefined ? progress : undefined
const uploadProgress = uploadState && progress !== undefined ? progress : undefined
const verifyProgress = verifyState && progress !== undefined ? progress : undefined

// 传递进度给 ProgressLineV3
<ProgressLineV3 assetStage={finalAssetStage} size={size} progress={assetProgress} />
<ProgressLineV3 uploadState={finalUploadState} size={size} progress={uploadProgress} />
<ProgressLineV3 verifyState={finalVerifyState} size={size} progress={verifyProgress} />
```

## 实施优先级

### Phase 1: 数据提取（必需）
1. ✅ 扩展 `RunbookStageSnapshot` 接口
2. ✅ 在 WebSocket 处理中提取 `progress` 和 `file_progress`
3. ✅ 更新 store 的 `setRunbookSnapshot` 方法

### Phase 2: Hook 扩展（必需）
4. ✅ 扩展 `useEpisodePipelineStateV3` 返回进度数据
5. ✅ 从 `runbookSnapshots` 读取进度

### Phase 3: UI 显示（可选）
6. ✅ 扩展 `ProgressLineV3` 支持进度百分比
7. ✅ 在 `GridProgressIndicatorV3` 中传递进度

## 验证清单

- [ ] WebSocket 事件中的 `artifacts.file_progress` 被正确提取
- [ ] Store 中的 `runbookSnapshots[episodeId].progress` 被正确更新
- [ ] `useEpisodePipelineStateV3` 返回 `progress` 和 `fileProgress`
- [ ] `ProgressLineV3` 根据进度百分比显示宽度动画
- [ ] 文件生成过程中进度条实时更新（0-100%）
- [ ] 完成后进度条显示 100% 宽度

## 向后兼容性

- ✅ 不破坏现有 API
- ✅ `progress` 和 `fileProgress` 为可选字段
- ✅ 如果后端未提供进度数据，组件仍显示状态动画（当前行为）
- ✅ 如果后端提供了进度数据，组件显示进度百分比（新行为）

## 总结

**问题根源**: V3 设计原则"无百分比计算"与后端提供的文件进度数据不匹配。

**解决方案**: 保持"纯状态驱动"原则，但**从后端数据源读取进度**，而不是猜测或计算。

**关键改进**:
1. 扩展 store 存储文件进度数据
2. 在 WebSocket 处理中提取进度
3. 在 hook 中返回进度数据
4. 在组件中显示进度百分比（如果可用）

这样既保持了 V3 的设计原则，又能反映文件生成进度的现实。

---

## Phase 1 实施总结

**日期**: 2025-01-XX  
**状态**: ✅ 完成

### 新增字段

在 `RunbookStageSnapshot` 接口中新增：

1. **`overallProgress?: number`**
   - 类型: `number` (0-100)
   - 用途: 存储总体进度百分比
   - 来源: WebSocket `runbook_stage_update` 事件的 `progress` 字段

2. **`fileProgress?: { ... }`**
   - 类型: 对象，包含 `total_files`, `completed_files`, `files`
   - 用途: 存储文件级别的详细进度信息
   - 来源: WebSocket `runbook_stage_update` 事件的 `artifacts.file_progress` 字段
   - 结构:
     ```typescript
     {
       total_files: number
       completed_files: number
       files: Record<string, {
         status: 'pending' | 'generating' | 'completed' | 'failed'
         progress: number // 0-100
         started_at?: string
         completed_at?: string
         error?: string
       }>
     }
     ```

### 修改的文件

1. **`kat_rec_web/frontend/stores/scheduleStore.ts`**
   - 扩展 `RunbookStageSnapshot` 接口（第 288-306 行）
   - 更新 `setRunbookSnapshot` 方法，实现非破坏性合并（第 1027-1045 行）
     - 如果新 snapshot 没有 `overallProgress`，保留现有值
     - 如果新 snapshot 没有 `fileProgress`，保留现有值

### 验证结果

- ✅ TypeScript 类型检查通过（无新增错误）
- ✅ 现有逻辑可以读取新字段（即使目前是 `undefined`）
- ✅ 非破坏性合并确保现有代码不受影响

### 当前状态

- ✅ 数据结构已就绪
- ⏳ WebSocket 事件处理尚未提取 `artifacts.file_progress`（Phase 2）
- ⏳ UI 组件尚未使用这些字段（Phase 3）

### 向后兼容性

- ✅ 所有新字段都是可选的（`?`）
- ✅ 现有代码在字段为 `undefined` 时正常工作
- ✅ `setRunbookSnapshot` 的非破坏性合并确保不会丢失现有数据

---

## Phase 2 实施总结

**日期**: 2025-01-XX  
**状态**: ✅ 完成

### WebSocket 事件处理

在 `runbook_stage_update` 事件处理中实现了文件进度数据的提取和存储：

1. **提取 `overallProgress`**
   - 来源: `data.progress` (0-100)
   - 处理: 使用 `Math.max(0, Math.min(100, data.progress))` 确保值在有效范围内
   - 位置: `kat_rec_web/frontend/hooks/useWebSocket.ts` 第 866 行

2. **提取 `fileProgress`**
   - 来源: `data.artifacts?.file_progress`
   - 结构: 包含 `total_files`, `completed_files`, `files` 对象
   - 位置: `kat_rec_web/frontend/hooks/useWebSocket.ts` 第 869 行

3. **更新 store snapshot**
   - 在 `setRunbookSnapshot` 调用中包含 `overallProgress` 和 `fileProgress`
   - 位置: `kat_rec_web/frontend/hooks/useWebSocket.ts` 第 895-903 行

### 调试日志

添加了开发模式下的调试日志（仅在 `NODE_ENV === 'development'` 时输出）：

1. **文件进度日志** (`[GridProgress][file_progress]`)
   - 输出: episode ID, stage, total_files, completed_files, 每个文件的状态和进度
   - 位置: `kat_rec_web/frontend/hooks/useWebSocket.ts` 第 872-884 行

2. **总体进度日志** (`[GridProgress][overall_progress]`)
   - 输出: episode ID, stage, progress 百分比
   - 位置: `kat_rec_web/frontend/hooks/useWebSocket.ts` 第 886-892 行

### 数据流

```
WebSocket runbook_stage_update 事件
  ↓
提取 data.progress → overallProgress (0-100)
  ↓
提取 data.artifacts?.file_progress → fileProgress
  ↓
调用 setRunbookSnapshot(episodeId, { ..., overallProgress, fileProgress })
  ↓
Store 非破坏性合并（保留现有进度数据）
  ↓
runbookSnapshots[episodeId] 包含进度数据
```

### 修改的文件

1. **`kat_rec_web/frontend/hooks/useWebSocket.ts`**
   - 在 `runbook_stage_update` 事件处理中提取进度数据（第 861-903 行）
   - 添加开发模式调试日志（第 872-893 行）

### 验证结果

- ✅ TypeScript 类型检查通过（无新增错误）
- ✅ ESLint 检查通过
- ✅ 调试日志在开发模式下正常工作
- ✅ 数据提取逻辑正确处理 `undefined` 情况

### 当前状态

- ✅ WebSocket 事件处理已提取 `artifacts.file_progress`
- ✅ Store 中的 `runbookSnapshots[episodeId]` 包含进度数据
- ⏳ UI 组件尚未使用这些字段（Phase 3）

### 向后兼容性

- ✅ 如果 WebSocket 事件没有 `progress` 或 `artifacts.file_progress`，字段保持 `undefined`
- ✅ Store 的非破坏性合并确保不会丢失现有数据
- ✅ 现有代码在字段为 `undefined` 时正常工作

