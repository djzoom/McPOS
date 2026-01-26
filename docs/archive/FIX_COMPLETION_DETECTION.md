# 文件生成完成判断问题修复方案

**日期**: 2025-01-XX  
**优先级**: 🔴 P0（影响工作流正确性）

---

## 🎯 问题总结

1. **MP3 合成完成判断过早**: 系统在 `full_mix.mp3` 生成时就认为完成，但应该等待 `full_mix_timeline.csv` 生成
2. **视频渲染完成判断不准确**: 只检查文件是否存在，不检查文件是否真正完成写入
3. **GridProgressIndicator 失灵**: 无法侦知重要事件（如 timeline_csv 生成、视频文件真正完成）

---

## 🔧 修复方案

### 修复 1: 强化 MP3 合成完成判断

**文件**: `kat_rec_web/frontend/stores/scheduleStore.ts`

**变更位置**: 第 823-847 行

**当前代码**:
```typescript
const isAudioMixed = (
  audioPath: string | null | undefined,
  timelineCsv?: string | null | undefined
): boolean => {
  if (!audioPath) return false
  if (
    timelineCsv &&
    (timelineCsv.includes('_full_mix_timeline.csv') ||
      timelineCsv.endsWith('_full_mix_timeline.csv'))
  ) {
    return true
  }
  return (
    audioPath.includes('_full_mix.mp3') || audioPath.endsWith('_full_mix.mp3')
  )
}

const hasAudio = isAudioMixed(
  event.assets.audio,
  event.assets.timeline_csv
) || !!event.assets.audio  // ⚠️ 问题：fallback 允许仅凭 audio 路径就认为完成
```

**修复后代码**:
```typescript
const isAudioMixed = (
  audioPath: string | null | undefined,
  timelineCsv?: string | null | undefined
): boolean => {
  if (!audioPath) return false
  
  // ✅ 严格要求：必须有 timeline_csv 才认为完成
  // timeline_csv 是 remix 阶段的最后一个文件，只有它生成才意味着真正完成
  if (
    timelineCsv &&
    (timelineCsv.includes('_full_mix_timeline.csv') ||
      timelineCsv.endsWith('_full_mix_timeline.csv'))
  ) {
    // 同时验证 audio 路径包含 full_mix.mp3
    return (
      audioPath.includes('_full_mix.mp3') || 
      audioPath.endsWith('_full_mix.mp3')
    )
  }
  
  // ❌ 移除 fallback：不允许仅凭 audio 路径就认为完成
  // 这确保了系统必须等待 timeline_csv 生成才认为 remix 完成
  return false
}

// ✅ 移除 fallback 逻辑，严格要求 timeline_csv 存在
const hasAudio = isAudioMixed(
  event.assets.audio,
  event.assets.timeline_csv
)  // 不再有 || !!event.assets.audio
```

---

### 修复 2: 强化视频渲染完成判断（使用后续旗标任务）

**文件**: `kat_rec_web/backend/t2r/routes/plan.py`

**变更位置**: 第 1812-1826 行（渲染完成广播事件）

**当前代码**:
```python
# Broadcast progress: 100% - render completed (include video path in event)
# Only broadcast if not already complete (idempotency)
if should_broadcast:
    await emit_stage_event({
        "episode_id": episode_id,
        "stage": "render",
        "progress": 100,
        "message": f"Video rendering completed successfully: {video_path.name}",
        "video_path": str(video_path),
        "assets": {
            "video": str(video_path),
            "video_path": str(video_path)
        },
        "timestamp": datetime.utcnow().isoformat()
    }, level="info", immediate=True)
```

**修复后代码**:
```python
# ✅ 生成后续旗标文件，确保渲染真正完成
render_complete_flag = episode_output_dir / f"{episode_id}_render_complete.flag"
try:
    with render_complete_flag.open("w", encoding="utf-8") as f:
        f.write(f"render_completed_at={datetime.utcnow().isoformat()}\n")
        f.write(f"video_path={video_path}\n")
        f.write(f"video_size={video_path.stat().st_size}\n")
        f.write(f"video_checksum={video_checksum or 'N/A'}\n")
    logger.info(f"✅ Created render complete flag: {render_complete_flag}")
except Exception as e:
    logger.warning(f"Failed to create render complete flag: {e}")

# Broadcast progress: 100% - render completed (include video path and flag in event)
# Only broadcast if not already complete (idempotency)
if should_broadcast:
    await emit_stage_event({
        "episode_id": episode_id,
        "stage": "render",
        "progress": 100,
        "message": f"Video rendering completed successfully: {video_path.name}",
        "video_path": str(video_path),
        "render_complete_flag": str(render_complete_flag),  # ✅ 新增
        "assets": {
            "video": str(video_path),
            "video_path": str(video_path),
            "render_complete_flag": str(render_complete_flag),  # ✅ 新增
        },
        "timestamp": datetime.utcnow().isoformat()
    }, level="info", immediate=True)
```

