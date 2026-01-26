# GridProgressSimple 进度条调试文档

## 1. 进度计算逻辑分析

### Audio Progress (音频进度)

**后端 API**: `/api/t2r/episodes/{episode_id}/audio-progress`

**计算逻辑**:
- 基于文件大小: `current_size / estimated_final_size * 100`
- `estimated_final_size` = `duration_hours * 75MB` (每小时的MP3大小，320kbps)
- 映射到 **10-95%** 范围（因为 remix 是 preparation 的 10-100%）
- `is_complete` = `timeline_csv` 文件存在
- 如果完成，`progress = 100`

**前端映射**:
```typescript
// GridProgressSimple.tsx:264-268
<ProgressLineSimple
  type="audio"
  progress={audioProgress?.progress ?? null}  // 直接使用 API 返回的 progress
  isActive={audioProgress?.is_remixing ?? false}
  isComplete={audioProgress?.is_complete ?? false}  // 如果 true，ProgressLineSimple 会显示 100%
/>
```

**ProgressLineSimple 逻辑**:
```typescript
// ProgressLineSimple.tsx:95-108
if (isComplete) {
  progressWidth = 100  // ✅ 完成时强制 100%
} else if (progress !== null && progress !== undefined && progress > 0) {
  progressWidth = Math.max(0, Math.min(100, progress))  // 使用实际 progress 值
} else {
  progressWidth = 0  // 无进度
}
```

### Video Progress (视频进度)

**后端 API**: `/api/t2r/episodes/{episode_id}/video-progress`

**计算逻辑**:
- 基于文件大小: `current_size / estimated_final_size * 100`
- `estimated_final_size` = `duration_hours * 500MB` (每小时的视频大小，1080p H.264)
- **上限 95%**，直到 `render_complete_flag` 存在
- `is_complete` = `render_complete_flag` 文件存在
- 如果完成，`progress = 100`

**前端映射**:
```typescript
// GridProgressSimple.tsx:281-287
<ProgressLineSimple
  type="video"
  progress={videoProgress?.progress ?? null}  // 直接使用 API 返回的 progress
  isActive={videoProgress?.is_rendering ?? false}
  isComplete={videoIsComplete}  // ✅ 使用计算后的 videoIsComplete（包含多个检查）
/>
```

**videoIsComplete 计算逻辑**:
```typescript
// GridProgressSimple.tsx:81-139
Priority 1: videoProgress?.is_complete === true  → 返回 true
Priority 2: videoProgress?.video_path && videoProgress?.render_complete_flag  → 返回 true
Priority 3: event?.assets?.video && event?.assets?.render_complete_flag  → 返回 true
否则: 返回 false
```

**问题点**:
- 如果 `videoProgress.progress = 28.59%` 但 `is_complete = false`
- 且 `videoProgress.video_path` 和 `videoProgress.render_complete_flag` 都不存在
- 且 `event.assets.video` 和 `event.assets.render_complete_flag` 都不存在
- 则 `videoIsComplete = false`，进度条显示 28.59% 而不是 100%

### Upload/Verify Progress (上传/验证进度)

**数据来源**: `event.uploadState` (来自 WebSocket `upload_state_changed` 事件)

**状态枚举**:
- `pending`: 0% (灰色)
- `queued`: 20% (蓝色动画)
- `uploading`: 100% (蓝色强动画)
- `uploaded`: 100% (蓝色脉冲)
- `verifying`: 100% (黄色脉冲)
- `verified`: 100% (绿色静态)
- `failed`: 0% (红色闪烁)
- `paused`: 100% (黄色半透明，API限额)

**前端映射**:
```typescript
// GridProgressSimple.tsx:299-304
<ProgressLineSimple
  type="upload"
  uploadState={uploadState?.state ?? null}
  verifyState={verifyState?.state ?? null}
/>
```

**ProgressLineSimple 逻辑**:
```typescript
// ProgressLineSimple.tsx:125-136
if (state === 'verified') {
  progressWidth = 100
} else if (state === 'uploaded' || state === 'verifying') {
  progressWidth = 100  // 全宽，但不同颜色/动画
} else if (state === 'uploading') {
  progressWidth = 100  // 全宽，动画
} else if (state === 'queued') {
  progressWidth = 20  // 小宽度显示排队
} else {
  progressWidth = 0  // pending 或 failed
}
```

## 2. 可能的问题点

### 问题 1: Video Progress 显示不准确

**症状**: 视频已完成，但进度条显示 28.59% 而不是 100%

**可能原因**:
1. `videoProgress.is_complete = false` (后端未检测到 `render_complete_flag`)
2. `videoProgress.video_path = null` (后端未找到视频文件)
3. `videoProgress.render_complete_flag = null` (后端未找到 flag 文件)
4. `event.assets.video = null` (前端 store 未更新)
5. `event.assets.render_complete_flag = null` (前端 store 未更新)

**调试方法**:
```javascript
// 在浏览器控制台执行
const eventId = '20251123'
const s = window.__KAT_STORE__?.getState()
const e = s?.eventsById?.[eventId]

console.log('=== Store Event ===')
console.log('Event:', e)
console.log('Event.assets.video:', e?.assets?.video)
console.log('Event.assets.video_path:', e?.assets?.video_path)
console.log('Event.assets.render_complete_flag:', e?.assets?.render_complete_flag)
console.log('Event.uploadState:', e?.uploadState)

Promise.all([
  fetch(`/api/t2r/episodes/${eventId}/audio-progress?channel_id=kat_lofi`).then(r => r.json()),
  fetch(`/api/t2r/episodes/${eventId}/video-progress?channel_id=kat_lofi`).then(r => r.json()),
  fetch(`/api/t2r/episodes/${eventId}/assets?channel_id=kat_lofi`).then(r => r.json())
]).then(([audio, video, assets]) => {
  console.log('=== API Responses ===')
  console.log('Audio Progress:', audio)
  console.log('Video Progress:', video)
  console.log('Assets:', assets)
  
  console.log('=== Analysis ===')
  console.log('Video is_complete:', video.is_complete)
  console.log('Video video_path:', video.video_path)
  console.log('Video render_complete_flag:', video.render_complete_flag)
  console.log('Video progress:', video.progress)
  console.log('Video is_rendering:', video.is_rendering)
})
```

