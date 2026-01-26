# Kat Rec 频道制播流程技术规范

**版本**: 1.0  
**最后更新**: 2025-01-XX  
**适用范围**: 所有 Kat Rec 频道（当前：kat_lofi，可扩展至多频道）

---

## 📋 文档目标

本文档是**频道配置级别的关键技术规范**，旨在实现：

- ✅ **独立性**：脱离代码库也能完整理解制播流程
- ✅ **可重建性**：任何人获得同样素材后，仅凭此文档即可完整重建制播流程
- ✅ **参数完全公开**：playlist、封面、mix、渲染、上传等每一步的技术参数全部公开
- ✅ **技术一致性**：输入输出格式精确描述，确保可重复执行
- ✅ **可审计性**：像专业电视台制作规范一样精确，每一步可追溯
- ✅ **未来可扩容**：支持多频道配置（频道 profile）

---

## 🎯 制播流程总览

```
[初始化] → [封面生成] → [文本资产生成] → [音频混音] → [视频渲染] → [YouTube上传] → [验证]
```

### 阶段定义

1. **初始化 (Init)**: 生成 `playlist.csv` 和 `recipe.json`
2. **封面生成 (Cover)**: 生成 4K 封面图片
3. **文本资产 (Text Assets)**: 生成标题、描述、标签、字幕
4. **音频混音 (Remix)**: 生成最终混音音频（MP3 + WAV）
5. **视频渲染 (Render)**: 生成最终视频文件（MP4）
6. **上传 (Upload)**: 上传到 YouTube
7. **验证 (Verify)**: 验证上传结果

---

## 📁 频道配置文件结构

### 频道目录结构

```
channels/
  {channel_id}/
    channel_profile.json          # 频道元数据
    config/
      channel.json                # 频道配置（时区、发布时间等）
    library/
      songs/                      # 音频库根目录
      images/                     # 图片库根目录
    output/
      {episode_id}/              # 每期输出目录
        playlist.csv              # 歌单文件（核心）
        {episode_id}_cover.png    # 封面图片
        {episode_id}_full_mix.mp3 # 混音音频（MP3）
        {episode_id}_final_mix.wav # 预混音音频（WAV，用于渲染）
        {episode_id}_youtube.mp4  # 最终视频
        {episode_id}_youtube_title.txt
        {episode_id}_youtube_description.txt
        {episode_id}_youtube_tags.txt
        {episode_id}_youtube.srt
        ...
```

### 频道配置文件格式

#### `channel_profile.json`

```json
{
  "id": "kat_lofi",
  "name": "Kat Records",
  "handle": "@KatRecordsStudio",
  "channel_url": "https://www.youtube.com/@KatRecordsStudio",
  "studio_url": "https://studio.youtube.com/channel/UCbLYx6UscJjfZ7Ch9U53nRg",
  "avatar_url": "https://yt3.googleusercontent.com/...",
  "description": "Kat Records Studio exists in the space between sound and silence...",
  "youtube_metadata": {
    "video_count": "700+ releases",
    "view_count": "24M+ views",
    "subscriber_count": "150K+ subscribers",
    "joined_date": "2017-06-11",
    "custom_url": "@KatRecordsStudio"
  }
}
```

#### `config/channel.json`

```json
{
  "timezone": "UTC+7",
  "publish_time_local": "23:00"
}
```

**参数说明**：
- `timezone`: 时区字符串，支持 `UTC+X` 或 `UTC-X` 格式（如 `UTC+7`、`UTC-5`）
- `publish_time_local`: 本地发布时间，格式 `HH:MM`（24小时制）

---

## 📝 阶段 1: 初始化 (Init)

### 输入

- `episode_id`: 期号（格式：`YYYYMMDD`，如 `20251124`）
- 音频库路径：`channels/{channel_id}/library/songs/`
- 图片库路径：`channels/{channel_id}/library/images/`

### 输出

#### `playlist.csv` 格式规范

**文件编码**: UTF-8  
**分隔符**: 逗号 (`,`)  
**换行符**: `\n` (Unix)

**表头**：
```csv
Section,Field,Value,Side,Order,Title,Duration,DurationSeconds,Timeline,Timestamp,Description
```

**行类型**：

