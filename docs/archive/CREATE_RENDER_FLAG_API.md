# 创建 Render Flag API 使用说明

**日期**: 2025-01-XX  
**Endpoint**: `POST /api/t2r/plan/create-render-flag`

## 概述

这个 API endpoint 用于为已完成的视频文件创建 `render_complete_flag`，当视频文件已完整但 flag 未创建时使用。

## 功能

1. **自动查找视频文件**: 支持多种命名格式
   - `{episode_id}_final.mp4`
   - `{episode_id}.mp4`
   - `{episode_id}_youtube.mp4`

2. **ffprobe 验证**: 使用与渲染流程相同的验证逻辑，确保视频文件完整

3. **创建 flag 文件**: 验证成功后创建 flag，包含：
   - `render_completed_at`: 创建时间
   - `video_path`: 视频文件路径
   - `video_size`: 文件大小
   - `video_checksum`: 文件校验和（如果可用）
   - `duration`: 视频时长（从 ffprobe 获取）
   - `validated_by`: 验证方式（ffprobe）
   - `created_by`: 创建来源（create-render-flag-endpoint）

4. **自动更新状态**:
   - 更新 `schedule_master.json` 中的 `assets.render_complete_flag` 字段
   - 更新 Asset State Registry

5. **幂等操作**: 如果 flag 已存在，返回成功（不重复创建）

## 使用方法

### 使用 curl

```bash
curl -X POST http://localhost:8000/api/t2r/plan/create-render-flag \
  -H "Content-Type: application/json" \
  -d '{
    "episode_id": "20251117",
    "channel_id": "kat_lofi"
  }'
```

### 使用 JavaScript (浏览器控制台)

```javascript
fetch('http://localhost:8000/api/t2r/plan/create-render-flag', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    episode_id: '20251117',
    channel_id: 'kat_lofi'
  })
})
.then(res => res.json())
.then(data => {
  console.log('Flag creation result:', data)
  if (data.status === 'ok' && data.flag_created) {
    console.log('✅ Flag created successfully:', data.flag_path)
  } else if (data.status === 'ok' && !data.flag_created) {
    console.log('ℹ️ Flag already exists:', data.flag_path)
  } else {
    console.error('❌ Failed to create flag:', data.message, data.errors)
  }
})
```

### 使用 Python

```python
import requests

response = requests.post(
    'http://localhost:8000/api/t2r/plan/create-render-flag',
    json={
        'episode_id': '20251117',
        'channel_id': 'kat_lofi'
    }
)

result = response.json()
if result['status'] == 'ok' and result['flag_created']:
    print(f"✅ Flag created: {result['flag_path']}")
elif result['status'] == 'ok' and not result['flag_created']:
    print(f"ℹ️ Flag already exists: {result['flag_path']}")
else:
    print(f"❌ Failed: {result['message']}")
    print(f"Errors: {result['errors']}")
```

## 请求参数

```json
{
  "episode_id": "20251117",  // 必需：期数 ID
  "channel_id": "kat_lofi"   // 必需：频道 ID
}
```

## 响应格式

### 成功创建 flag

```json
{
  "status": "ok",
  "episode_id": "20251117",
  "flag_created": true,
  "flag_path": "channels/kat_lofi/output/20251117/20251117_render_complete.flag",
  "validation_success": true,
  "message": "Successfully created render_complete_flag for 20251117",
  "errors": []
}
```

### Flag 已存在

```json
{
  "status": "ok",
  "episode_id": "20251117",
  "flag_created": false,
  "flag_path": "channels/kat_lofi/output/20251117/20251117_render_complete.flag",
  "validation_success": true,
  "message": "Flag already exists",
  "errors": []
}
```

### 视频验证失败

```json
{
  "status": "error",
  "episode_id": "20251117",
  "flag_created": false,
  "flag_path": null,
  "validation_success": false,
  "message": "Video validation failed: ['ffprobe error: ...']",
  "errors": ["ffprobe error: ..."]
}
```

### 视频文件未找到

```json
{
  "status": "error",
  "episode_id": "20251117",
  "flag_created": false,
  "flag_path": null,
  "validation_success": false,
  "message": "Video file not found in channels/kat_lofi/output/20251117",
  "errors": ["Video file not found. Checked: ['20251117_final.mp4', '20251117.mp4', '20251117_youtube.mp4']"]
}
```

## 验证 flag 是否生效

### 1. 检查文件系统

```bash
ls -la channels/kat_lofi/output/20251117/*_render_complete.flag
cat channels/kat_lofi/output/20251117/20251117_render_complete.flag
```

### 2. 检查 schedule_master.json

```bash
# 查看 assets.render_complete_flag 字段
cat channels/kat_lofi/schedule_master.json | jq '.episodes[] | select(.episode_id == "20251117") | .assets.render_complete_flag'
```

### 3. 浏览器控制台检查

```javascript
// 等待前端同步后检查
const event = window.__KAT_STORE__.getState().eventsById['20251117']
console.log('Flag:', event?.assets?.render_complete_flag)
console.log('Render Ready:', calculateAssetStageReadiness(event).render.ready)
```

## 注意事项

1. **视频文件必须完整**: API 会使用 ffprobe 验证视频文件，如果验证失败，不会创建 flag
2. **幂等操作**: 多次调用不会重复创建 flag，如果已存在会返回成功
3. **自动更新**: 创建 flag 后会自动更新 `schedule_master.json` 和 Asset State Registry
4. **前端同步**: 创建 flag 后，前端需要重新加载 schedule 或等待 WebSocket 事件才能看到更新

## 故障排除

### 问题 1: 视频验证失败

**原因**: 视频文件可能不完整或损坏

**解决**:
1. 检查视频文件是否可以正常播放
2. 手动运行 ffprobe 验证：
   ```bash
   ffprobe -v error -show_entries format=duration \
     channels/kat_lofi/output/20251117/20251117_final.mp4
   ```

### 问题 2: Flag 创建成功但前端未显示

**原因**: 前端缓存或未同步

**解决**:
1. 刷新页面
2. 手动触发 schedule 同步：
   ```javascript
   // 在浏览器控制台
   window.__KAT_STORE__.getState().hydrate({ events: [] })
   // 然后重新加载 schedule
   ```

### 问题 3: API 返回 404

**原因**: 路由未注册

**解决**: 确认后端服务已重启，并且 `plan.py` 中的 router 已正确注册到主应用

## 相关文档

- `docs/RENDER_FLAG_AND_UPLOAD_LOGIC.md` - Flag 的作用和判断逻辑
- `kat_rec_web/backend/t2r/routes/plan.py` - API 实现代码

