# YouTube End Screen 自动设置实现方案

## 当前状态

**重要**: YouTube Data API v3 **目前不直接支持**通过 API 自动设置 End Screen（结尾画面）。

根据 [YouTube Data API v3 文档](https://developers.google.com/youtube/v3)，End Screen 管理功能尚未在 API 中提供。

## 替代方案

### 方案 1: 在视频编辑阶段嵌入结尾画面（推荐）

**优点**:
- 完全自动化
- 不依赖 YouTube API
- 结尾画面成为视频内容的一部分，无法被移除

**实现方式**:
在视频渲染阶段（`kat_rec_web/backend/t2r/utils/ffmpeg_builder.py`），在视频末尾添加结尾画面：

```python
def build_render_command(
    cover_path: Path,
    audio_path: Path,
    video_path: Path,
    ending_screen_path: Optional[Path] = None,  # ✅ 新增参数
    codec: str = "libx264",
    audio_duration_sec: Optional[float] = None,
    threads: Optional[int] = None,
) -> List[str]:
    """
    构建视频渲染 FFmpeg 命令，支持结尾画面
    
    Args:
        ending_screen_path: 结尾画面图片路径（可选）
    """
    # ... 现有代码 ...
    
    # ✅ 如果有结尾画面，在视频末尾添加
    if ending_screen_path and ending_screen_path.exists():
        # 使用 concat demuxer 或 overlay 滤镜
        # 方案 A: 使用 concat（推荐）
        # 1. 生成封面循环视频（音频时长 - 结尾时长）
        # 2. 生成结尾画面视频（固定时长，例如 5 秒）
        # 3. 使用 concat 合并
        
        # 方案 B: 使用 overlay 滤镜
        # 在视频末尾叠加结尾画面
        pass
```

### 方案 2: 使用 YouTube Studio 模板（半自动化）

**步骤**:
1. 在 YouTube Studio 中创建结尾画面模板
2. 上传视频后，手动或使用浏览器自动化工具应用模板

**浏览器自动化示例**（使用 Selenium 或 Playwright）:
```python
from selenium import webdriver
from selenium.webdriver.common.by import By

def apply_end_screen_template(video_id: str, template_name: str):
    """使用浏览器自动化应用结尾画面模板"""
    driver = webdriver.Chrome()
    try:
        # 登录 YouTube Studio
        driver.get(f"https://studio.youtube.com/video/{video_id}/edit")
        # ... 自动化操作 ...
    finally:
        driver.quit()
```

**缺点**:
- 需要浏览器自动化
- 可能违反 YouTube 服务条款
- 需要处理登录和认证

### 方案 3: 等待 YouTube API 更新

定期检查 [YouTube Data API v3 更新日志](https://developers.google.com/youtube/v3/revision_history)，等待官方支持。

## 推荐实现：方案 1（视频编辑阶段嵌入）

### 实现步骤

1. **准备结尾画面图片**
   - 创建或指定结尾画面图片（例如：`assets/ending_screen.png`）
   - 建议尺寸：1920x1080 或 3840x2160（4K）

2. **修改 FFmpeg 渲染命令**
   - 在 `build_render_command` 函数中添加结尾画面支持
   - 使用 FFmpeg 的 `concat` demuxer 合并封面循环和结尾画面

3. **配置结尾画面路径**
   - 在 `config/config.yaml` 中添加 `ending_screen_path` 配置项

### 代码实现示例

```python
# kat_rec_web/backend/t2r/utils/ffmpeg_builder.py

def build_render_command_with_ending(
    cover_path: Path,
    audio_path: Path,
    video_path: Path,
    ending_screen_path: Optional[Path] = None,
    ending_duration: float = 5.0,  # 结尾画面时长（秒）
    codec: str = "libx264",
    audio_duration_sec: Optional[float] = None,
    threads: Optional[int] = None,
) -> List[str]:
    """
    构建视频渲染 FFmpeg 命令（支持结尾画面）
    
    如果提供了 ending_screen_path，会在视频末尾添加结尾画面。
    """
    if ending_screen_path and ending_screen_path.exists() and audio_duration_sec:
        # 方案：使用 concat demuxer
        # 1. 生成主视频（封面循环，时长 = 音频时长 - 结尾时长）
        # 2. 生成结尾视频（结尾画面，固定时长）
        # 3. 使用 concat 合并
        
        main_duration = audio_duration_sec - ending_duration
        
        # 主视频命令
        main_video_cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-t", str(main_duration), "-i", str(cover_path),
            "-i", str(audio_path),
            "-vf", "scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2,fps=1:round=down",
            "-c:v", codec, "-preset", "slow", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-f", "mp4", "main_video.mp4"
        ]
        
        # 结尾视频命令
        ending_video_cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-t", str(ending_duration), "-i", str(ending_screen_path),
            "-vf", "scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2,fps=1:round=down",
            "-c:v", codec, "-preset", "slow", "-crf", "23",
            "-an",  # 无音频
            "-f", "mp4", "ending_video.mp4"
        ]
        
        # Concat 文件
        concat_file = "concat_list.txt"
        with open(concat_file, "w") as f:
            f.write("file 'main_video.mp4'\n")
            f.write("file 'ending_video.mp4'\n")
        
        # 最终合并命令
        final_cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c", "copy",
            "-movflags", "+faststart",
            str(video_path)
        ]
        
        # 返回多步骤命令（需要按顺序执行）
        return {
            "steps": [
                {"cmd": main_video_cmd, "name": "main_video"},
                {"cmd": ending_video_cmd, "name": "ending_video"},
                {"cmd": final_cmd, "name": "concat"}
            ]
        }
    else:
        # 无结尾画面，使用原有逻辑
        return build_render_command(cover_path, audio_path, video_path, codec, audio_duration_sec, threads)
```

### 配置示例

```yaml
# config/config.yaml
youtube:
  # ... 其他配置 ...
  ending_screen:
    enabled: true
    image_path: "assets/ending_screen.png"  # 结尾画面图片路径
    duration: 5.0  # 结尾画面时长（秒）
```

## 总结

| 方案 | 自动化程度 | 实现难度 | 推荐度 |
|------|-----------|---------|--------|
| **方案 1: 视频编辑嵌入** | ✅ 完全自动化 | 中等 | ⭐⭐⭐⭐⭐ |
| **方案 2: 浏览器自动化** | ⚠️ 半自动化 | 高 | ⭐⭐ |
| **方案 3: 等待 API** | ❌ 不可用 | 低 | ⭐ |

**建议**: 使用方案 1，在视频渲染阶段直接嵌入结尾画面。这是最可靠和完全自动化的方案。

## 参考资料

- [YouTube Data API v3 文档](https://developers.google.com/youtube/v3)
- [FFmpeg Concat Demuxer 文档](https://ffmpeg.org/ffmpeg-formats.html#concat)
- [YouTube Studio 结尾画面指南](https://support.google.com/youtube/answer/6140493)