**前端修改** (`scheduleStore.ts` 第 873-876 行):

**当前代码**:
```typescript
// renderDone: Only true if video file actually exists
const renderDone = !!event.assets.video || !!event.assets.video_path
```

**修复后代码**:
```typescript
// ✅ 检查视频文件和后续旗标文件都存在
// render_complete_flag 确保渲染真正完成（文件写入完成、验证通过）
const renderDone = !!(
  (event.assets.video || event.assets.video_path) &&
  event.assets.render_complete_flag  // ✅ 必须存在旗标文件
)
```

**WebSocket 事件处理** (`useWebSocket.ts`):

**需要更新**: 确保在收到 render 完成事件时，同时更新 `render_complete_flag`

```typescript
// 在 useWebSocket.ts 中，处理 render 完成事件
if (stage.includes('render') && data.progress === 100) {
  if (data.video_path || data.assets?.video) {
    const videoPath = data.video_path || data.assets?.video
    updates.assets = {
      ...(updates.assets || currentEvent?.assets || {}),
      video: videoPath,
      video_path: videoPath,
      render_complete_flag: data.assets?.render_complete_flag || data.render_complete_flag,  // ✅ 新增
    }
    logger.debug('[useWebSocket] Updating assets.video and render_complete_flag for episode', episodeId)
  }
}
```

---

### 修复 3: 确保后端在 timeline_csv 生成后才广播完成

**文件**: `kat_rec_web/backend/t2r/routes/plan.py`

**变更位置**: 第 1409-1420 行（remix 完成广播）

**当前逻辑**: 
- Timeline CSV 生成在 MP3 生成之后（第 1262-1353 行）
- 但广播事件可能在 timeline_csv 生成之前就发送

**修复**: 确保在 timeline_csv 生成**之后**才广播 remix 完成事件

**当前代码** (第 1409 行):
```python
# Broadcast progress: 100% - remix completed (include audio path, timeline CSV, and playlist path in event)
```

**修复后代码**:
```python
# ✅ 确保 timeline_csv 已生成后才广播完成事件
# Timeline CSV 是 remix 阶段的最后一个文件，只有它生成才意味着真正完成
if not timeline_csv_path.exists():
    logger.warning(f"Timeline CSV not found for {episode_id}, remix may not be fully complete")
    # 可以选择：等待 timeline_csv 生成，或标记为部分完成
    # 这里我们选择等待，确保完整性
    # 如果 timeline_csv 生成失败，会在上面的异常处理中记录

# Broadcast progress: 100% - remix completed (include audio path, timeline CSV, and playlist path in event)
# ✅ 只有在 timeline_csv 存在时才广播完成
if timeline_csv_path.exists():
    await emit_stage_event({
        "episode_id": episode_id,
        "stage": "remix",
        "progress": 100,
        "message": "Audio remix completed successfully",
        "audio_path": str(full_mix_path),
        "timeline_csv_path": str(timeline_csv_path),  # ✅ 确保包含 timeline_csv 路径
        "assets": {
            "audio": str(full_mix_path),
            "timeline_csv": str(timeline_csv_path),  # ✅ 确保包含 timeline_csv
        },
        "timestamp": datetime.utcnow().isoformat()
    }, level="info", immediate=True)
else:
    logger.error(f"Cannot broadcast remix completion: timeline_csv not found for {episode_id}")
```

---

### 修复 4: 改进 WebSocket 事件处理

**文件**: `kat_rec_web/frontend/hooks/useWebSocket.ts`

**变更位置**: 第 530-544 行（remix 完成处理）

