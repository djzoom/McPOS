# 旧世界视频渲染方式详解

本文档描述旧世界（legacy）的视频渲染实现方式，包括输入文件、FFmpeg 参数和渲染流程。

## 一、渲染架构演进

### 阶段 1：事件-Based Filtergraph（已废弃）

**位置**：`kat_rec_web/backend/t2r/utils/direct_video_render.py`（历史版本）

**工作原理**：
- 从 `playlist.csv` 解析 Timeline 事件
- 为每个事件（曲目和 SFX）创建 FFmpeg 输入
- 使用 `adelay` 和 `amix` 在视频渲染时实时混音
- 输出视频和音频同时生成

**问题**：
- 性能差：需要实时混音，耗时很长
- 磁盘 I/O 高：需要读取所有曲目文件
- 复杂度高：视频和音频混音逻辑耦合

### 阶段 2：Unified Pre-Mix Architecture（当前）

**位置**：`kat_rec_web/backend/t2r/utils/direct_video_render.py`（当前版本）

**工作原理**：
- **优先使用预混音音频**：`final_mix.mp3` (256kbps) 或 `full_mix.mp3` (legacy)
- **直接渲染视频**：封面图片 + 预混音音频 → 视频文件
- **跳过实时混音**：不再从 playlist.csv 构建 filtergraph

**优势**：
- 性能大幅提升：只需读取封面和预混音音频
- 磁盘 I/O 降低：减少文件读取次数
- 逻辑解耦：混音和渲染分离

## 二、输入文件

### 必需文件

1. **封面图片**
   - 文件：`{episode_id}_cover.png`
   - 分辨率：4K (7680×4320) 或更高
   - 格式：PNG（支持透明通道）

2. **预混音音频**（优先级顺序）
   - `{episode_id}_final_mix.mp3` (256kbps) - **优先使用**
   - `{episode_id}_full_mix.mp3` (legacy) - 回退选项
   - `{episode_id}_playlist_full_mix.mp3` - 备用命名

### 文件检查逻辑

```python
# 优先级：final_mix.mp3 > full_mix.mp3 > playlist_full_mix.mp3
if final_mix_mp3_path.exists():
    audio_path = final_mix_mp3_path
elif legacy_mp3_path.exists():
    audio_path = legacy_mp3_path
else:
    # 尝试其他可能的命名
    alt_mp3_path = episode_dir / f"{episode_id}_playlist_full_mix.mp3"
    if alt_mp3_path.exists():
        audio_path = alt_mp3_path
    else:
        raise FileNotFoundError("Pre-mixed MP3 not found")
```

**注意**：如果找不到预混音 MP3，渲染会失败，不再支持回退到事件-based filtergraph。

## 三、FFmpeg 命令结构

### 基本命令结构

```bash
ffmpeg -y -hide_banner -loglevel error \
  -loop 1 -i "{cover_path}" \
  -i "{audio_path}" \
  -vf "{video_filter}" \
  {common_args} \
  {video_encoding_args} \
  {audio_encoding_args} \
  "{output_video_path}"
```

### 输入参数

- `-loop 1`: 循环播放封面图片（静态图片需要循环以匹配音频长度）
- `-i "{cover_path}"`: 输入 0 - 封面图片
- `-i "{audio_path}"`: 输入 1 - 预混音音频（MP3）

### 视频滤镜（`-vf`）

```bash
scale=3840:2160:force_original_aspect_ratio=decrease,
pad=3840:2160:(ow-iw)/2:(oh-ih)/2,
fps=1:round=down
```

**说明**：
- `scale=3840:2160:force_original_aspect_ratio=decrease`: 缩放到 4K，保持宽高比（不拉伸）
- `pad=3840:2160:(ow-iw)/2:(oh-ih)/2`: 填充到 3840×2160，居中（黑边）
- `fps=1:round=down`: 帧率 1 FPS（静态图片），向下舍入确保时长精确

### 通用参数（`build_common_args()`）

```python
[
    "-pix_fmt", "yuv420p",      # 像素格式：标准格式，文件更小，兼容性更好
    "-vsync", "vfr",            # 可变帧率
    "-fps_mode", "passthrough", # 传递原始帧率
    "-shortest",                # 时长控制：确保视频长度匹配音频
    "-movflags", "+faststart",  # 快速启动：将 moov atom 移到文件开头
]
```

### 视频编码参数（`build_video_encoding_args()`）

```python
[
    "-c:v", "libx264",                    # 视频编码器：H.264
    "-preset", "veryfast",                 # 编码速度预设：快速编码
    "-crf", "35",                          # 质量因子：CRF 35（质量与文件大小平衡）
    "-tune", "stillimage",                 # 调优：针对静态图片优化（码率降低 20-30 倍）
    "-g", "3600",                          # 关键帧间隔：每 3600 秒（1小时）一个 I 帧
    "-x264-params", "keyint=3600:min-keyint=3600",  # x264 参数：与 -g 3600 配合
]
```

**关键参数说明**：
- **`-tune stillimage`**：最关键，针对静态图片优化，码率降低 20-30 倍
- **`-g 3600`**：fps=1 时，每 3600 秒（1小时）一个 I 帧，大幅减少文件大小
- **`-crf 35`**：质量因子，35 是静态图片的合理值（动态视频通常用 23）

### 音频编码参数（`build_audio_encoding_args()`）