1. **Metadata 行**（元信息）：
   ```csv
   Metadata,AlbumTitle,{标题},,,,,,,,
   Metadata,ColorHex,#{颜色十六进制},,,,,,,,
   Metadata,Prompt,{提示词},,,,,,,,
   Metadata,TitleSource,{标题来源},,,,,,,,
   ```

2. **Summary 行**（摘要）：
   ```csv
   Summary,SideTotal,{数量} tracks,{A|B},,,{总时长MM:SS},{总时长秒数},,,,
   ```

3. **Track 行**（曲目列表）：
   ```csv
   Track,,,{A|B},{序号},{曲目名称},{时长MM:SS},{时长秒数},,,,
   ```

4. **Timeline 行 - Needle**（混音时间线）：
   ```csv
   Timeline,,,{A|B},,,,,Needle,{时间戳MM:SS},{事件描述}
   ```

5. **Timeline 行 - Clean**（干净时间线，用于描述/字幕）：
   ```csv
   Timeline,,,{A|B},,,,,Clean,{时间戳MM:SS},{事件描述}
   ```

**时间戳格式**: `MM:SS`（如 `2:12`、`10:45`）

**Timeline 事件类型**：
- `Needle On Vinyl Record`: 唱针落在黑胶上（开始）
- `Vinyl Noise`: 黑胶噪音（曲目之间）
- `Silence`: 静音（3秒）
- `{曲目名称}`: 曲目播放

**示例**：
```csv
Section,Field,Value,Side,Order,Title,Duration,DurationSeconds,Timeline,Timestamp,Description
Metadata,AlbumTitle,Winter Dreams,,,,,,,,
Metadata,ColorHex,#8B4513,,,,,,,,
Track,,,A,1,Cable Car Reverie,2:11,131,,,,
Track,,,A,2,Quiet Field,2:07,127,,,,
Timeline,,,A,,,,,Needle,0:00,Needle On Vinyl Record
Timeline,,,A,,,,,Needle,0:03,Cable Car Reverie
Timeline,,,A,,,,,Needle,2:12,Vinyl Noise
Timeline,,,A,,,,,Needle,2:17,Quiet Field
Timeline,,,B,,,,,Clean,0:00,Cable Car Reverie
Timeline,,,B,,,,,Clean,2:11,Quiet Field
```

#### `recipe.json` 格式

```json
{
  "episode_id": "20251124",
  "channel_id": "kat_lofi",
  "created_at": "2025-11-24T10:00:00Z",
  "tracks": {
    "side_a": [
      {
        "title": "Cable Car Reverie",
        "duration_seconds": 131,
        "order": 1
      }
    ],
    "side_b": [
      {
        "title": "What Happened in This Beat",
        "duration_seconds": 193,
        "order": 1
      }
    ]
  },
  "metadata": {
    "album_title": "Winter Dreams",
    "color_hex": "#8B4513",
    "prompt": "..."
  }
}
```

---

## 🎨 阶段 2: 封面生成 (Cover)

### 输入

- `playlist.csv`
- 图片文件：从 `library/images/` 中选择（或由系统自动选择）

### 输出

- `{episode_id}_cover.png`: 4K 封面图片

### 技术参数

#### 画布规格

- **分辨率**: 3840 × 2160 (4K UHD)
- **颜色模式**: RGBA
- **背景色**: 从图片提取主色调，经过秋季色板增强（混合因子 0.3）

#### 颜色提取算法

1. **主色调提取**：
   - 使用 `PIL.Image` 读取图片
   - 缩放到 150×150 像素（质量优化）
   - 使用 K-means 聚类提取主色调
   - 如果提取失败，回退到 `(128, 128, 128)`

2. **秋季色板增强**：
   - 种子：基于 `episode_id` 和图片文件名生成 MD5 哈希的前8位
   - 混合因子：0.3（30% 原色 + 70% 秋季色板）
   - 秋季色板参考：`@tyleraromatherapy` 风格

#### 文字样式

- **字体**: Lora-Regular.ttf（位于 `assets/fonts/`）
- **颜色**: 白色 `(255, 255, 255)`
- **不透明度**: 85% (`217/255`)
- **样式**: 带噪点颗粒感（`text_style="noise"`）

#### 噪点叠加

- **噪点强度**: 18（范围：10-30）
- **噪点透明度**: 32（范围：16-48）
- **生成方式**: `numpy.random.normal(128, noise_strength, (height, width))`

#### 布局配置

