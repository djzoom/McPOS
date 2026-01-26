# 上传工作流分析与问题总结

## 问题回顾

**Episode 20251117 的问题**：
- 视频时长：3836 秒 (63.93 分钟)
- 音频时长：757 秒 (12.63 分钟)
- **视频比音频长 51 分钟（空白内容）**
- 导致 YouTube 处理失败："Processing abandoned"

## 完整工作流梳理

### 1. 渲染阶段 (Render Stage)

#### 1.1 音频时长获取
**位置**: `kat_rec_web/backend/t2r/routes/plan.py:1780-1805`

```python
# 获取音频时长（用于 explicit 模式）
audio_duration_sec = None
try:
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]
    probe_result = await run_command_simple(probe_cmd, timeout=10.0)
    if probe_result.returncode == 0 and probe_result.stdout.strip():
        audio_duration_sec = float(probe_result.stdout.strip())
except Exception as e:
    logger.warning(f"Could not get audio duration: {e}")
    # ⚠️ 问题：如果获取失败，audio_duration_sec 保持为 None
```

**潜在问题**：
- ✅ 如果获取音频时长失败，会回退到使用 `-shortest` 参数
- ⚠️ 某些编码器（如 `h264_videotoolbox`）对 `-shortest` 的处理可能不准确
- ⚠️ 超时时间只有 10 秒，对于大文件可能不够

#### 1.2 FFmpeg 命令构建
**位置**: `kat_rec_web/backend/t2r/utils/ffmpeg_builder.py:94-186`

```python
def build_render_command(
    cover_path: Path,
    audio_path: Path,
    video_path: Path,
    codec: str = "libx264",
    audio_duration_sec: Optional[float] = None,  # ⚠️ 可能为 None
    threads: Optional[int] = None,
) -> List[str]:
    # ...
    if audio_duration_sec is not None:
        # ✅ 显式时长模式：使用 -t 参数限制视频时长
        ffmpeg_cmd.extend(["-loop", "1", "-t", str(audio_duration_sec), "-i", str(cover_path)])
    else:
        # ⚠️ 回退模式：使用 -shortest（可能不准确）
        ffmpeg_cmd.extend(["-loop", "1", "-i", str(cover_path)])
    
    # ...
    # ⚠️ 问题：使用了 VFR (Variable Frame Rate) 模式
    ffmpeg_cmd.extend(["-vsync", "vfr", "-fps_mode", "passthrough"])
    
    # ...
    if audio_duration_sec is None:
        ffmpeg_cmd.append("-shortest")  # ⚠️ 回退到 -shortest
```

**潜在问题**：
1. **VFR 模式可能导致时长不准确**：
   - `-vsync vfr` + `-fps_mode passthrough` 可能导致视频时长计算错误
   - 特别是当使用 1fps 时，帧间隔可能不精确

2. **-shortest 参数在某些编码器下不准确**：
   - `h264_videotoolbox`: 可能有 +3 秒偏差
   - `libx264`: 可能有 +33 秒偏差
   - `mjpeg`: 时长准确但文件体积巨大

3. **显式时长模式（-t）更可靠**：
   - 如果 `audio_duration_sec` 获取成功，使用 `-t` 参数可以确保视频时长不超过音频
   - 但如果获取失败，回退到 `-shortest` 可能导致问题

#### 1.3 渲染执行
**位置**: `kat_rec_web/backend/t2r/routes/plan.py:1823-1966`

```python
# 执行 FFmpeg 命令
result = await async_run_ffmpeg_with_priority(ffmpeg_cmd, ...)

# 渲染完成后验证视频
validation_success, validation_result = await validate_and_update_manifest(
    channel_id,
    episode_id,
    video_path,
    expected_resolution=None,
    min_duration=0.0,  # ⚠️ 只检查最小时长，不检查与音频的匹配
    max_retries=3
)
```

**潜在问题**：
- ✅ 有视频验证步骤
- ⚠️ 但只检查了最小时长（`min_duration=0.0`），**没有检查视频和音频时长是否匹配**
- ⚠️ 如果验证失败，会更新 manifest 为 `render_failed`，但不会阻止后续上传

### 2. 视频验证阶段 (Validation)

#### 2.1 验证逻辑
**位置**: `kat_rec_web/backend/t2r/services/render_validator.py:20-249`

