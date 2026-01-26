# 音频进度更新和前端状态监控实施总结

## 概述

已成功实施基于文件大小的音频渲染进度更新方案，并按照优先级实施了前端状态更新监控方案。

## 1. 音频渲染进度更新（基于文件大小）

### 1.1 后端 API 端点

**文件**: `kat_rec_web/backend/t2r/routes/episodes.py`

**新增端点**: `GET /t2r/episodes/{episode_id}/audio-progress`

**功能**:
- 检查 `full_mix.mp3` 文件是否存在和大小
- 检查 `timeline_csv` 是否存在以判断是否完成
- 从 schedule 获取实际时长（`durationSec`）以更准确估算
- 基于文件大小和预期时长计算进度（10-100% 范围，映射到 remix 阶段）

**进度计算逻辑**:
1. 如果 `timeline_csv` 存在 → 进度 = 100%（remix 完成）
2. 如果文件存在且大小 > 100KB → 正在 remixing
   - 从 schedule 获取实际时长
   - 估算最终文件大小：`时长（小时） × 75MB/小时`（MP3 320kbps）
   - 计算进度：`10% + (当前大小 / 预期大小) × 85%`
   - 上限 95%（直到 timeline_csv 存在）
3. 如果文件存在但大小 < 100KB → 进度 = 10%（刚开始）
4. 如果文件不存在 → 进度 = null

### 1.2 前端 API 服务

**文件**: `kat_rec_web/frontend/services/t2rApi.ts`

**新增函数**: `getAudioRemixProgress(episode_id, channel_id)`

**类型**: `AudioRemixProgress` 接口

### 1.3 前端轮询 Hook

**文件**: `kat_rec_web/frontend/hooks/useAudioRemixProgress.ts` (新建)

**功能**:
- 每 2 秒轮询一次后端 API
- 仅在 remix 进行中且未完成时启用
- 检测文件大小稳定性（连续 3 次相同 = 6 秒）
- remix 完成后自动停止轮询

**优化**:
- 条件启用：仅在需要时轮询
- 稳定检测：文件大小稳定时减少更新频率
- 自动停止：完成后立即停止

### 1.4 进度计算函数更新

**文件**: `kat_rec_web/frontend/utils/progressCalculators.ts`

**修改**: `calculatePreparationProgress` 添加可选参数 `fileSizeProgress`

**优先级**:
1. 文件大小进度（如果提供且有效）
2. WebSocket 实时进度（fallback）
3. 默认 10%（remix 阶段最小值）

### 1.5 GridProgressIndicator 组件更新

**文件**: `kat_rec_web/frontend/components/mcrb/GridProgressIndicator.tsx`

**修改**:
- 导入并使用 `useAudioRemixProgress` hook
- 将音频文件大小进度传递给 `calculatePreparationProgress`
- 仅在 remix 进行中时启用轮询

## 2. 前端状态更新监控方案（高优先级）

### 2.1 状态更新日志

**位置**: `kat_rec_web/frontend/hooks/useWebSocket.ts`

**实现**: 在 `batchedPatchEvent` 函数中添加开发环境日志

**功能**:
- 记录每次批处理更新的详细信息
- 包括 episodeId、更新字段、时间戳、待处理数量、是否关键更新、阶段信息
- 仅在开发环境或 `?debug=true` 时启用

**日志格式**:
```typescript
console.debug('[StateUpdate] Batched update:', {
  episodeId,
  updates: Object.keys(updates),
  timestamp: Date.now(),
  pendingCount: pendingUpdatesRef.current.size,
  isCritical: options?.immediate || isCriticalUpdate(updates, options?.stage),
  stage: options?.stage,
})
```

### 2.2 时间戳冲突检测

**位置**: `kat_rec_web/frontend/hooks/useWebSocket.ts`

**实现**: 在时间戳检查后添加警告

**功能**:
- 检测时间戳冲突（两个事件时间戳相差 < 100ms）
- 记录冲突详情：episodeId、两个时间戳、差值、阶段、进度
- 仅在开发环境或 `?debug=true` 时启用

**检测逻辑**:
```typescript
if (Math.abs(eventTimestamp - lastStageTimestamp) < 100) {
  console.warn('[StateUpdate] Potential timestamp conflict:', {
    episodeId,
    eventTimestamp,
    lastStageTimestamp,
    diff: Math.abs(eventTimestamp - lastStageTimestamp),
    stage: data.stage,
    progress: data.progress,
  })
}
```

### 2.3 状态一致性检查

