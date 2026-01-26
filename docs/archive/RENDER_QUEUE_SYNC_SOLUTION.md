# 渲染队列同步问题解决方案

## 问题描述

渲染队列无法正确反映期数的渲染状态：
1. **已渲染完成的期数（12-16）无法离开渲染队列**
   - 显示为"等待渲染"状态
   - 实际上已经渲染完成（有视频文件）

2. **渲染就绪的期数（17,18,19）无法进入渲染队列**
   - 准备已完成（音频、封面、标题、描述、字幕都有）
   - 但队列中没有显示

## 根本原因

### 1. 缺少 `render_complete_flag`

**问题**：
- 12-15期有视频文件，但缺少 `render_complete_flag`
- 前端判断 `renderDone` 需要：`(video || video_path) && render_complete_flag`
- 没有 flag，前端认为渲染未完成

**状态**：
- ✅ 20251116: 有 `render_complete_flag`
- ❌ 20251112-20251115: 缺少 `render_complete_flag`

### 2. `schedule_master.json` 中的资产信息不完整

**问题**：
- 文件系统中的资产文件存在，但 `schedule_master.json` 中没有记录
- 前端依赖 `schedule_master.json` 中的 `assets` 字段判断状态
- 如果 `assets` 字段不完整，前端无法正确判断准备是否完成

**示例**：
- 17,18,19期在文件系统中有所有必需文件
- 但 `schedule_master.json` 中可能缺少 `assets.timeline_csv` 等字段

## 解决方案

### 1. 创建资产同步服务

**文件**：`kat_rec_web/backend/t2r/services/render_queue_sync.py`

**功能**：
- `sync_episode_assets_from_filesystem()`: 从文件系统同步单个期数的资产
- `sync_all_episodes_assets()`: 同步所有期数的资产
- `get_episodes_ready_for_render()`: 获取准备好渲染的期数
- `get_episodes_with_completed_render()`: 获取已完成渲染的期数

**同步逻辑**：
1. 检查文件系统中的所有资产文件
2. 更新 `schedule_master.json` 中的 `assets` 字段
3. 为已完成的渲染创建 `render_complete_flag`（如果缺失）

### 2. 修改 `list_episodes` 自动同步

**文件**：`kat_rec_web/backend/t2r/routes/episodes.py`

**修改**：
- 在返回期数列表前，自动同步每个期数的资产信息
- 确保 `assets.render_complete_flag` 被包含在返回数据中

### 3. 创建同步 API 端点

**文件**：`kat_rec_web/backend/t2r/routes/render_queue_sync.py`

**端点**：
- `POST /api/t2r/render-queue-sync/sync-all`: 同步所有期数的资产
- `GET /api/t2r/render-queue-sync/ready-for-render`: 获取准备好渲染的期数
- `GET /api/t2r/render-queue-sync/completed-renders`: 获取已完成渲染的期数

### 4. 为已完成的期数创建 `render_complete_flag`

**已执行**：
- ✅ 为 20251112-20251115 创建了 `render_complete_flag`
- ✅ 使用 ffprobe 验证视频完整性后创建 flag

## 使用说明

### 立即修复当前状态

**方法1：调用同步 API**
```bash
curl -X POST http://localhost:8000/api/t2r/render-queue-sync/sync-all \
  -H "Content-Type: application/json" \
  -d '{"channel_id": "kat_lofi"}'
```

**方法2：刷新前端页面**
- `list_episodes` 现在会自动同步资产信息
- 刷新页面后，队列状态应该会更新

### 定期同步（建议）

**前端可以定期调用同步 API**：
- 每30秒自动调用 `sync-all` 端点
- 确保队列状态始终与文件系统同步

## 验证

### 检查12-16期是否离开队列

**条件**：
- `assets.video` 存在
- `assets.render_complete_flag` 存在
- `calculateStageStatus` 返回 `render.done = true`
- `RenderQueuePanel` 应该不再显示这些期数

### 检查17,18,19期是否进入队列

**条件**：
- `assets.audio` 存在
- `assets.timeline_csv` 存在
- `assets.cover` 存在
- `title` 存在
- `assets.description` 存在
- `assets.captions` 存在
- `calculateStageStatus` 返回 `preparation.done = true`
- `calculateStageStatus` 返回 `render.done = false`
- `RenderQueuePanel` 应该显示这些期数

## 技术细节

### 渲染完成判断逻辑

**前端** (`scheduleStore.ts` line 950-953):
```typescript
const renderDone = !!(
  (event.assets.video || event.assets.video_path) &&
  event.assets.render_complete_flag  // ✅ 必须存在旗标文件
)
```

**后端** (`plan.py` line 1956-1975):
- 渲染完成后，使用 ffprobe 验证视频完整性
- 验证成功后创建 `render_complete_flag`
- 广播事件时包含 `render_complete_flag` 路径

### 准备完成判断逻辑

**前端** (`scheduleStore.ts` line 1026-1030):
```typescript
const preparationAssets = [playlistDone, coverDone, titleDone, descriptionDone, captionsDone, audioDone]
const preparationProgress = preparationAssets.filter(Boolean).length / preparationAssets.length
const preparationDone = preparationProgress >= 1.0  // 必须100%完成
```

**音频完成判断** (line 889-912):
```typescript
const isAudioMixed = (audioPath, timelineCsv) => {
  if (!audioPath) return false
  // ✅ 严格要求：必须有 timeline_csv 才认为完成
  if (timelineCsv && timelineCsv.includes('_full_mix_timeline.csv')) {
    return audioPath.includes('_full_mix.mp3')
  }
  return false
}
```

## 后续改进建议

1. **定期自动同步**：前端可以设置定时器，每30秒自动同步一次
2. **WebSocket 事件增强**：确保所有资产更新都通过 WebSocket 实时推送
3. **状态验证**：在渲染队列面板显示前，验证文件系统状态

