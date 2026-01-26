# 渲染状态显示问题修复总结

## 问题描述

前端显示 20251112 在渲染队列中显示"等待渲染"，但实际上已经开始渲染。

## 根本原因

1. **前端状态判断逻辑不完整**: `render.inProgress` 判断没有显式检查 `render.in_progress` 状态
2. **RenderQueuePanel 状态计算不完整**: `renderingEvents` 过滤逻辑没有正确处理 `render.in_progress` 状态
3. **WebSocket 事件处理**: 状态更新可能没有正确传递 `render.in_progress` 状态

## 修复内容

### 1. 修复前端 render.inProgress 判断逻辑

**文件**: `kat_rec_web/frontend/stores/scheduleStore.ts`

**修改**:
- 添加显式检查 `render.in_progress` 状态
- 确保 `activeStageKey === 'render'` 或 `currentStage === 'render.in_progress'` 时，`render.inProgress` 为 true
- 添加调试日志以追踪状态计算

```typescript
inProgress: (() => {
  const isInProgress = (activeStageKey === 'render' || 
                        (isEventInProgress && 
                         runbookState?.currentStage && 
                         (runbookState.currentStage.toLowerCase() === 'render.in_progress' ||
                          runbookState.currentStage.toLowerCase().includes('render.in_progress')))) && 
                       failedStageKey !== 'render' &&
                       runbookState?.currentStage?.toLowerCase() !== 'render.queue' &&
                       !runbookState?.currentStage?.toLowerCase().includes('render.queue')
  // 添加调试日志
  if (event.id === '20251112' || event.id.includes('20251112')) {
    console.debug('[calculateStageStatus] Render inProgress calculation:', {...})
  }
  return isInProgress
})(),
```

### 2. 修复 RenderQueuePanel 的状态计算

**文件**: `kat_rec_web/frontend/components/mcrb/RenderQueuePanel.tsx`

**修改**:
- 在 `renderingEvents` 计算中添加对 `render.in_progress` 状态的显式检查
- 确保 `render.in_progress` 状态被正确识别为"渲染中"
- 添加调试日志以追踪事件状态

```typescript
const isRendering = (
  stages.render.inProgress || 
  (runbookState?.episodeId === event.id && 
   (runbookState.currentStage === 'render' || 
    runbookState.currentStage === 'render.in_progress' ||
    currentStage === 'render.in_progress') && 
   !isRenderQueue) ||
  ...
)
```

### 3. 验证 WebSocket 事件处理

**文件**: `kat_rec_web/frontend/hooks/useWebSocket.ts`

**修改**:
- 确保 `data.stage` 或 `data.currentStage` 正确传递到 `setRunbookSnapshot`
- 添加调试日志以追踪渲染状态更新

```typescript
const normalizedStage = data.stage || data.currentStage || null
setRunbookSnapshot(episodeId, {
  currentStage: normalizedStage,
  episodeId,
  failedStage: data.failedStage || null,
  errorMessage: data.error || data.message || null,
})
// 添加调试日志
if (normalizedStage && normalizedStage.toLowerCase().includes('render')) {
  logger.debug(`[useWebSocket] Render state updated for ${episodeId}: stage=${normalizedStage}, progress=${progress}`)
}
```

## 判断启动渲染的条件

### 后端条件

**位置**: `kat_rec_web/backend/t2r/services/render_queue.py`

1. **前置条件检查**: `validate_render_prerequisites` 检查必需文件
   - cover (封面)
   - audio (音频)
   - title (标题)
   - description (描述)
   - captions (字幕)

2. **等待机制**: 如果前置条件不满足，等待最多 5 分钟

3. **状态流程**:
   - `RENDER_QUEUE` (render.queue) - 排队中
   - `RENDER_ACTIVE` (render.in_progress) - 正在渲染
   - `RENDER_DONE` (render.done) - 渲染完成

### 前端条件

**位置**: `kat_rec_web/frontend/components/mcrb/RenderQueuePanel.tsx`

1. **准备完成**: `stages.preparation.done === true`
   - 所有准备资产完成（playlist, cover, title, description, captions, audio）

2. **渲染未完成**: `stages.render.done === false`

3. **渲染未进行**: `stages.render.inProgress === false`

## 异步/串行/时序/并发问题评估

### 已实施的并发控制 ✅

1. **Schedule 更新锁** (`schedule_service.py`): 每个 channel 一个锁，带超时（5秒）
2. **Render queue 锁** (`render_queue.py`): 带超时（5秒）
3. **Plan queue 锁** (`plan.py`): 带超时（5秒）
4. **Channel automation 锁** (`channel_automation.py`): 带超时（5秒）
5. **原子性文件写入**: 临时文件+原子重命名
6. **Timeline CSV 写入增强**: flush + fsync + 验证

### 剩余问题 ⚠️

1. **Plan.py 中的同步 Schedule 更新** (2处):
   - Lines 1690-1699: 直接调用 `load_schedule_master` + `save_schedule_master`
   - Lines 1871-1882: 直接调用 `load_schedule_master` + `save_schedule_master`
   - **建议**: 迁移到 `async_update_schedule_atomic` 或添加文件锁

2. **前端状态更新的竞态条件** (已缓解):
   - 使用时间戳检查防止旧事件覆盖新事件
   - 使用 `batchedPatchEvent` 批量更新
   - **建议**: 继续监控，考虑添加状态版本号

3. **文件系统延迟** (已缓解):
   - Timeline CSV 写入后使用 `flush()` + `fsync()` + `time.sleep(0.1)`
   - 文件写入后验证文件存在性和可读性
   - **建议**: 继续监控，考虑添加重试机制

详细评估见 `CONCURRENCY_EVALUATION.md`。

## 测试建议

1. **验证渲染状态显示**:
   - 启动渲染后，检查前端是否正确显示"渲染中"而不是"等待渲染"
   - 检查浏览器控制台的调试日志，确认状态更新流程

2. **验证并发控制**:
   - 同时启动多个渲染任务，检查是否有冲突
   - 检查日志中是否有锁超时错误

3. **验证状态同步**:
   - 检查 WebSocket 事件是否正确传递 `render.in_progress` 状态
   - 检查前端状态是否及时更新

## 预期结果

1. ✅ 前端能正确识别 `render.in_progress` 状态，显示"渲染中"而不是"等待渲染"
2. ✅ 渲染状态更新及时且准确
3. ✅ 所有并发问题都已解决或已识别

## 后续改进建议

1. 迁移 plan.py 中的同步 schedule 更新到异步原子更新
2. 添加前端状态更新的版本号验证
3. 为所有文件写入操作添加重试机制
4. 添加并发测试以验证修复的有效性