```python
def validate_video_with_ffprobe(
    video_path: Path,
    expected_resolution: Optional[Tuple[int, int]] = None,
    min_duration: float = 0.0  # ⚠️ 只检查最小时长
) -> Dict:
    # ...
    # 提取视频时长
    duration_str = format_info.get("duration")
    if duration_str:
        result["duration"] = float(duration_str)
        if result["duration"] <= min_duration:
            result["errors"].append(f"Duration {result['duration']}s is too short")
    
    # ⚠️ 问题：没有检查视频和音频时长是否匹配
    # ⚠️ 没有检查视频流和音频流的时长是否一致
```

**缺失的验证**：
1. ❌ **没有比较视频和音频时长**
2. ❌ **没有检查视频流和音频流的时长是否一致**
3. ❌ **没有检查视频是否包含空白内容**

### 3. 上传阶段 (Upload)

#### 3.1 上传前检查
**位置**: `kat_rec_web/backend/t2r/routes/upload.py:941-1106`

```python
async def upload_full(request: UploadFullRequest) -> Dict:
    # ...
    video_path = _resolve_video_path(request.video_file)
    if not video_path.exists():
        return {"status": "error", "errors": [f"Video file not found"]}
    
    # ⚠️ 问题：只检查文件是否存在，没有验证视频质量
    # ⚠️ 没有检查视频和音频时长是否匹配
    # ⚠️ 没有检查视频是否完整
```

**缺失的检查**：
1. ❌ **上传前没有再次验证视频和音频时长是否匹配**
2. ❌ **没有检查视频文件是否完整（可能正在写入）**
3. ❌ **没有检查视频和音频流的时长是否一致**

#### 3.2 上传执行
**位置**: `kat_rec_web/backend/t2r/routes/upload.py` (通过 `upload_to_youtube.py`)

- ✅ 使用 YouTube Data API v3 上传
- ✅ 支持断点续传
- ⚠️ 如果视频有问题，会直接上传到 YouTube
- ⚠️ YouTube 处理失败后，需要手动删除

## 问题总结

### 核心问题

1. **视频时长不匹配检测缺失**：
   - 渲染后验证只检查最小时长，不检查与音频的匹配
   - 上传前没有再次验证视频和音频时长是否匹配

2. **回退机制不安全**：
   - 如果获取音频时长失败，回退到 `-shortest` 参数
   - `-shortest` 在某些编码器下可能不准确

3. **VFR 模式可能导致时长不准确**：
   - `-vsync vfr` + `-fps_mode passthrough` 可能导致视频时长计算错误

4. **上传前缺少质量检查**：
   - 只检查文件是否存在，不检查视频质量
   - 不检查视频和音频时长是否匹配

### 可能出问题的环节

#### 🔴 高风险环节

1. **渲染阶段 - 音频时长获取失败**：
   - 如果 `ffprobe` 超时或失败，会回退到 `-shortest`
   - `-shortest` 在某些编码器下可能不准确

2. **渲染阶段 - VFR 模式**：
   - `-vsync vfr` + `-fps_mode passthrough` 可能导致时长不准确
   - 特别是当使用 1fps 时

3. **验证阶段 - 缺少时长匹配检查**：
   - 只检查最小时长，不检查与音频的匹配
   - 如果视频时长超过音频，不会被检测到

4. **上传阶段 - 缺少质量检查**：
   - 只检查文件是否存在，不检查视频质量
   - 如果视频有问题，会直接上传到 YouTube

#### 🟡 中风险环节

1. **渲染阶段 - 编码器选择**：
   - 不同编码器对 `-shortest` 的处理不同
   - `h264_videotoolbox` 可能有 +3 秒偏差
   - `libx264` 可能有 +33 秒偏差

2. **验证阶段 - 重试机制**：
   - 如果验证失败，会重试 3 次
   - 但如果视频确实有问题，重试不会解决问题

#### 🟢 低风险环节

1. **上传阶段 - 断点续传**：
   - 支持断点续传，但不会检测视频质量问题

## 改进建议

### 1. 增强视频验证

**在 `render_validator.py` 中添加时长匹配检查**：