**位置**: `kat_rec_web/frontend/stores/scheduleStore.ts`

**实现**: 在 `patchEvent` 函数中添加一致性检查

**功能**:
- 检查更新前后的状态一致性
- 检测以下问题：
  - `assets` 对象是否丢失
  - `gridProgress.lastStageTimestamp` 是否倒退
  - 关键资产字段是否丢失（`audio`、`video`、`timeline_csv`）
- 仅在开发环境或 `?debug=true` 时启用

**检查项**:
1. **Assets 丢失**: 如果更新前有 `assets`，更新后没有，记录警告
2. **时间戳倒退**: 如果 `gridProgress.lastStageTimestamp` 变小，记录警告
3. **关键资产丢失**: 如果更新前有 `audio`/`video`/`timeline_csv`，更新后没有，记录警告

**警告格式**:
```typescript
console.warn('[StateUpdate] State inconsistency detected:', {
  eventId,
  inconsistencies: ['assets lost', 'gridProgress timestamp regressed: ...', 'audio asset lost'],
  before: beforeState,
  after: updatedEvent,
})
```

## 3. 实施效果

### 3.1 音频进度更新

✅ **更准确的进度反馈**:
- 基于实际文件大小，不依赖 WebSocket 事件的及时性
- 实时更新（每 2 秒轮询一次）
- 基于实际时长和文件大小计算

✅ **更可靠的完成检测**:
- 双重验证：文件大小 + `timeline_csv`
- 防止误判：即使文件存在，也检查 timeline_csv 确认完成
- 稳定检测：文件大小稳定 6 秒后假设接近完成

✅ **更好的用户体验**:
- 连续进度：即使 WebSocket 事件延迟，也能看到进度更新
- 视觉反馈：进度条平滑增长，提供实时反馈
- 自动停止：remix 完成后自动停止轮询，节省资源

### 3.2 前端状态监控

✅ **开发调试支持**:
- 详细的状态更新日志，便于追踪问题
- 时间戳冲突检测，发现并发问题
- 状态一致性检查，发现数据丢失问题

✅ **生产环境安全**:
- 所有监控功能仅在开发环境或 `?debug=true` 时启用
- 不影响生产环境性能
- 可通过 URL 参数临时启用调试

## 4. 使用说明

### 4.1 启用调试模式

在浏览器 URL 中添加 `?debug=true` 参数即可启用所有监控功能：

```
http://localhost:3000/channel?debug=true
```

### 4.2 查看监控日志

打开浏览器开发者工具（F12），在 Console 标签页中查看：

- **调试日志**: `[StateUpdate] Batched update:` - 每次状态更新
- **警告日志**: `[StateUpdate] Potential timestamp conflict:` - 时间戳冲突
- **警告日志**: `[StateUpdate] State inconsistency detected:` - 状态不一致

### 4.3 监控指标

**状态更新日志**:
- `episodeId`: 更新的 episode ID
- `updates`: 更新的字段列表
- `timestamp`: 更新时间戳
- `pendingCount`: 待处理的更新数量
- `isCritical`: 是否为关键更新
- `stage`: 当前阶段

**时间戳冲突检测**:
- `episodeId`: 冲突的 episode ID
- `eventTimestamp`: 新事件时间戳
- `lastStageTimestamp`: 上次阶段时间戳
- `diff`: 时间戳差值（毫秒）
- `stage`: 阶段信息
- `progress`: 进度信息

**状态一致性检查**:
- `eventId`: 事件 ID
- `inconsistencies`: 不一致项列表
- `before`: 更新前状态
- `after`: 更新后状态

## 5. 后续改进建议

### 5.1 音频进度估算优化

- 使用 ffprobe 获取实际码率
- 基于历史数据动态调整估算
- 考虑内容复杂度（静态 vs 动态）

### 5.2 监控功能增强

- 添加版本号/序列号机制
- 使用乐观锁机制
- 添加状态快照机制
- 性能监控（批处理耗时）

### 5.3 自适应轮询

- 渲染初期：更频繁轮询（1 秒）
- 渲染中期：正常轮询（2 秒）
- 接近完成：减少轮询（5 秒）

## 6. 总结

已成功实施：

1. ✅ **音频渲染进度更新**：基于文件大小的实时进度反馈
2. ✅ **前端状态更新监控**：高优先级的监控功能（日志、时间戳冲突检测、状态一致性检查）

所有功能已通过 lint 检查，可以立即使用。监控功能仅在开发环境或 `?debug=true` 时启用，不影响生产环境性能。

