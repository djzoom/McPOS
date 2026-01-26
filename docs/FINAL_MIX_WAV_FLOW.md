# final_mix.wav 生成流程文档

## 概述

`final_mix.wav` 是 Remix 阶段生成的预混音音频文件，用于优化 Render 阶段的性能。本文档说明其生成函数、触发方式，以及如何整合到事件流和状态流中。

## 1. 生成函数

### 位置
`kat_rec_web/backend/t2r/routes/plan.py` 的 `_execute_stage_core()` 函数

### 函数逻辑
```python
# Remix 阶段完成后自动生成
async def _execute_stage_core(stage: str, ...):
    if stage == "remix":
        # ... remix 执行逻辑 ...
        
        # ✅ Unified Pre-Mix Architecture: Generate final_mix.wav after remix completes
        logger.info(f"[remix] Generating final_mix.wav for {episode_id}")
        
        # 1. 解析 playlist.csv Timeline 部分
        events = parse_playlist_timeline(playlist_path)
        
        # 2. 构建 FFmpeg filtergraph
        # - 加载每个音频轨道，应用 delay（基于 timestamp）
        # - 插入 Needle_Start.mp3 和 Vinyl_Noise.mp3（音量 -18dB）
        # - 处理 Silence 事件（生成 3s 静音）
        # - 构建 amix filtergraph（normalize=0, duration=longest）
        # - 应用 loudnorm (I=-14, TP=-1.5, LRA=11)
        
        # 3. 导出为 16-bit PCM WAV 格式
        cmd_wav = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            # ... 输入文件 ...
            "-filter_complex", ";".join(filter_complex),
            "-map", "[mix]",
            "-c:a", "pcm_s16le",  # 16-bit PCM WAV
            str(final_mix_path),
        ]
        
        # 4. 创建检查点
        flag_path = episode_output_dir / f"{episode_id}.final_mix.complete.flag"
        flag_data = {
            "episode_id": episode_id,
            "channel_id": channel_id,
            "stage": "final_mix",
            "completed_at": datetime.utcnow().isoformat(),
            "final_mix_path": str(final_mix_path),
        }
        atomic_write_json(flag_path, flag_data)
```

### 生成参数
- **格式**: 16-bit PCM WAV (`pcm_s16le`)
- **采样率**: 44.1kHz
- **声道**: 立体声
- **响度**: I=-14 LUFS, TP=-1.5 dBTP, LRA=11
- **文件位置**: `{episode_dir}/{episode_id}_final_mix.wav`
- **检查点**: `{episode_dir}/{episode_id}.final_mix.complete.flag`

## 2. 触发方式

### 自动触发
`final_mix.wav` 在 **Remix 阶段完成后自动生成**，无需手动触发。

### 触发流程
```
Remix 阶段执行
  ↓
remix_mixtape.py 完成
  ↓
_execute_stage_core("remix") 完成
  ↓
自动生成 final_mix.wav
  ↓
创建 final_mix.complete.flag 检查点
  ↓
Remix 阶段标记为完成
```

### 触发位置
- **主要入口**: `kat_rec_web/backend/t2r/routes/plan.py` → `_execute_stage_core("remix")`
- **通过 StageflowExecutor**: `kat_rec_web/backend/t2r/services/stageflow.py` → `execute_stage("remix")`
- **自动化流程**: `kat_rec_web/backend/t2r/services/channel_automation.py` → `_run_remix_stage()`

## 3. 事件流整合

### 当前状态
目前 `final_mix.wav` 生成**没有**发送事件流事件，只在日志中记录。

### 需要添加的事件
1. **final_mix_started**: final_mix.wav 开始生成
2. **final_mix_completed**: final_mix.wav 生成完成
3. **final_mix_failed**: final_mix.wav 生成失败

### 事件发送位置
在 `kat_rec_web/backend/t2r/routes/plan.py` 的 `_execute_stage_core()` 函数中：

```python
# 生成开始
if emit_events:
    from src.core.event_bus import get_event_bus
    event_bus = get_event_bus()
    event_bus.emit_final_mix_started(episode_id)

# 生成完成
if final_mix_path.exists():
    if emit_events:
        event_bus.emit_final_mix_completed(episode_id, str(final_mix_path))

# 生成失败
except Exception as e:
    if emit_events:
        event_bus.emit_final_mix_failed(episode_id, str(e))
```

## 4. 状态流整合

### 当前状态
`final_mix.wav` 的状态**没有**在状态流中跟踪，只在文件系统中通过检查点文件存在。

### 需要添加的状态
1. **final_mix 阶段检查点**: 在 `StageflowExecutor` 中添加 `final_mix` 阶段
2. **状态视图**: 在 `get_episode_state_view()` 中添加 `final_mix` 状态
3. **前端状态**: 在前端状态流中显示 `final_mix` 状态

### 状态检查点
在 `kat_rec_web/backend/t2r/services/stageflow.py` 中：

```python
# 添加 final_mix 检查点
self.checkpoint_files = {
    "init": ...,
    "remix": ...,
    "final_mix": self.episode_dir / f"{episode_id}.final_mix.complete.flag",
    "render": ...,
    "upload": ...,
    "verify": ...,
}

# 在 get_episode_state_view() 中添加
state_view["stages"]["final_mix"] = {
    "completed": executor.get_checkpoint("final_mix"),
    "checkpoint_path": str(executor.checkpoint_files.get("final_mix")),
}
```

## 5. 完整流程

### 阶段顺序
```
init → remix → final_mix → render → upload → verify
```

### 状态流转
```
[remix] 执行中
  ↓
[remix] 完成 → 触发 final_mix 生成
  ↓
[final_mix] 开始生成
  ↓
[final_mix] 完成 → 创建检查点
  ↓
[render] 检查 final_mix.wav 存在
  ↓
[render] 使用 final_mix.wav 渲染视频
```

### 检查点依赖
- **render 阶段**: 需要 `final_mix.complete.flag` 存在（或 `final_mix.wav` 文件存在）
- **前置条件检查**: `async_validate_render_prerequisites()` 检查 `final_mix.wav` 存在

## 6. 容错处理

### 生成失败
- **非致命错误**: `final_mix.wav` 生成失败不会导致 remix 阶段失败
- **回退机制**: 如果 `final_mix.wav` 不存在，render 阶段会失败（因为现在是必需的前置条件）

### 恢复机制
- **检查点恢复**: 如果 `final_mix.complete.flag` 存在但文件被删除，可以重新生成
- **自动检测**: AssetWatchdog 可以检测并重新生成缺失的 `final_mix.wav`

## 7. 性能优化

### 优势
1. **预混音**: 避免 render 阶段重复混音
2. **响度标准化**: 提前应用 loudnorm，render 阶段无需再次处理
3. **格式统一**: WAV 格式便于后续处理

### 使用场景
- **必需**: Render 阶段现在**必须**有 `final_mix.wav` 才能渲染
- **优化**: 前三秒使用静态图片，提高 ffmpeg 效率

