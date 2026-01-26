# 旧世界混音方式详解

本文档描述旧世界（legacy）的混音实现方式，包括 SFX 插入逻辑和时间轴安排。

## 一、混音引擎类型

旧世界支持两种混音引擎：

### 1. FFmpeg 引擎（默认）

**位置**：`scripts/local_picker/remix_mixtape.py` (main 函数，`args.engine == "ffmpeg"`)

**工作原理**：
- 为每个 timeline 事件创建一个独立的 FFmpeg 输入
- 使用 `adelay` filter 将每个音频片段定位到指定时间戳
- 使用 `amix` filter 将所有片段叠加到一条音轨上
- 最后应用 `loudnorm` 进行响度标准化

**时间轴安排**：
```
从第 0 秒开始：
- 每个事件（曲目或 SFX）根据 playlist.csv 中的 timestamp 字段定位
- 使用 adelay={delay_ms}|{delay_ms} 将音频延迟到指定位置
- 所有片段叠加到一条静音基轨上
- 最终输出长度 = max(所有事件的 end_ms)
```

**SFX 插入方式**：
- SFX 和曲目一样，都是 timeline 中的独立事件
- 每个 SFX 有自己的时间戳（timestamp）
- 通过 `adelay` 在指定位置开始播放
- SFX 音量：-18 dB（约 12.6% 音量）

**示例 FFmpeg filtergraph**：
```bash
# 每个事件一个 filter：
[0:a]aformat=...,volume={vol},adelay={delay_ms}|{delay_ms}[a0]
[1:a]aformat=...,volume={vol},adelay={delay_ms}|{delay_ms}[a1]
...
[a0][a1][a2]...amix=inputs={N}:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[mix]
```

### 2. Pydub 引擎（可选）

**位置**：`scripts/local_picker/remix_mixtape.py` (main 函数，`args.engine == "pydub"`)

**两种模式**：

#### 模式 A：Timeline 模式（`--mix_mode timeline`）

**工作原理**：
- 解析所有 timeline 事件，收集 `(start_ms, segment, kind)`
- 创建一条全长静音基轨：`AudioSegment.silent(duration=max_end + 1000)`
- 使用 `overlay()` 方法将每个片段叠加到基轨的指定位置

**时间轴安排**：
```
从第 0 秒开始：
- 创建一条 max_end + 1000 毫秒的静音基轨
- 遍历所有事件，按时间戳顺序：
  - 曲目：在 start_ms 位置叠加，长度 = 曲目原始长度 - 淡出时间
  - SFX：在 start_ms 位置叠加，长度 = SFX 文件长度
- 最终输出长度 = max(所有事件的 end_ms) + 1000ms（缓冲）
```

**SFX 插入方式**：
- SFX 和曲目一样，通过 `overlay(segment, position=start_ms)` 叠加
- SFX 音量：-18 dB（在 `prepare_segment` 中应用）
- SFX 淡入淡出：80ms 淡入，200ms 淡出

#### 模式 B：Sequential 模式（`--mix_mode sequential`）

**工作原理**：
- 按 timeline 事件的出现顺序，依次拼接音频片段
- 曲目之间使用 `crossfade` 进行交叉淡入淡出
- SFX 和曲目之间不使用 crossfade，直接拼接

**时间轴安排**：
```
从第 0 秒开始：
- 第一个事件：直接添加到 chain
- 后续事件：
  - 如果前一个是曲目且当前也是曲目：使用 crossfade 拼接
  - 否则：直接拼接（chain + seg）
- 最终输出长度 = 所有片段长度之和（减去 crossfade 重叠部分）
```

**SFX 插入方式**：
- SFX 作为独立片段，按顺序插入到 chain 中
- 曲目 → SFX：直接拼接（无 crossfade）
- SFX → 曲目：直接拼接（无 crossfade）
- 曲目 → 曲目：使用 crossfade（默认 1500ms，可配置）

## 二、SFX 类型和插入位置

### SFX 类型

1. **Needle On Vinyl Record**（针落音效）
   - 文件：`assets/sfx/Needle_Start.mp3`
   - 音量：-18 dB
   - 位置：每个 Side 开始前（Side A 和 Side B 的第一条事件）
   - 时长：3 秒（在 timeline 中）

2. **Vinyl Noise**（黑胶噪音）
   - 文件：`assets/sfx/Vinyl_Noise.mp3`
   - 音量：-18 dB
   - 位置：曲目之间（不是最后一首曲目之后）
   - 时长：5 秒（在 timeline 中）

