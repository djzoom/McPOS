# Render Progress Unification - Stateflow V4 Phase 3.1

**日期**: 2025-01-XX  
**状态**: ✅ 已完成

---

## 概述

渲染进度系统已统一到单一后端 API 和单一前端 hook，消除了状态漂移、重复逻辑、遗留轮询和启发式检测。

## 架构

### 后端

**单一服务**: `kat_rec_web/backend/t2r/services/render_progress_service.py`
- `get_video_progress(channel_id, episode_id)` - 统一的渲染进度检测
- 仅使用文件系统检查（无 ASR 或 registry 依赖）
- 检查 `*_render_complete.flag`、视频文件大小、mtime 稳定性

**单一端点**: `GET /api/t2r/episodes/{episode_id}/video-progress?channel_id={channelId}`
- 位置: `kat_rec_web/backend/t2r/routes/episodes.py`
- 返回格式:
  ```json
  {
    "episode_id": "20251123",
    "channel_id": "kat_lofi",
    "is_rendering": true|false,
    "is_complete": true|false,
    "progress": 0-100 as float,
    "video_size": int (bytes),
    "last_modified": "ISO8601 string",
    "source": "filesystem"
  }
  ```

**WebSocket 事件** (仅通知):
- `t2r.episode.render_started` - 触发前端 refetch
- `t2r.episode.render_completed` - 触发前端 refetch
- `t2r.episode.render_failed` - 触发前端 refetch

### 前端

**单一 Hook**: `useVideoProgress({ channelId, episodeId })`
- 位置: `kat_rec_web/frontend/hooks/useVideoProgress.ts`
- 智能轮询: 渲染中每 5 秒，完成时停止
- WebSocket 集成: 监听渲染事件并触发 refetch
- 返回: `{ isRendering, isComplete, progress, videoSize, lastModified, isLoading, isError }`

**组件使用**:
- `GridProgressSimple` - 使用 `useVideoProgress` 显示渲染进度
- `OverviewGrid` - 使用文件系统检查替代 `calculateStageStatus`
- `TaskPanel` - 使用 `useEpisodeAssets` + `useVideoProgress` 判断操作可用性

## 已移除/弃用

### 后端
- ❌ 旧的 `video_progress_detector.py` (如果存在)
- ❌ `render_queue.py` 中的进度存储逻辑 (已移除，仅保留通知)

### 前端
- ❌ `calculateStageStatus()` - 已禁用，返回空状态
- ❌ `calculateAssetStageReadiness()` - 已禁用，返回空状态
- ⚠️ `assetUtils.hasVideo()` - 已标记为 `@deprecated`，使用 `useVideoProgress()` 替代
- ⚠️ `assetUtils.hasVideoStarted()` - 已标记为 `@deprecated`，使用 `useVideoProgress().isRendering` 替代
- ❌ `GridProgressIndicator` - 已替换为 `GridProgressSimple`

## 迁移指南

### 对于新代码

**渲染进度检测**:
```typescript
// ✅ 正确
const videoProgress = useVideoProgress({ channelId, episodeId })
if (videoProgress.isComplete) {
  // 渲染完成
}

// ❌ 错误
const stages = calculateStageStatus(event, runbookState)
if (stages.render.done) {
  // 不要使用
}
```

**资产检测**:
```typescript
// ✅ 正确
const assets = useEpisodeAssets(channelId, episodeId)
if (assets.data?.hasVideo) {
  // 视频文件存在
}

// ❌ 错误
if (hasVideo(event)) {
  // 不要使用已弃用的工具函数
}
```

## 测试场景

1. ✅ 渲染前 (无 MP4) → UI 显示灰色/未开始
2. ✅ 渲染中 (ffmpeg 写入) → UI 显示黄色进度条，显示进度百分比
3. ✅ 渲染完成 (flag 文件存在) → UI 显示绿色 100%
4. ✅ 页面刷新 → 状态持久化
5. ✅ 多个期数 → 每个独立轮询
6. ✅ 渲染重启 → UI 恢复为黄色进度

## 阈值配置

在 `render_progress_service.py` 中:
- `LARGE_FILE_THRESHOLD_BYTES = 100 * 1024 * 1024` (100 MB)
- `STABLE_SECONDS_THRESHOLD = 5 * 60` (5 分钟)
- `RECENT_MODIFICATION_SECONDS = 2 * 60` (2 分钟)

## 相关文档

- `docs/RENDER_PROGRESS_SYSTEM_AUDIT.md` - 审计报告
- `docs/STATEFLOW_V4_MIGRATION_REPORT.md` - Stateflow V4 迁移报告

