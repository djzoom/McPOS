# 视频时长修复指南

## 问题描述

使用静态封面图 + 长音频生成视频时，不同编码器产生的视频时长与音频不一致：
- **x264**: +33秒偏差
- **VTB (h264_videotoolbox)**: +3秒偏差  
- **MJPEG**: 时长准确但文件体积巨大（3GB+）

## 解决方案

### 方案A：30fps 固定帧率（**默认，推荐**）

**原理**：用30fps固定帧率喂给编码器，避免1fps帧长带来的大颗粒四舍五入。

**特点**：
- ✅ 时长精度高（≤1s误差）
- ✅ 保持上传友好性（H.264 + yuv420p + faststart）
- ⚠️ 文件体积略大（比1fps多约30倍帧数）
- ⚠️ 编码时间略长（但仍在可接受范围）

**使用方式**：
```bash
# 默认使用30fps方案
python scripts/local_picker/create_mixtape.py --font_name Lora-Regular

# 明确指定
python scripts/local_picker/create_mixtape.py --font_name Lora-Regular --duration-fix 30fps
```

### 方案B：显式时长裁剪（最强一致性）

**原理**：用 `-t $DUR` 从根源上限定视频时长，确保视频不超过音频长度。

**特点**：
- ✅ 时长完全精确（与音频一致）
- ✅ 可批量自动化
- ⚠️ 需要预先获取音频时长（自动处理）

**使用方式**：
```bash
python scripts/local_picker/create_mixtape.py --font_name Lora-Regular --duration-fix explicit
```

### 方案C：原逻辑（不推荐，仅用于对比）

**使用方式**：
```bash
python scripts/local_picker/create_mixtape.py --font_name Lora-Regular --duration-fix none
```

## 编码器选择逻辑

### 自动模式（--codec_v auto，默认）

1. **优先使用环境测试结果**：
   - 读取 `config/best_encoder.json`
   - 使用初始化或每周测试确定的最快编码器
   - 验证编码器仍然可用

2. **回退到硬件加速优先**：
   - `h264_videotoolbox` (macOS 硬件加速)
   - `h264_nvenc` (NVIDIA GPU)
   - `libx264` (软件编码，通用回退)

3. **MJPEG 不在自动模式中**：
   - 虽然速度快，但文件体积太大（约3GB vs 150-250MB）
   - 仅在手动指定时使用

### 手动指定编码器

```bash
# 使用 VTB（macOS 硬件加速，推荐）
python scripts/local_picker/create_mixtape.py --codec_v h264_videotoolbox

# 使用 x264（软件编码，最稳定）
python scripts/local_picker/create_mixtape.py --codec_v libx264

# 使用 MJPEG（速度快但体积大）
python scripts/local_picker/create_mixtape.py --codec_v mjpeg
```

## 环境测试依赖

### 当前机制（OK，推荐保持）

1. **初始化测试**（`make init` 或 `python scripts/init_env.py`）：
   - 首次运行或环境变化时自动测试
   - 测试所有可用编码器，选择最快的
   - 保存配置到 `config/best_encoder.json`

2. **每周测试**（`make weekly-bench` 或 `python scripts/weekly_bench.py`）：
   - 每周定期验证性能
   - 环境变化时自动重新测试
   - 更新最佳编码器配置

3. **自动应用**：
   - `create_mixtape.py` 自动读取配置
   - 优先使用测试确定的最佳编码器
   - 如果配置不可用，回退到硬件加速优先

### 为什么这个机制OK？

✅ **智能缓存**：避免每次运行都测试，节省时间  
✅ **环境感知**：检测硬件/软件变化，自动重新测试  
✅ **可靠回退**：如果配置不可用，有明确的回退逻辑  
✅ **用户可控**：可以手动指定编码器，不依赖测试  

### 建议

保持当前机制，但可以：
- 在视频生成日志中明确标注编码器选择逻辑

## 验证修复效果

### 检查时长一致性

生成视频后，运行诊断：

```bash
# 检查视频时长
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 output/video/*.mp4

# 检查音频时长
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 output/audio/*_full_mix.mp3
```

### 预期结果

- **方案A (30fps)**：视频时长 - 音频时长 ≤ 1秒
- **方案B (explicit)**：视频时长 = 音频时长（严格一致）
- **方案C (none)**：可能有几秒到几十秒偏差（不推荐）

## 性能对比参考

基于 3872.88秒（≈64分钟）音频的测试结果：

| 编码器 | 编码时间 | 文件大小 | 时长准确性 |
|--------|----------|----------|------------|
| h264_videotoolbox (30fps) | ~26分钟 | ~240MB | ✅ ≤1s误差 |
| mjpeg | ~27分钟 | ~3123MB | ✅ 准确 |
| libx264 (30fps) | ~29分钟 | ~149MB | ✅ ≤1s误差 |

**推荐选择**：`h264_videotoolbox`（macOS硬件加速，最快且体积合理）