3. **Silence**（静音）
   - 生成方式：`AudioSegment.silent(duration=3000)` 或 FFmpeg `anullsrc`
   - 位置：Side A 结束后，Side B 开始前
   - 时长：3 秒

### SFX 插入规则（Needle Timeline）

```
Side A:
  0:00 - Needle On Vinyl Record (3秒)
  0:03 - Track 1 开始（duration - 2秒淡出）
  ...  - Track 1 结束
  ...  - Vinyl Noise (5秒) [如果不是最后一首]
  ...  - Track 2 开始
  ...  - ...
  ...  - Track N 结束
  ...  - Silence (3秒)

Side B:
  ...  - Needle On Vinyl Record (3秒)
  ...  - Track 1 开始
  ...  - Vinyl Noise (5秒) [如果不是最后一首]
  ...  - Track 2 开始
  ...  - ...
```

## 三、时间轴计算方式

### Needle Timeline（用于混音）

**计算方式**（与 `_calculate_needle_timeline_duration` 一致）：

```python
total_time = 0

# Side A 开始
total_time += 3  # Needle On Vinyl Record

# Side A 曲目
for idx, track in enumerate(side_a):
    total_time += max(0, track["duration_seconds"] - 2)  # 减去 2 秒淡出
    if idx < len(side_a) - 1:
        total_time += 5  # Vinyl Noise（不是最后一首）

# A 面结束
total_time += 3  # Silence

# Side B 开始
total_time += 3  # Needle On Vinyl Record

# Side B 曲目
for idx, track in enumerate(side_b):
    total_time += max(0, track["duration_seconds"] - 2)  # 减去 2 秒淡出
    if idx < len(side_b) - 1:
        total_time += 5  # Vinyl Noise（不是最后一首）
```

### Clean Timeline（用于字幕生成）

- 只包含曲目，不包含 SFX
- 使用 Needle Timeline 中对应曲目的开始时间戳
- 确保字幕时间码与音频混音对齐

## 四、不同引擎/模式的时间轴处理对比

| 特性 | FFmpeg 引擎 | Pydub Timeline | Pydub Sequential |
|------|------------|----------------|------------------|
| **时间定位** | `adelay` filter | `overlay(position=start_ms)` | 顺序拼接，无时间定位 |
| **SFX 插入** | 独立事件，按时间戳叠加 | 独立事件，按时间戳叠加 | 顺序插入，无时间戳 |
| **曲目淡入淡出** | 在 filtergraph 中处理 | `fade_in(120ms).fade_out(200ms)` | `fade_in(120ms).fade_out(200ms)` |
| **SFX 淡入淡出** | 在 filtergraph 中处理 | `fade_in(80ms).fade_out(200ms)` | `fade_in(80ms).fade_out(200ms)` |
| **交叉淡入淡出** | 无（叠加模式） | 无（叠加模式） | 有（曲目之间 1500ms） |
| **响度标准化** | `loudnorm` filter | 无（pydub 不支持） | 无（pydub 不支持） |
| **输出长度** | max(所有事件 end_ms) | max(所有事件 end_ms) + 1000ms | 所有片段长度之和 |

## 五、McPOS 的实现方式

McPOS 的 `mcpos/assets/mix.py` 采用 **FFmpeg 引擎的 Timeline 模式**：

- 解析 playlist.csv 的 "Needle" timeline
- 为每个事件创建 FFmpeg filter（`adelay` + `volume`）
- 使用 `amix` 叠加所有片段
- 应用 `loudnorm` 进行响度标准化
- 输出 256 kbps CBR MP3

**与旧世界的差异**：
- McPOS 只生成 `final_mix.mp3`（256 kbps），不生成 `full_mix.mp3`（320 kbps）
- McPOS 使用 48 kHz 采样率（旧世界使用 44.1 kHz）
- McPOS 的 SFX 音量计算方式与旧世界一致（-18 dB）

## 六、关键代码位置

- **旧世界 FFmpeg 引擎**：`scripts/local_picker/remix_mixtape.py` (行 394-485)
- **旧世界 Pydub 引擎**：`scripts/local_picker/remix_mixtape.py` (行 293-392)
- **McPOS 混音实现**：`mcpos/assets/mix.py` (行 199-426)
- **时间轴计算**：`mcpos/assets/init.py` (行 314-361, `_calculate_needle_timeline_duration`)