- **标题位置**: 
  - 右侧显示一次（完整标题）
  - 中央垂直显示一次（spine，用于黑胶封面效果）
- **曲目列表位置**: 左侧固定位置
- **字体自动缩放**: 确保每行一个曲目，自动调整字体大小

#### 输出文件

- **文件名**: `{episode_id}_cover.png`
- **格式**: PNG
- **分辨率**: 3840 × 2160
- **颜色深度**: 32-bit RGBA

---

## 📄 阶段 3: 文本资产生成 (Text Assets)

### 输入

- `playlist.csv`
- `{episode_id}_cover.png`（用于颜色提取）

### 输出

#### `{episode_id}_youtube_title.txt`

- **格式**: 纯文本，UTF-8 编码
- **内容**: SEO 优化的 YouTube 标题
- **长度限制**: 100 字符（YouTube 限制）
- **生成方式**: 基于 `playlist.csv` 的 Metadata 和 Track 信息，使用 AI 生成

#### `{episode_id}_youtube_description.txt`

- **格式**: 纯文本，UTF-8 编码
- **内容**: 完整的 YouTube 描述
- **结构**:
  ```
  {欢迎语}

  🎵 Tracklist:

  Side A:
  01. {曲目1}
  02. {曲目2}
  ...

  Side B:
  01. {曲目1}
  02. {曲目2}
  ...

  {结尾语}
  ```
- **生成方式**: 基于 `playlist.csv` 的 Clean Timeline 生成

#### `{episode_id}_youtube_tags.txt`

- **格式**: 每行一个标签，UTF-8 编码
- **默认标签**:
  ```
  lofi
  music
  Kat Records
  chill
  ```
- **生成方式**: 基于频道配置和内容生成

#### `{episode_id}_youtube.srt`

- **格式**: SRT 字幕文件，UTF-8 编码
- **时间戳格式**: `HH:MM:SS,mmm`（如 `00:02:11,000`）或 `H:MM:SS,mmm`（超过一小时时，如 `1:01:03,000`）
- **内容**: 基于 Clean Timeline 生成，每行一个曲目
- **时间格式规范**:
  - 分钟和秒的最大值是 **59**，不允许 `61:03,000` 这样的格式
  - 如果分钟超过 59，必须进位到小时（如 `61:03,000` → `1:01:03,000`）
  - 如果秒超过 59，必须进位到分钟（如 `00:65,000` → `00:01:05,000`）
- **示例**:
  ```
  1
  00:00:00,000 --> 00:02:11,000
  Cable Car Reverie

  2
  00:02:11,000 --> 00:04:18,000
  Quiet Field
  
  3
  1:01:03,000 --> 1:01:08,000
  Long Track Name
  ```

---

## 🎵 阶段 4: 音频混音 (Remix)

### 输入

- `playlist.csv`（必须包含 Needle Timeline）
- 音频库：`channels/{channel_id}/library/songs/`
- 音效库：`assets/sfx/`
  - `Needle_Start.mp3`: 唱针开始音效
  - `Vinyl_Noise.mp3`: 黑胶噪音

### 输出

#### `{episode_id}_full_mix.mp3`

- **格式**: MP3
- **编码器**: `libmp3lame`
- **码率**: 256 kbps (`-b:a 256k`)
- **质量**: `-q:a 2`（高质量）
- **采样率**: 44.1 kHz
- **声道**: 立体声

#### `{episode_id}_final_mix.wav`

- **格式**: 16-bit PCM WAV
- **编码器**: `pcm_s16le`
- **采样率**: 44.1 kHz
- **声道**: 立体声
- **用途**: 用于视频渲染（预混音，提升性能）

### 技术参数

#### FFmpeg Filtergraph 构建

**统一采样格式**：
- `aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo`

**音量控制**：
- 曲目：`volume=1.0`（原始音量）
- Needle Start: `volume=10^(needle_gain_db/20.0)`（默认 `-18dB`，即 `volume=0.1259`）
- Vinyl Noise: `volume=10^(vinyl_noise_db/20.0)`（默认 `-18dB`，即 `volume=0.1259`）

**延迟定位**：
- `adelay={delay_ms}|{delay_ms}`（毫秒，基于 Timeline 时间戳）

**静音处理**：
- `anullsrc=r=44100:cl=stereo,atrim=0:3`（生成 3 秒静音）

