# YouTube 上传功能说明

## 1. SRT 字幕生成

### 生成函数
**位置**: `kat_rec_web/backend/t2r/routes/automation.py`

**函数名**: `_filler_generate_srt` (第 2647 行)

```python
async def _filler_generate_srt(
    playlist_data: Dict,
    output_path: Path,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """异步生成 SRT 字幕文件"""
```

### 调用位置
在 `_filler_generate_title_desc_srt_tags` 函数中（第 2906-2933 行）：

```python
if "captions" in asset_types:
    if playlist_data:
        try:
            srt_path = episode_output_dir / f"{episode_id}_youtube.srt"
            if not await file_cache.async_file_exists_cached(srt_path) or overwrite:
                await _filler_generate_srt(
                    playlist_data,
                    srt_path,
                    api_key=api_key,
                    api_base=api_base,
                    model=model,
                )
                results["srt_path"] = srt_path
                logger.info(f"SRT 文件已生成: {srt_path}")
```

### SRT 内容结构
1. **开场欢迎词**（第 10-25 秒）
   - 使用 `_filler_generate_welcoming_messages` 生成
   - 格式：`Track {num} (Side {A|B}): {track_title}`

2. **曲目时间轴**
   - 从 `playlist_data` 的 `clean_timeline` 或 `timeline` 中提取
   - 过滤掉 "Needle On Vinyl Record"、"Vinyl Noise"、"Silence"
   - 每个曲目显示：`Track {track_num} (Side {A|B}): {track_title}`

3. **结束语**（最后一个曲目结束后 6 秒开始，持续 5 秒）
   - 使用 `_filler_generate_welcoming_messages` 生成的 `outro_msg`

### 相关辅助函数
- `_filler_parse_timestamp`: 解析时间戳
- `_filler_format_srt_time`: 格式化 SRT 时间格式
- `_filler_generate_welcoming_messages`: 生成欢迎和结束消息

---

## 2. 默认歌单（Playlist）

### 配置位置
**配置文件**: `src/core/config_access.py` (第 95 行)

```python
"youtube": {
    "playlist_id": app_config.youtube.playlist_id,
    # ... 其他配置
}
```

### 使用位置

#### 1. 上传配置加载
**文件**: `scripts/uploader/upload_to_youtube.py` (第 187 行)

```python
def load_config() -> Dict:
    # ...
    return {
        "playlist_id": youtube_config["playlist_id"],
        # ...
    }
```

#### 2. 创建 UploadConfig
**文件**: `scripts/uploader/upload_to_youtube.py` (第 367-382 行)

```python
upload_config = UploadConfig(
    # ...
    playlist_id=config.get("playlist_id"),
    # ...
)
```

#### 3. 添加到播放列表
**文件**: `scripts/uploader/upload_to_youtube.py` (第 404 行)

```python
# Attach to playlist
attach_to_playlist(youtube, video_id, upload_config.playlist_id, episode_id)
```

#### 4. 实现函数
**文件**: `scripts/uploader/upload_helpers.py` (第 312-351 行)

```python
def attach_to_playlist(
    youtube: Any,
    video_id: str,
    playlist_id: Optional[str],
    episode_id: Optional[str] = None,
) -> None:
    """
    将视频添加到播放列表
    
    Args:
        youtube: YouTube API 服务对象
        video_id: YouTube 视频 ID
        playlist_id: 播放列表 ID（可选）
        episode_id: 期数 ID（用于日志）
    """
    if not playlist_id:
        return  # 如果没有 playlist_id，直接返回
    
    try:
        add_video_to_playlist = _get_add_to_playlist()
        add_video_to_playlist(youtube, video_id, playlist_id, episode_id)
        # ... 日志记录
    except Exception as e:
        # 记录错误但不中断上传流程
        # ...
```

### 配置方式
在配置文件中设置 `youtube.playlist_id`，例如：