### 问题 2: Audio Progress 显示不准确

**症状**: 音频已完成，但进度条显示 < 100%

**可能原因**:
1. `audioProgress.is_complete = false` (后端未检测到 `timeline_csv`)
2. `audioProgress.progress` 计算错误（文件大小估算不准确）

**调试方法**: 同上，检查 `audio.is_complete` 和 `audio.progress`

### 问题 3: Upload/Verify 状态不准确

**症状**: 上传已完成，但进度条显示错误状态

**可能原因**:
1. `event.uploadState` 未更新（WebSocket 未收到事件）
2. `event.uploadState.state` 值不正确

**调试方法**: 检查 `event.uploadState` 和 WebSocket 消息

## 3. 调试工具

在浏览器控制台执行以下代码来调试特定事件：

```javascript
// 调试函数
async function debugGridProgress(eventId, channelId = 'kat_lofi') {
  const s = window.__KAT_STORE__?.getState()
  const e = s?.eventsById?.[eventId]
  
  console.log('=== GridProgressSimple Debug ===')
  console.log('Event ID:', eventId)
  console.log('Channel ID:', channelId)
  
  // Store data
  console.log('\n--- Store Event ---')
  console.log('Event exists:', !!e)
  if (e) {
    console.log('Event.assets.video:', e.assets?.video)
    console.log('Event.assets.video_path:', e.assets?.video_path)
    console.log('Event.assets.render_complete_flag:', e.assets?.render_complete_flag)
    console.log('Event.uploadState:', e.uploadState)
  }
  
  // API data
  console.log('\n--- API Data ---')
  try {
    const [audio, video, assets] = await Promise.all([
      fetch(`/api/t2r/episodes/${eventId}/audio-progress?channel_id=${channelId}`).then(r => r.json()),
      fetch(`/api/t2r/episodes/${eventId}/video-progress?channel_id=${channelId}`).then(r => r.json()),
      fetch(`/api/t2r/episodes/${eventId}/assets?channel_id=${channelId}`).then(r => r.json())
    ])
    
    console.log('Audio Progress:', audio)
    console.log('Video Progress:', video)
    console.log('Assets:', assets)
    
    // Analysis
    console.log('\n--- Analysis ---')
    console.log('Audio:')
    console.log('  is_complete:', audio.is_complete)
    console.log('  progress:', audio.progress)
    console.log('  is_remixing:', audio.is_remixing)
    
    console.log('Video:')
    console.log('  is_complete:', video.is_complete)
    console.log('  progress:', video.progress)
    console.log('  is_rendering:', video.is_rendering)
    console.log('  video_path:', video.video_path)
    console.log('  render_complete_flag:', video.render_complete_flag)
    
    console.log('Upload/Verify:')
    console.log('  uploadState:', e?.uploadState?.state)
    console.log('  verifyState:', e?.uploadState?.state === 'verified' ? 'verified' : e?.uploadState?.state === 'verifying' ? 'verifying' : 'none')
    
    // Expected UI values
    console.log('\n--- Expected UI Values ---')
    const audioComplete = audio.is_complete
    const audioProgressValue = audioComplete ? 100 : (audio.progress ?? 0)
    console.log('Audio bar:', {
      progress: audioProgressValue,
      isComplete: audioComplete,
      label: audioComplete ? '✓ 完成' : `${Math.round(audioProgressValue)}%`
    })
    
    const videoComplete = video.is_complete || (video.video_path && video.render_complete_flag) || (e?.assets?.video && e?.assets?.render_complete_flag)
    const videoProgressValue = videoComplete ? 100 : (video.progress ?? 0)
    console.log('Video bar:', {
      progress: videoProgressValue,
      isComplete: videoComplete,
      label: videoComplete ? '✓ 完成' : `${Math.round(videoProgressValue)}%`
    })
    
    const uploadState = e?.uploadState?.state || 'pending'
    console.log('Upload/Verify bar:', {
      state: uploadState,
      width: uploadState === 'verified' ? 100 : uploadState === 'uploaded' || uploadState === 'verifying' ? 100 : uploadState === 'uploading' ? 100 : uploadState === 'queued' ? 20 : 0
    })
    
  } catch (error) {
    console.error('Error fetching API data:', error)
  }
}

// 使用示例
// debugGridProgress('20251123', 'kat_lofi')
```

## 4. 修复建议

### 修复 1: 增强 videoIsComplete 检测

如果视频文件存在但 `is_complete` 为 false，应该检查文件是否真的在增长：
- 如果文件大小稳定（多次检查大小不变），且文件大小 > 预期大小的 90%，应该认为完成
- 或者，如果 `video_path` 存在且文件大小合理（> 100MB），应该认为完成

### 修复 2: 添加文件大小验证

在 `videoIsComplete` 中，如果 `videoProgress.video_path` 存在，应该检查文件大小是否合理：
- 如果文件大小 > 预期大小的 90%，即使没有 `render_complete_flag`，也应该认为完成

### 修复 3: 添加后端日志

在后端 `get_video_render_progress` 中添加详细日志：
- 记录文件大小、预期大小、计算出的进度
- 记录 `render_complete_flag` 是否存在
- 记录 `is_complete` 的判断逻辑