**混音叠加**：
- `amix=inputs={N}:normalize=0:duration=longest`
  - `normalize=0`: 不归一化（保持原始音量比例）
  - `duration=longest`: 以最长轨道为准

**响度标准化**：
- `loudnorm=I=-14:TP=-1.5:LRA=11:print_format=summary`
  - `I=-14`: 目标响度 -14 LUFS（ITU-R BS.1770-4 标准）
  - `TP=-1.5`: 真峰值限制 -1.5 dBTP
  - `LRA=11`: 响度范围 11 LU

#### 完整 FFmpeg 命令示例

**生成 final_mix.wav**：
```bash
ffmpeg -y -hide_banner -loglevel error \
  -i "Needle_Start.mp3" \
  -i "track1.mp3" \
  -i "Vinyl_Noise.mp3" \
  -i "track2.mp3" \
  ... \
  -filter_complex "
    [0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume=0.1259,adelay=0|0[a0];
    [1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume=1.0,adelay=3000|3000[a1];
    [2:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume=0.1259,adelay=132000|132000[a2];
    [a0][a1][a2]amix=inputs=3:normalize=0:duration=longest,loudnorm=I=-14:TP=-1.5:LRA=11:print_format=summary[mix]
  " \
  -map "[mix]" \
  -c:a pcm_s16le \
  "{episode_id}_final_mix.wav"
```

**生成 final_mix.mp3**：
```bash
ffmpeg -y -hide_banner -loglevel error \
  ...（输入文件同上）... \
  -filter_complex "...（同上）..." \
  -map "[mix]" \
  -c:a libmp3lame \
  -b:a 256k \
  -q:a 2 \
  "{episode_id}_final_mix.mp3"
```

### 检查点文件

- `{episode_id}.remix.complete.flag`: JSON 格式，包含完成时间、文件路径等元数据

---

## 🎬 阶段 5: 视频渲染 (Render)

### 输入

- `{episode_id}_cover.png`: 4K 封面图片
- `{episode_id}_final_mix.wav`: 预混音音频（优先使用）
- 或 `{episode_id}_full_mix.mp3`: 备用音频（如果 WAV 不存在）

### 输出

- `{episode_id}_youtube.mp4`: 最终视频文件

### 技术参数

#### 视频编码参数（全频道标准）

**编码器**: `libx264`  
**预设**: `veryfast`（编码速度）  
**质量因子**: `CRF=35`（Constant Rate Factor）  
**调优**: `tune=stillimage`（针对静态图片优化，码率降低 20-30 倍）  
**关键帧间隔**: `g=3600`（每 3600 秒一个 I 帧，fps=1 时）  
**像素格式**: `yuv420p`（标准格式，文件更小，兼容性更好）

#### x264 参数

- `keyint=3600:min-keyint=3600`（与 `-g 3600` 配合）

#### 视频滤镜

```bash
scale=3840:2160:force_original_aspect_ratio=decrease,
pad=3840:2160:(ow-iw)/2:(oh-ih)/2,
fps=1:round=down
```

**说明**：
- `scale`: 缩放到 4K，保持宽高比（`force_original_aspect_ratio=decrease`）
- `pad`: 填充到 3840×2160，居中（`(ow-iw)/2:(oh-ih)/2`）
- `fps=1`: 帧率 1 FPS（静态图片）
- `round=down`: 向下舍入，确保时长精确

#### 音频编码参数

- **编码器**: `copy`（直接复制音频流，保持原始采样率和采样深度）
- **备用**: 如果源文件格式不兼容，回退到 `aac` 编码，码率 `192k`

#### 时间戳模式

- `vsync=vfr`: 可变帧率
- `fps_mode=passthrough`: 传递原始帧率

#### 容器参数

- `movflags=+faststart`: 快速启动（将 moov atom 移到文件开头，便于流式播放）

#### 完整 FFmpeg 命令

```bash
ffmpeg -y -hide_banner -loglevel error \
  -loop 1 -i "{episode_id}_cover.png" \
  -i "{episode_id}_final_mix.wav" \
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
  "{episode_id}_youtube.mp4"
```

**参数说明**：
- `-loop 1`: 循环播放封面图片
- `-shortest`: 以最短输入（音频）为准，确保视频长度匹配音频
- `-y`: 覆盖输出文件（如果存在）