**当前代码**:
```typescript
// If remix completed, update assets.audio
if (stage.includes('remix') && data.progress === 100) {
  if (data.audio_path || data.assets?.audio) {
    const audioPath = data.audio_path || data.assets?.audio
    updates.assets = {
      ...(updates.assets || currentEvent?.assets || {}),
      audio: audioPath
    }
    updates.audio_exists = true
    logger.debug('[useWebSocket] Updating assets.audio for episode', episodeId, 'with path:', audioPath)
  }
  
  // Auto-generate text assets after remix completion
  ensureTextAssets(episodeId)
}
```

**修复后代码**:
```typescript
// ✅ 如果 remix 完成，更新 assets.audio 和 assets.timeline_csv
if (stage.includes('remix') && data.progress === 100) {
  if (data.audio_path || data.assets?.audio) {
    const audioPath = data.audio_path || data.assets?.audio
    const timelineCsvPath = data.timeline_csv_path || data.assets?.timeline_csv  // ✅ 新增
    
    updates.assets = {
      ...(updates.assets || currentEvent?.assets || {}),
      audio: audioPath,
      timeline_csv: timelineCsvPath,  // ✅ 新增：确保 timeline_csv 被更新
    }
    updates.audio_exists = true
    logger.debug('[useWebSocket] Updating assets.audio and timeline_csv for episode', episodeId, {
      audio: audioPath,
      timeline_csv: timelineCsvPath,
    })
    
    // ✅ 只有在 timeline_csv 存在时才认为 remix 真正完成
    if (timelineCsvPath) {
      // Auto-generate text assets after remix completion
      ensureTextAssets(episodeId)
    } else {
      logger.warn('[useWebSocket] Remix completed but timeline_csv not found, skipping text asset generation')
    }
  }
}
```

---

## 🔍 其他潜在问题检查

### 问题 4: 文件写入过程中的检测

**检查点**:
- ✅ `plan.py` 中已有文件存在检查（`video_path.exists()`）
- ⚠️ 但没有检查文件大小是否稳定

**建议**: 使用后续旗标任务（已在修复 2 中实现）

### 问题 5: 文件系统延迟

**检查点**:
- ✅ 后端有重试机制（`render_validator.py` 中的 `max_retries`）
- ⚠️ 前端没有重试机制

**建议**: 前端依赖 WebSocket 事件，不直接检查文件系统

### 问题 6: 并发问题

**检查点**:
- ✅ 后端使用 manifest 系统来协调（`plan.py` 第 1379-1407 行）
- ✅ 有 idempotency 检查

**建议**: 保持现有机制，确保 manifest 更新是原子的

---

## 📋 实施步骤

### 步骤 1: 修复 MP3 合成完成判断

1. 修改 `scheduleStore.ts` 的 `isAudioMixed` 函数
2. 移除 fallback 逻辑
3. 测试验证

### 步骤 2: 修复视频渲染完成判断

1. 在 `plan.py` 中添加 `render_complete_flag` 生成
2. 修改前端 `scheduleStore.ts` 的 `renderDone` 判断
3. 更新 `useWebSocket.ts` 的事件处理
4. 测试验证

### 步骤 3: 确保后端正确广播事件

1. 修改 `plan.py` 确保在 timeline_csv 生成后才广播
2. 更新 WebSocket 事件包含完整信息
3. 测试验证

---

## ✅ 验证标准

### MP3 合成完成
- ✅ `full_mix.mp3` 文件存在
- ✅ `full_mix_timeline.csv` 文件存在
- ✅ 前端 `isAudioMixed` 返回 `true`
- ✅ 前端 `hasAudio` 为 `true`

### 视频渲染完成
- ✅ 视频文件存在
- ✅ `render_complete_flag` 文件存在
- ✅ 视频文件通过 `ffprobe` 验证
- ✅ 前端 `renderDone` 为 `true`

### GridProgressIndicator
- ✅ 能够实时反映进度
- ✅ 能够侦知 timeline_csv 生成事件
- ✅ 能够侦知 render_complete_flag 生成事件
- ✅ 状态更新及时准确

---

## 🚨 注意事项

1. **向后兼容**: 对于已存在的视频文件，可能需要手动创建 `render_complete_flag`
2. **错误处理**: 如果 timeline_csv 生成失败，需要明确标记为失败，而不是静默忽略
3. **性能**: 文件大小稳定性检查可能增加延迟，使用旗标文件更可靠

---

**下一步**: 实施修复并测试验证

