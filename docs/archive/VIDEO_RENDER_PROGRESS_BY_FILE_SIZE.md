# 基于文件大小的视频渲染进度更新方案

## 概述

实现了通过观测 MP4 文件大小来更新 GridProgressIndicator 第二条（渲染进度条）的功能。这提供了比 WebSocket 事件更准确和实时的渲染进度反馈。

## 实现方案

### 1. 后端 API 端点

**文件**: `kat_rec_web/backend/t2r/routes/episodes.py`

**端点**: `GET /t2r/episodes/{episode_id}/video-progress`

**功能**:
- 检查视频文件是否存在
- 获取当前文件大小
- 检查 `render_complete_flag` 是否存在
- 根据文件大小和预期时长估算进度
- 返回进度信息（0-100%）

**进度计算逻辑**:
1. 如果 `render_complete_flag` 存在 → 进度 = 100%
2. 如果文件存在且大小 > 1MB → 正在渲染
   - 从 schedule 获取实际时长（`durationSec`）
   - 估算最终文件大小：`时长（小时） × 500MB/小时`
   - 计算进度：`当前大小 / 预期大小 × 100%`
   - 上限 95%（直到 flag 文件存在）
3. 如果文件存在但大小 < 1MB → 进度 = 5%（刚开始）
4. 如果文件不存在 → 进度 = null

**返回数据**:
```json
{
  "episode_id": "20251112",
  "video_path": "/path/to/video.mp4",
  "video_size": 524288000,  // bytes
  "expected_size": 750000000,  // bytes (基于时长估算)
  "progress": 69.9,  // 0-100
  "is_rendering": true,
  "is_complete": false,
  "timestamp": "2025-01-12T10:30:00Z"
}
```

### 2. 前端 API 服务

**文件**: `kat_rec_web/frontend/services/t2rApi.ts`

**函数**: `getVideoRenderProgress(episode_id, channel_id)`

**功能**:
- 调用后端 API 获取视频渲染进度
- 返回类型化的 `VideoRenderProgress` 对象

### 3. 前端轮询 Hook

**文件**: `kat_rec_web/frontend/hooks/useVideoRenderProgress.ts`

**Hook**: `useVideoRenderProgress({ episodeId, channelId, enabled, pollInterval })`

**功能**:
- 轮询后端 API 获取文件大小进度（默认每 2 秒）
- 仅在渲染进行中且未完成时启用
- 检测文件大小是否稳定（连续 3 次相同 = 6 秒）
- 自动停止轮询当渲染完成

**返回**:
```typescript
{
  progress: number | null,  // 0-100 或 null
  videoSize: number | null,  // 文件大小（字节）
  isRendering: boolean,
  isComplete: boolean
}
```

**优化**:
- 文件大小稳定检测：如果连续 3 次轮询（6 秒）文件大小不变，假设接近完成
- 自动停止：当 `is_complete` 为 true 时停止轮询
- 条件启用：仅在渲染进行中时启用轮询

### 4. 进度计算函数更新

**文件**: `kat_rec_web/frontend/utils/progressCalculators.ts`

**函数**: `calculateRenderQueueProgress(...)`

**修改**:
- 添加可选参数 `fileSizeProgress?: number | null`
- 优先使用文件大小进度（如果提供）
- Fallback 到 WebSocket 进度（如果文件大小进度不可用）

**优先级**:
1. 文件大小进度（如果提供且有效）
2. WebSocket 实时进度
3. 默认 50%（渲染中但无进度信息）

### 5. GridProgressIndicator 组件更新

**文件**: `kat_rec_web/frontend/components/mcrb/GridProgressIndicator.tsx`

**修改**:
- 导入 `useVideoRenderProgress` hook
- 在渲染进行中时调用 hook 获取文件大小进度
- 将文件大小进度传递给 `calculateRenderQueueProgress`

**启用条件**:
- `isRenderInProgress === true`（runbook state 显示正在渲染）
- `stageStatus.render.done === false`（渲染未完成）

## 优势

### 1. 更准确的进度反馈 ✅

- **文件大小是客观指标**：不依赖 WebSocket 事件的及时性
- **实时更新**：每 2 秒轮询一次，提供连续的进度反馈
- **基于实际数据**：使用实际文件大小和预期时长计算

### 2. 更可靠的完成检测 ✅

- **双重验证**：文件大小 + `render_complete_flag`
- **防止误判**：即使文件存在，也检查 flag 文件确认完成
- **稳定检测**：文件大小稳定 6 秒后假设接近完成

### 3. 更好的用户体验 ✅

- **连续进度**：即使 WebSocket 事件延迟，也能看到进度更新
- **视觉反馈**：进度条平滑增长，提供实时反馈
- **自动停止**：渲染完成后自动停止轮询，节省资源

## 技术细节

### 文件大小估算

**公式**:
```
预期文件大小 = 时长（小时） × 500MB/小时
进度 = min(95%, (当前大小 / 预期大小) × 100%)
```

**假设**:
- 1080p H.264 编码
- 平均码率约 500MB/小时
- 实际可能因内容复杂度而变化

**改进空间**:
- 可以使用 ffprobe 获取实际码率
- 可以根据历史数据动态调整估算
- 可以基于音频文件时长更准确地估算

### 轮询策略

**默认间隔**: 2 秒

**优化**:
- 仅在渲染进行中时启用
- 渲染完成后立即停止
- 文件大小稳定时减少更新频率

**资源消耗**:
- 每个渲染中的 episode 每 2 秒一次 API 调用
- 通常同时只有 1-2 个 episode 在渲染
- 总 API 调用频率：1-2 次/秒（可接受）

## 使用示例

```typescript
// 在 GridProgressIndicator 组件中
const { progress: fileSizeProgress } = useVideoRenderProgress({
  episodeId: eventId,
  channelId: event.channelId,
  enabled: isRenderInProgress && !stageStatus.render.done,
  pollInterval: 2000,
})

const renderQueueProgressPercentage = calculateRenderQueueProgress(
  event, 
  stageStatus, 
  effectiveRunbookState,
  fileSizeProgress // ✅ 传递文件大小进度
)
```

## 测试建议

1. **验证进度准确性**:
   - 启动渲染后，观察进度条是否平滑增长
   - 检查进度是否接近实际文件大小比例

2. **验证完成检测**:
   - 渲染完成后，检查进度是否显示 100%
   - 检查轮询是否自动停止

3. **验证资源使用**:
   - 检查浏览器网络标签，确认轮询频率合理
   - 确认渲染完成后轮询停止

4. **验证边界情况**:
   - 文件不存在时的行为
   - 文件大小很小（< 1MB）时的行为
   - 文件大小稳定时的行为

## 后续改进

### 1. 更准确的进度估算 🔄

- 使用 ffprobe 获取实际码率
- 基于历史数据动态调整估算
- 考虑内容复杂度（静态 vs 动态）

### 2. 自适应轮询间隔 🔄

- 渲染初期：更频繁轮询（1 秒）
- 渲染中期：正常轮询（2 秒）
- 接近完成：减少轮询（5 秒）

### 3. 文件大小历史记录 🔄

- 记录文件大小变化历史
- 基于变化率预测完成时间
- 检测异常（文件大小不增长 = 可能卡住）

### 4. 多文件支持 🔄

- 支持检查多个视频文件（如果存在多个版本）
- 选择最大的文件作为进度参考

## 总结

通过观测 MP4 文件大小来更新渲染进度是一个有效且可靠的方案。它提供了比 WebSocket 事件更准确和实时的进度反馈，同时保持了良好的用户体验和资源效率。实现已经完成，可以立即使用。