#### 性能优化

- **优先使用 final_mix.wav**: 如果存在，直接使用预混音 WAV，绕过事件-based filtergraph，大幅提升性能
- **回退机制**: 如果 `final_mix.wav` 不存在，回退到从 `playlist.csv` 构建 filtergraph 的旧逻辑

### 检查点文件

- `{episode_id}.render.complete.flag`: JSON 格式，包含完成时间、文件路径、文件大小等元数据

---

## 📤 阶段 6: YouTube 上传 (Upload)

### 输入

- `{episode_id}_youtube.mp4`: 视频文件
- `{episode_id}_cover.png`: 缩略图（可选，自动调整大小）
- `{episode_id}_youtube_title.txt`: 标题
- `{episode_id}_youtube_description.txt`: 描述
- `{episode_id}_youtube_tags.txt`: 标签
- `{episode_id}_youtube.srt`: 字幕文件（可选）

### 输出

- `upload_result.json`: 上传结果（包含 `video_id`）
- YouTube 视频 URL

### 技术参数

#### 视频元数据构建

**Snippet（片段）**：
```json
{
  "title": "{从文件读取}",
  "description": "{从文件读取}",
  "tags": ["lofi", "music", "Kat Records", "chill", ...],
  "categoryId": "10",
  "defaultLanguage": "en",
  "localized": {
    "title": "{同 title}",
    "description": "{同 description}"
  }
}
```

**Status（状态）**：
```json
{
  "privacyStatus": "unlisted",
  "license": "creativeCommon",
  "embeddable": true,
  "publicStatsViewable": true,
  "selfDeclaredMadeForKids": false,
  "publishAt": "{ISO 8601 格式，基于频道配置的时区和发布时间}"
}
```

**Recording Details（录制详情）**：
```json
{
  "recordingDate": "{从 episode_id 解析的日期，ISO 8601 格式}"
}
```

#### 发布时间计算

**逻辑**：
1. 解析 `episode_id` 为日期（如 `20251124` → `2025-11-24`）
2. 读取频道配置的时区（如 `UTC+7`）和发布时间（如 `23:00`）
3. 计算本地发布时间：`{日期} {发布时间}`（如 `2025-11-24 23:00:00 UTC+7`）
4. 转换为 UTC：`2025-11-24 16:00:00 UTC`
5. 格式化为 RFC 3339：`2025-11-24T16:00:00.000Z`

**特殊情况**：
- 如果排播日期是当天，且当前时间 < 11:00，则排播到当天 12:00-14:00 之间随机时间
- 如果排播日期是当天，且当前时间 >= 11:00，则立即发布（`publishAt` = 当前时间）

#### 缩略图处理

- **最大文件大小**: 2 MB
- **最大宽度**: 1280 像素
- **自动调整**: 如果超过限制，自动缩放并压缩

#### 上传方式

- **分块上传**: 支持大文件分块上传（`resumable=True`）
- **自动分块**: 文件大小 < 256 MB 时使用标准上传，>= 256 MB 时自动分块
- **重试机制**: 最多重试 5 次

#### 添加到播放列表

- 如果频道配置中包含 `playlist_id`，自动将视频添加到播放列表

### 检查点文件

- `upload_result.json`: JSON 格式，包含：
  ```json
  {
    "episode_id": "20251124",
    "video_id": "dQw4w9WgXcQ",
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "uploaded_at": "2025-11-24T16:00:00.000Z",
    "status": "uploaded"
  }
  ```

---

## ✅ 阶段 7: 验证 (Verify)

### 输入

- `upload_result.json`（包含 `video_id`）

### 输出

- 验证结果（视频是否成功上传并可见）

### 技术参数

#### 验证逻辑

1. **延迟验证**: 上传完成后延迟 5 分钟（300 秒）执行验证（给 YouTube API 时间处理）
2. **API 调用**: 使用 YouTube Data API v3 的 `videos().list()` 方法
3. **检查字段**:
   - `snippet.publishedAt`: 发布时间
   - `status.uploadStatus`: 上传状态（应为 `processed`）
   - `status.privacyStatus`: 隐私状态（应为 `unlisted`）

#### 验证结果

- **成功**: 视频已处理并可见
- **失败**: 视频未处理或不可见（记录错误信息）

---

## 🔄 完整流程示例