```yaml
# config/app_config.yaml 或类似配置文件
youtube:
  playlist_id: "PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # YouTube 播放列表 ID
```

---

## 3. 结尾画面（Ending Screen）

### 当前实现
**位置**: `kat_rec_web/backend/t2r/utils/ffmpeg_builder.py` (第 94-158 行)

**函数**: `build_render_command`

### 当前逻辑
目前视频渲染**只使用封面图片循环播放**，没有专门的结尾画面：

```python
def build_render_command(
    cover_path: Path,
    audio_path: Path,
    video_path: Path,
    codec: str = "libx264",
    audio_duration_sec: Optional[float] = None,
    threads: Optional[int] = None,
) -> List[str]:
    # ...
    # Input: cover image (loop) and audio
    if audio_duration_sec is not None:
        ffmpeg_cmd.extend(["-loop", "1", "-t", str(audio_duration_sec), "-i", str(cover_path)])
    else:
        ffmpeg_cmd.extend(["-loop", "1", "-i", str(cover_path)])
    ffmpeg_cmd.extend(["-i", str(audio_path)])
    
    # Video filter: scale to 4K, pad, fps=1
    sw, sh = 3840, 2160  # 4K resolution
    vf = f"scale={sw}:{sh}:force_original_aspect_ratio=decrease,pad={sw}:{sh}:(ow-iw)/2:(oh-ih)/2,fps=1:round=down"
    ffmpeg_cmd.extend(["-vf", vf])
    # ...
```

### 需要实现的功能
要添加结尾画面，需要：

1. **准备结尾画面图片**
   - 创建或指定一个结尾画面图片文件（例如：`ending_screen.png`）
   - 可以放在配置中或固定路径

2. **修改 FFmpeg 命令**
   - 在视频末尾（例如最后 5-10 秒）切换到结尾画面
   - 使用 FFmpeg 的 `concat` 或 `overlay` 滤镜
   - 或者使用两个输入源（封面 + 结尾画面）并在指定时间切换

3. **实现方案示例**
   ```python
   # 方案 1: 使用 concat demuxer
   # 1. 封面循环（音频时长 - 结尾时长）
   # 2. 结尾画面（固定时长，例如 5 秒）
   # 3. 使用 concat 合并
   
   # 方案 2: 使用 overlay 滤镜
   # 在视频末尾叠加结尾画面
   ```

### 建议的实现位置
- **修改**: `kat_rec_web/backend/t2r/utils/ffmpeg_builder.py` 的 `build_render_command` 函数
- **配置**: 在 `src/core/config_access.py` 中添加 `ending_screen_path` 配置项
- **调用**: `kat_rec_web/backend/t2r/routes/plan.py` 的 `_execute_stage_core` 函数（render 阶段）

---

## 总结

| 功能 | 状态 | 位置 | 说明 |
|------|------|------|------|
| **SRT 字幕生成** | ✅ 已实现 | `automation.py` 第 2647 行 | `_filler_generate_srt` 函数 |
| **默认歌单** | ✅ 已实现 | `upload_helpers.py` 第 312 行 | `attach_to_playlist` 函数，通过配置读取 `playlist_id` |
| **结尾画面** | ❌ 未实现 | `ffmpeg_builder.py` 第 94 行 | 目前只使用封面循环，需要添加结尾画面逻辑 |

---

## 下一步行动

### 1. 实现结尾画面功能
- [ ] 在配置中添加 `ending_screen_path` 配置项
- [ ] 修改 `build_render_command` 函数以支持结尾画面
- [ ] 测试结尾画面是否正确显示

### 2. 验证默认歌单功能
- [ ] 确认配置中的 `playlist_id` 是否正确设置
- [ ] 测试上传后视频是否自动添加到播放列表

### 3. 验证 SRT 字幕生成
- [ ] 确认 SRT 文件是否正确生成
- [ ] 验证字幕内容是否完整（开场、曲目列表、结束语）

