# Render Flag 和上传逻辑说明

**日期**: 2025-01-XX  
**问题**: 17期为什么没有flag？现在判断第二阶段就绪、上传可以开始的逻辑是靠flag吗？

## 核心结论

**是的，判断第二阶段（render）就绪和上传可以开始的逻辑都依赖 `render_complete_flag`。**

## 判断逻辑

### 1. 第二阶段（Render）就绪判断

**位置**: `kat_rec_web/frontend/stores/scheduleStore.ts` - `calculateAssetStageReadiness()`

```typescript
const videoReady = !!(event.assets.video || event.assets.video_path)

// Check render_complete_flag from assetStates first, fallback to legacy assets.render_complete_flag
const renderFlagReady = isAssetReadyFromStates(event, 'render_complete_flag') ||
  !!(event.assets as any).render_complete_flag

// ✅ 关键：renderDone 需要同时有 video 和 flag
const renderDone = videoReady && renderFlagReady

return {
  render: {
    videoReady,
    renderFlagReady,
    ready: videoReady && renderFlagReady, // ✅ 必须两者都为 true
  }
}
```

**结论**: `render.ready = videoReady && renderFlagReady`，**必须同时有 video 文件和 render_complete_flag**。

### 2. 上传可以开始的判断

**位置**: `kat_rec_web/frontend/components/mcrb/OverviewGrid.tsx` - `renderEventCell()`

```typescript
const stages = calculateStageStatus(primaryEvent, runbookState)

// ✅ 关键：canUpload 依赖 stages.render.done
const canUpload = stages.render.done && 
                  !stages.publish.done && 
                  !actuallyUploaded
```

**`stages.render.done` 的计算**（`calculateStageStatus()`）:

```typescript
const hasVideo = !!(event.assets.video || (event.assets as any).video_path)
const hasRenderFlag = !!(event.assets as any).render_complete_flag
const renderDone = hasVideo && hasRenderFlag // ✅ 必须两者都为 true
```

**结论**: `canUpload` 依赖 `stages.render.done`，而 `stages.render.done` 需要同时有 video 和 flag。

## Flag 的生成条件

**位置**: `kat_rec_web/backend/t2r/routes/plan.py` - `_execute_stage_core()`

```python
render_complete_flag = episode_output_dir / f"{episode_id}_render_complete.flag"
if should_broadcast and validation_success and video_path.exists():
    try:
        video_size = video_path.stat().st_size
        with render_complete_flag.open("w", encoding="utf-8") as f:
            f.write(f"render_completed_at={datetime.utcnow().isoformat()}\n")
            f.write(f"video_path={video_path}\n")
            f.write(f"video_size={video_size}\n")
            f.write(f"video_checksum={video_checksum or 'N/A'}\n")
            f.write(f"duration={validation_result.get('duration', 0.0)}\n")
            f.write(f"validated_by=ffprobe\n")
        logger.info(f"✅ Created render complete flag (validated by ffprobe): {render_complete_flag}")
    except Exception as e:
        logger.warning(f"Failed to create render complete flag: {e}")
elif should_broadcast and not validation_success:
    logger.warning(f"⚠️  Skipping render_complete_flag creation for {episode_id}: ffprobe validation failed")
```

**生成条件**:
1. ✅ `should_broadcast` 为 true（需要广播事件）
2. ✅ `validation_success` 为 true（**ffprobe 验证成功**）
3. ✅ `video_path.exists()` 为 true（视频文件存在）

**关键**: 如果 ffprobe 验证失败，**不会创建 flag**。

## 17期为什么没有flag？

可能的原因：

### 1. ffprobe 验证失败

如果渲染完成后 ffprobe 验证失败，不会创建 flag。这会导致：
- ✅ 视频文件存在（`videoReady = true`）
- ❌ flag 不存在（`renderFlagReady = false`）
- ❌ `renderDone = false`
- ❌ `canUpload = false`