### 示例：生成 `20251124` 期

#### 1. 初始化

**输入**：
- `episode_id`: `20251124`
- 音频库：`channels/kat_lofi/library/songs/`
- 图片库：`channels/kat_lofi/library/images/`

**输出**：
- `channels/kat_lofi/output/20251124/playlist.csv`
- `channels/kat_lofi/output/20251124/recipe.json`

#### 2. 封面生成

**输入**：
- `playlist.csv`

**输出**：
- `channels/kat_lofi/output/20251124/20251124_cover.png` (3840×2160)

#### 3. 文本资产生成

**输入**：
- `playlist.csv`
- `20251124_cover.png`

**输出**：
- `20251124_youtube_title.txt`
- `20251124_youtube_description.txt`
- `20251124_youtube_tags.txt`
- `20251124_youtube.srt`

#### 4. 音频混音

**输入**：
- `playlist.csv`
- 音频库文件

**输出**：
- `20251124_full_mix.mp3` (256 kbps)
- `20251124_final_mix.wav` (16-bit PCM, 44.1 kHz)
- `20251124.remix.complete.flag`

#### 5. 视频渲染

**输入**：
- `20251124_cover.png`
- `20251124_final_mix.wav`

**输出**：
- `20251124_youtube.mp4` (4K, 1 FPS, CRF 35, yuv420p)
- `20251124.render.complete.flag`

#### 6. YouTube 上传

**输入**：
- `20251124_youtube.mp4`
- `20251124_youtube_title.txt`
- `20251124_youtube_description.txt`
- `20251124_youtube_tags.txt`
- `20251124_cover.png`（缩略图）

**输出**：
- `upload_result.json`（包含 `video_id`）
- YouTube 视频 URL

#### 7. 验证

**输入**：
- `upload_result.json`

**输出**：
- 验证结果（成功/失败）

---

## 📊 文件格式规范总结

### 输入文件格式

| 文件类型 | 格式 | 编码 | 说明 |
|---------|------|------|------|
| 音频文件 | MP3/WAV/FLAC/M4A/AAC | - | 音频库支持格式 |
| 图片文件 | PNG/JPEG | - | 图片库支持格式 |
| `playlist.csv` | CSV | UTF-8 | 核心歌单文件 |

### 输出文件格式

| 文件类型 | 格式 | 编码 | 分辨率/码率 | 说明 |
|---------|------|------|-----------|------|
| 封面 | PNG | RGBA | 3840×2160 | 4K 封面 |
| 混音音频 (MP3) | MP3 | libmp3lame | 256 kbps | 最终混音 |
| 预混音音频 (WAV) | WAV | pcm_s16le | 44.1 kHz, 16-bit | 用于渲染 |
| 视频 | MP4 | H.264 (libx264) | 3840×2160, 1 FPS, CRF 35 | 最终视频 |
| 标题 | TXT | UTF-8 | - | YouTube 标题 |
| 描述 | TXT | UTF-8 | - | YouTube 描述 |
| 标签 | TXT | UTF-8 | - | YouTube 标签（每行一个） |
| 字幕 | SRT | UTF-8 | - | YouTube 字幕 |

---

## 🔧 技术依赖

### 必需工具

- **FFmpeg**: 音频/视频处理（版本 >= 4.0）
- **Python**: 脚本执行（版本 >= 3.11）
- **PIL/Pillow**: 图片处理
- **NumPy**: 数值计算（颜色提取、噪点生成）

### API 依赖

- **YouTube Data API v3**: 视频上传和验证
- **OpenAI API**（可选）: 文本生成（标题、描述）

---

## 📐 参数参考表

### 音频参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 采样率 | 44100 Hz | 标准 CD 质量 |
| 声道 | 立体声 (stereo) | 双声道 |
| 响度目标 | -14 LUFS | ITU-R BS.1770-4 标准 |
| 真峰值限制 | -1.5 dBTP | 防止削波 |
| 响度范围 | 11 LU | 动态范围 |
| Needle Start 音量 | -18 dB | 相对原始音量 |
| Vinyl Noise 音量 | -18 dB | 相对原始音量 |
| MP3 码率 | 256 kbps | 高质量 |
| WAV 位深 | 16-bit | PCM 格式 |