```python
def validate_video_with_ffprobe(
    video_path: Path,
    audio_path: Optional[Path] = None,  # ✅ 新增：音频文件路径
    expected_resolution: Optional[Tuple[int, int]] = None,
    min_duration: float = 0.0,
    max_duration_diff: float = 5.0  # ✅ 新增：允许的最大时长差异（秒）
) -> Dict:
    # ...
    # ✅ 如果提供了音频路径，检查视频和音频时长是否匹配
    if audio_path and audio_path.exists():
        audio_duration = get_audio_duration(audio_path)
        video_duration = result.get("duration")
        if audio_duration and video_duration:
            duration_diff = abs(video_duration - audio_duration)
            if duration_diff > max_duration_diff:
                result["errors"].append(
                    f"Video duration ({video_duration:.2f}s) does not match audio duration "
                    f"({audio_duration:.2f}s). Difference: {duration_diff:.2f}s"
                )
                result["valid"] = False
```

### 2. 强制使用显式时长模式

**在 `plan.py` 中确保音频时长获取成功**：

```python
# ✅ 增加重试机制和更长的超时时间
audio_duration_sec = None
max_retries = 3
for attempt in range(max_retries):
    try:
        probe_cmd = [...]
        probe_result = await run_command_simple(probe_cmd, timeout=30.0)  # ✅ 增加超时时间
        if probe_result.returncode == 0 and probe_result.stdout.strip():
            audio_duration_sec = float(probe_result.stdout.strip())
            break
    except Exception as e:
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # 指数退避
        else:
            logger.error(f"Failed to get audio duration after {max_retries} attempts: {e}")
            # ⚠️ 如果仍然失败，应该抛出异常而不是回退到 -shortest
            raise ValueError(f"Cannot proceed without audio duration: {e}")
```

### 3. 上传前质量检查

**在 `upload.py` 中添加上传前验证**：

```python
async def upload_full(request: UploadFullRequest) -> Dict:
    # ...
    video_path = _resolve_video_path(request.video_file)
    if not video_path.exists():
        return {"status": "error", "errors": [f"Video file not found"]}
    
    # ✅ 新增：上传前验证视频质量
    from ..services.render_validator import validate_video_with_ffprobe
    from ..services.schedule_service import get_output_dir
    
    output_dir = get_output_dir(request.channel_id)
    episode_output_dir = output_dir / request.episode_id
    audio_path = episode_output_dir / f"{request.episode_id}_full_mix.mp3"
    
    validation_result = validate_video_with_ffprobe(
        video_path=video_path,
        audio_path=audio_path if audio_path.exists() else None,
        min_duration=60.0,  # 至少 1 分钟
        max_duration_diff=5.0  # 允许 5 秒差异
    )
    
    if not validation_result["valid"]:
        return {
            "status": "error",
            "errors": validation_result["errors"],
            "timestamp": datetime.utcnow().isoformat(),
        }
```

### 4. 改进 FFmpeg 命令

**考虑使用固定帧率而不是 VFR**：

```python
# 当前：VFR 模式（可能导致时长不准确）
ffmpeg_cmd.extend(["-vsync", "vfr", "-fps_mode", "passthrough"])

# ✅ 建议：使用固定帧率（更准确）
ffmpeg_cmd.extend(["-r", "1", "-vsync", "cfr"])  # 1fps 固定帧率
# 或者
ffmpeg_cmd.extend(["-r", "30", "-vsync", "cfr"])  # 30fps 固定帧率（更平滑）
```

## 实施优先级

### 🔴 高优先级（立即实施）

1. **增强视频验证**：添加视频和音频时长匹配检查
2. **上传前质量检查**：在上传前验证视频质量

### 🟡 中优先级（近期实施）

1. **强制使用显式时长模式**：确保音频时长获取成功，不要回退到 `-shortest`
2. **改进 FFmpeg 命令**：考虑使用固定帧率而不是 VFR

### 🟢 低优先级（长期优化）

1. **编码器选择优化**：根据编码器的特性调整参数
2. **监控和告警**：添加监控，当检测到时长不匹配时发送告警

## 相关文档

- `scripts/local_picker/DURATION_FIX_GUIDE.md`: 视频时长修复指南
- `tools/DURATION_FIX_COMPARISON.md`: 时长修复方案对比
- `kat_rec_web/backend/t2r/utils/ffmpeg_builder.py`: FFmpeg 命令构建工具
- `kat_rec_web/backend/t2r/services/render_validator.py`: 视频验证服务