### 2. Flag 文件未同步到前端

即使后端创建了 flag 文件，如果前端没有从 `schedule_master.json` 或 WebSocket 事件中获取到 flag 路径，前端仍然认为 flag 不存在。

### 3. 渲染过程中断

如果渲染过程中断（例如进程被杀死），可能视频文件已生成但 flag 未创建。

## 解决方案

### 方案 1: 检查后端日志

查看后端日志，确认 17 期渲染时是否输出了：
- `✅ Created render complete flag` - flag 已创建
- `⚠️ Skipping render_complete_flag creation` - flag 未创建（ffprobe 验证失败）

### 方案 2: 手动创建 flag（临时方案）

如果视频文件已存在且可以正常播放，可以手动创建 flag：

```bash
# 在 episode 输出目录创建 flag 文件
cd channels/kat_lofi/output/20251117
cat > 20251117_render_complete.flag << EOF
render_completed_at=$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)
video_path=$(pwd)/20251117_final.mp4
video_size=$(stat -f%z 20251117_final.mp4)
video_checksum=N/A
duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 20251117_final.mp4)
validated_by=manual
EOF
```

### 方案 3: 使用 API 创建 flag（推荐）

使用新创建的 API endpoint，自动验证视频并创建 flag：

```bash
# 调用创建 flag API
curl -X POST http://localhost:8000/api/t2r/plan/create-render-flag \
  -H "Content-Type: application/json" \
  -d '{
    "episode_id": "20251117",
    "channel_id": "kat_lofi"
  }'
```

**API 功能**:
- ✅ 自动查找视频文件（支持 `{episode_id}_final.mp4`, `{episode_id}.mp4`, `{episode_id}_youtube.mp4`）
- ✅ 使用 ffprobe 验证视频文件完整性
- ✅ 验证成功后创建 `render_complete_flag` 文件
- ✅ 自动更新 `schedule_master.json` 中的 `assets.render_complete_flag` 字段
- ✅ 自动更新 Asset State Registry
- ✅ 如果 flag 已存在，返回成功（幂等操作）

**返回示例**:
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

### 方案 4: 同步资产状态

使用后端的资产同步服务，自动检测并创建缺失的 flag：

```bash
# 调用资产同步 API
curl -X POST http://localhost:8000/api/t2r/render-queue-sync/sync-all \
  -H "Content-Type: application/json" \
  -d '{"channel_id": "kat_lofi"}'
```

## 验证方法

### 1. 浏览器控制台检查

```javascript
// 检查 17 期的状态
const event = window.__KAT_STORE__.getState().eventsById['20251117']
console.log('Video:', event?.assets?.video || event?.assets?.video_path)
console.log('Flag:', event?.assets?.render_complete_flag)
console.log('Render Ready:', event ? calculateAssetStageReadiness(event).render.ready : false)
```

### 2. 后端文件系统检查

```bash
# 检查 flag 文件是否存在
ls -la channels/kat_lofi/output/20251117/*_render_complete.flag

# 检查视频文件是否存在
ls -la channels/kat_lofi/output/20251117/*_final.mp4
```

### 3. 后端 API 检查

```bash
# 获取 episode 详情
curl http://localhost:8000/api/t2r/episodes/20251117?channel_id=kat_lofi | jq '.assets.render_complete_flag'
```

## 总结

1. **第二阶段就绪判断**: 依赖 `videoReady && renderFlagReady`
2. **上传可以开始判断**: 依赖 `stages.render.done`，而 `stages.render.done = hasVideo && hasRenderFlag`
3. **Flag 生成**: 只有在 ffprobe 验证成功后才创建
4. **17期没有flag**: 可能是 ffprobe 验证失败，或 flag 未同步到前端

**建议**: 先检查后端日志，确认 flag 是否创建；如果未创建，检查 ffprobe 验证是否成功；如果验证成功但 flag 未创建，检查文件系统权限。