```python
[
    "-c:a", "copy",  # 直接复制音频流，保持原始采样率和采样深度
]
```

**说明**：
- 优先使用 `copy` 模式，避免重新编码
- 如果源文件格式不兼容，FFmpeg 会自动回退到 AAC 编码（192kbps）

## 四、完整 FFmpeg 命令示例

### 标准命令

```bash
ffmpeg -y -hide_banner -loglevel error \
  -loop 1 -i "kat_20251201_cover.png" \
  -i "kat_20251201_final_mix.mp3" \
  -vf "scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2,fps=1:round=down" \
  -pix_fmt yuv420p \
  -c:v libx264 \
  -preset veryfast \
  -crf 35 \
  -tune stillimage \
  -g 3600 \
  -x264-params "keyint=3600:min-keyint=3600" \
  -vsync vfr \
  -fps_mode passthrough \
  -c:a copy \
  -shortest \
  -movflags +faststart \
  "kat_20251201_youtube.mp4"
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `-y` | 覆盖输出文件（如果存在） |
| `-hide_banner` | 隐藏 FFmpeg 版本信息 |
| `-loglevel error` | 只显示错误信息 |
| `-loop 1` | 循环播放封面图片 |
| `-shortest` | 以最短输入（音频）为准，确保视频长度匹配音频 |
| `-movflags +faststart` | 快速启动：将 moov atom 移到文件开头，便于流式播放 |

## 五、输出文件

### 视频文件

- **文件名**：`{episode_id}_youtube.mp4`
- **分辨率**：4K (3840×2160)
- **编码**：H.264 (libx264)
- **帧率**：1 FPS
- **音频**：直接复制（保持原始采样率和采样深度）

### 检查点文件（可选）

- **文件名**：`{episode_id}_render_complete.flag`
- **格式**：JSON 或空文件
- **内容**：完成时间、文件路径、文件大小等元数据

## 六、性能优化要点

### 1. 预混音架构

- **不再实时混音**：使用预混音的 `final_mix.mp3`
- **减少文件读取**：只需读取封面和音频两个文件
- **降低 CPU 使用**：不需要构建复杂的 filtergraph

### 2. 静态图片优化

- **`-tune stillimage`**：针对静态图片优化，码率降低 20-30 倍
- **`-g 3600`**：fps=1 时，每 3600 秒一个 I 帧，大幅减少文件大小
- **`-crf 35`**：静态图片的合理质量因子

### 3. 编码速度

- **`-preset veryfast`**：快速编码，适合批量渲染
- **`-fps_mode passthrough`**：传递原始帧率，减少处理开销

## 七、McPOS 的实现方式

McPOS 的 `mcpos/adapters/render_engine.py` 采用**与旧世界相同的渲染方案**：

- 使用预混音的 `final_mix.mp3`（256kbps CBR, 48 kHz, 16-bit）
- 使用相同的视频滤镜和编码参数
- 使用相同的音频编码参数（`copy` 模式）

**与旧世界的差异**：
- McPOS 只使用 `final_mix.mp3`（不检查 `full_mix.mp3`）
- McPOS 使用 48 kHz 采样率的音频（旧世界可能使用 44.1 kHz）
- McPOS 的音频标准是 256 kbps CBR（旧世界可能使用 320 kbps 或 VBR）

## 八、关键代码位置

- **旧世界渲染实现**：`kat_rec_web/backend/t2r/utils/direct_video_render.py`
- **渲染配置模块**：`kat_rec_web/backend/t2r/utils/video_render_config.py`
- **McPOS 渲染适配器**：`mcpos/adapters/render_engine.py`
- **McPOS 渲染阶段**：`mcpos/assets/render.py`
- **技术规范文档**：`docs/CHANNEL_PRODUCTION_SPEC.md` (阶段 5: 视频渲染)

## 九、渲染流程总结

```
1. 检查输入文件
   ├─ 封面图片：{episode_id}_cover.png
   └─ 预混音音频：{episode_id}_final_mix.mp3（优先）

2. 构建 FFmpeg 命令
   ├─ 输入：封面图片（-loop 1）+ 预混音音频
   ├─ 视频滤镜：缩放到 4K，填充，1 FPS
   ├─ 视频编码：H.264, CRF 35, preset veryfast, tune stillimage
   └─ 音频编码：copy（直接复制）

3. 执行 FFmpeg
   └─ 输出：{episode_id}_youtube.mp4

4. 验证输出
   ├─ 检查文件是否存在
   ├─ 检查文件大小（不为 0）
   └─ 创建 render_complete.flag（可选）
```

## 十、常见问题

### Q: 为什么使用 `-tune stillimage`？

A: 静态图片视频的特点是画面几乎不变，使用 `stillimage` 调优可以大幅降低码率（20-30 倍），同时保持视觉质量。

### Q: 为什么使用 `-g 3600`？

A: fps=1 时，每 3600 秒（1小时）一个 I 帧已经足够。对于静态图片，不需要频繁的关键帧，这样可以大幅减少文件大小。

### Q: 为什么使用 `-c:a copy`？

A: 预混音音频已经经过响度标准化和编码优化，直接复制可以避免重新编码带来的质量损失和性能开销。

### Q: 如果音频格式不兼容怎么办？

A: FFmpeg 会自动回退到 AAC 编码（192kbps），或者可以在代码中显式检查并回退。