### 视频参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 分辨率 | 3840×2160 | 4K UHD |
| 帧率 | 1 FPS | 静态图片 |
| 编码器 | libx264 | H.264 编码 |
| 预设 | veryfast | 编码速度 |
| CRF | 35 | 质量因子 |
| 调优 | stillimage | 静态图片优化 |
| 像素格式 | yuv420p | 标准格式 |
| 关键帧间隔 | 3600 秒 | 1 小时（fps=1 时） |
| 音频编码 | copy | 直接复制（或 AAC 192k） |

### 封面参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 分辨率 | 3840×2160 | 4K |
| 颜色模式 | RGBA | 32-bit |
| 文字颜色 | (255, 255, 255) | 白色 |
| 文字不透明度 | 85% (217/255) | 半透明 |
| 噪点强度 | 18 | 范围 10-30 |
| 噪点透明度 | 32 | 范围 16-48 |
| 颜色混合因子 | 0.3 | 30% 原色 + 70% 秋季色板 |

---

## 🎯 多频道扩展

### 频道配置隔离

每个频道拥有独立的：
- 配置文件：`channels/{channel_id}/config/channel.json`
- 输出目录：`channels/{channel_id}/output/`
- 音频库：`channels/{channel_id}/library/songs/`
- 图片库：`channels/{channel_id}/library/images/`

### 频道特定参数

可在频道配置中覆盖的参数：
- 时区（`timezone`）
- 发布时间（`publish_time_local`）
- YouTube 频道 ID
- 播放列表 ID
- 默认标签
- 上传隐私设置

### 全局参数

所有频道共享的参数：
- 视频渲染参数（CRF、预设、分辨率等）
- 音频混音参数（响度、码率等）
- 封面生成参数（分辨率、字体等）

---

## 📝 检查点文件格式

### `{episode_id}.remix.complete.flag`

```json
{
  "episode_id": "20251124",
  "channel_id": "kat_lofi",
  "stage": "remix",
  "completed_at": "2025-11-24T10:30:00.000Z",
  "files": {
    "full_mix_mp3": "channels/kat_lofi/output/20251124/20251124_full_mix.mp3",
    "final_mix_wav": "channels/kat_lofi/output/20251124/20251124_final_mix.wav"
  }
}
```

### `{episode_id}.render.complete.flag`

```json
{
  "episode_id": "20251124",
  "channel_id": "kat_lofi",
  "stage": "render",
  "completed_at": "2025-11-24T11:00:00.000Z",
  "files": {
    "video": "channels/kat_lofi/output/20251124/20251124_youtube.mp4",
    "file_size_bytes": 52428800
  }
}
```

### `upload_result.json`

```json
{
  "episode_id": "20251124",
  "channel_id": "kat_lofi",
  "video_id": "dQw4w9WgXcQ",
  "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "uploaded_at": "2025-11-24T16:00:00.000Z",
  "status": "uploaded",
  "metadata": {
    "title": "...",
    "description": "...",
    "privacy_status": "unlisted"
  }
}
```

---

## 🔍 故障排查

### 常见问题

1. **playlist.csv 格式错误**
   - 检查编码是否为 UTF-8
   - 检查表头是否完整
   - 检查 Timeline 行是否包含 Needle 和 Clean 两种类型

2. **音频混音失败**
   - 检查音频文件是否存在
   - 检查 Timeline 时间戳格式（MM:SS）
   - 检查音效文件（Needle_Start.mp3, Vinyl_Noise.mp3）是否存在

3. **视频渲染失败**
   - 检查封面图片是否存在且为 4K
   - 检查 final_mix.wav 是否存在
   - 检查 FFmpeg 版本是否 >= 4.0

4. **YouTube 上传失败**
   - 检查 API 凭证是否有效
   - 检查视频文件大小是否 < 256 GB（YouTube 限制）
   - 检查缩略图大小是否 < 2 MB

---

## 📚 参考文档

- [FFmpeg 官方文档](https://ffmpeg.org/documentation.html)
- [YouTube Data API v3 文档](https://developers.google.com/youtube/v3)
- [ITU-R BS.1770-4 响度标准](https://www.itu.int/rec/R-REC-BS.1770-4-201510-I/)

---

## 📄 版本历史

- **v1.0** (2025-01-XX): 初始版本，完整定义所有制播流程技术参数

---

**文档维护**: 本文档应与代码库同步更新，任何技术参数变更都应在此文档中反映。

