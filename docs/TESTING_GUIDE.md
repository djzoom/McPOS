# McPOS 测试指南：生成 Kat 20251201 的所有资产

本指南将教你如何使用 McPOS 命令行工具一步步生成 `kat_20251201` 的所有资产。

## 前置条件

1. **设置环境变量（重要！）**：
   ```bash
   # 方法 1: 加载 .envrc（推荐）
   source .envrc
   
   # 方法 2: 手动导出（如果 .envrc 不存在）
   export OPENAI_API_KEY='your-api-key-here'
   
   # 验证是否设置成功
   echo $OPENAI_API_KEY | head -c 20  # 应该显示 API key 的前 20 个字符
   ```
   
   **注意**：如果使用 `direnv`，可以自动加载 `.envrc`：
   ```bash
   # 安装 direnv（如果未安装）
   brew install direnv
   
   # 在 ~/.zshrc 中添加（如果未添加）
   echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
   
   # 允许当前目录的 .envrc
   direnv allow
   ```

2. **确保环境已配置**：
   ```bash
   # 检查 Python 环境
   python3 --version
   
   # 检查依赖是否安装
   pip list | grep -E "pillow|typer|numpy"
   ```

2. **检查资源库**：
   ```bash
   # 检查曲库
   ls -la channels/kat/library/songs/ | head -5
   
   # 检查图片池
   ls -la images_pool/available/ | head -5
   
   # 检查 tracklist.csv
   head -3 channels/kat/library/tracklist.csv
   ```

3. **检查字体文件**（可选，用于封面生成）：
   ```bash
   ls -la assets/fonts/Lora-Regular.ttf 2>/dev/null || echo "字体文件不存在，将使用系统默认字体"
   ```

## 步骤 1：初始化（INIT）

生成 `playlist.csv` 和 `recipe.json`，这是所有后续阶段的基础。

```bash
# 使用 init-episode 命令
python3 -m mcpos.cli.main init-episode kat kat_20251201
```

**预期输出**：
```
初始化 kat_20251201 (channel: kat)...
输出目录: channels/kat/output/kat_20251201
✅ 初始化完成: kat_20251201
   playlist.csv: True
   recipe.json: True
```

**验证**：
```bash
# 检查生成的文件
ls -lh channels/kat/output/kat_20251201/

# 查看 playlist.csv 内容
head -20 channels/kat/output/kat_20251201/playlist.csv

# 查看 recipe.json 内容
cat channels/kat/output/kat_20251201/recipe.json
```

**如果失败**：
- 检查 `channels/kat/library/tracklist.csv` 是否存在且格式正确
- 检查 `channels/kat/library/songs/` 目录是否有曲目文件
- 查看错误信息，可能需要更新 `tracklist.csv` 中的曲目时长

---

## 步骤 2：生成基础文本（TEXT_BASE）

生成 YouTube 标题、描述和标签。**注意**：此阶段需要 OpenAI API Key。

```bash
# 确保已加载 .envrc（如果未加载）
source .envrc

# 运行 TEXT_BASE 阶段
python3 -m mcpos.cli.main run-stage kat kat_20251201 TEXT_BASE
```

**或者一行命令**：
```bash
source .envrc && python3 -m mcpos.cli.main run-stage kat kat_20251201 TEXT_BASE
```

**预期输出**：
```
运行阶段 TEXT_BASE for kat_20251201 (channel: kat)...
✅ 阶段 TEXT_BASE 完成: kat_20251201
   耗时: 5.23 秒
   生成文件:
     ✅ kat_20251201_youtube_title.txt
     ✅ kat_20251201_youtube_description.txt
     ✅ kat_20251201_youtube_tags.txt
```

**验证**：
```bash
# 查看生成的标题
cat channels/kat/output/kat_20251201/kat_20251201_youtube_title.txt

# 查看生成的描述（前几行）
head -10 channels/kat/output/kat_20251201/kat_20251201_youtube_description.txt
```

**如果失败**：
- 检查 `OPENAI_API_KEY` 环境变量是否设置
- 检查网络连接（需要访问 OpenAI API）
- 如果 API 不可用，可以暂时跳过此阶段（封面会使用 fallback 标题）

---

## 步骤 3：生成封面（COVER）

生成封面图片。此阶段可以与 TEXT_BASE 并行执行（都只依赖 playlist.csv）。

```bash
# 运行 COVER 阶段
python3 -m mcpos.cli.main run-stage kat kat_20251201 COVER
```

**预期输出**：
```
运行阶段 COVER for kat_20251201 (channel: kat)...
✅ 阶段 COVER 完成: kat_20251201
   耗时: 2.45 秒
   生成文件:
     ✅ kat_20251201_cover.png
```

**验证**：
```bash
# 检查封面文件
ls -lh channels/kat/output/kat_20251201/kat_20251201_cover.png

# 使用 ImageMagick 或 PIL 验证尺寸（可选）
python3 << 'EOF'
from PIL import Image
img = Image.open("channels/kat/output/kat_20251201/kat_20251201_cover.png")
print(f"封面尺寸: {img.size} (期望: 3840×2160)")
print(f"格式: {img.format}")
EOF
```

**如果失败**：
- 检查 `images_pool/available/` 是否有可用图片
- 检查 Pillow 是否已安装：`pip install Pillow`
- 如果使用 Lora 字体，检查 `assets/fonts/Lora-Regular.ttf` 是否存在（否则会使用系统默认字体）

---

## 步骤 4：音频混音（MIX）

生成最终混音 MP3 和时间轴 CSV。

```bash
# 运行 MIX 阶段
python3 -m mcpos.cli.main run-stage kat kat_20251201 MIX
```

**预期输出**：
```
运行阶段 MIX for kat_20251201 (channel: kat)...
✅ 阶段 MIX 完成: kat_20251201
   耗时: 45.67 秒
   生成文件:
     ✅ kat_20251201_final_mix.mp3
     ✅ kat_20251201_full_mix_timeline.csv
```

**验证**：
```bash
# 检查生成的文件
ls -lh channels/kat/output/kat_20251201/*.mp3
ls -lh channels/kat/output/kat_20251201/*timeline.csv

# 使用 ffprobe 检查 MP3 属性（可选）
ffprobe -v error -show_format -show_streams channels/kat/output/kat_20251201/kat_20251201_final_mix.mp3 | grep -E "bit_rate|sample_rate|duration"
```

**如果失败**：
- 检查 ffmpeg 是否已安装：`which ffmpeg`
- 检查 `channels/kat/library/songs/` 中的曲目文件是否存在
- 查看错误信息，可能是某些曲目文件路径不匹配

---

## 步骤 5：生成字幕（TEXT_SRT）

生成 SRT 字幕文件。**注意**：此阶段依赖 MIX 阶段生成的 `full_mix_timeline.csv`。

```bash
# 运行 TEXT_SRT 阶段
python3 -m mcpos.cli.main run-stage kat kat_20251201 TEXT_SRT
```

**预期输出**：
```
运行阶段 TEXT_SRT for kat_20251201 (channel: kat)...
✅ 阶段 TEXT_SRT 完成: kat_20251201
   耗时: 0.12 秒
   生成文件:
     ✅ kat_20251201_youtube.srt
```

**验证**：
```bash
# 查看字幕文件（前几行）
head -20 channels/kat/output/kat_20251201/kat_20251201_youtube.srt
```

**如果失败**：
- 确保 MIX 阶段已成功完成
- 检查 `full_mix_timeline.csv` 是否存在且格式正确

---

## 步骤 6：视频渲染（RENDER）

生成最终视频文件。**注意**：此阶段依赖 COVER 和 MIX 阶段。

```bash
# 运行 RENDER 阶段
python3 -m mcpos.cli.main run-stage kat kat_20251201 RENDER
```

**预期输出**：
```
运行阶段 RENDER for kat_20251201 (channel: kat)...
✅ 阶段 RENDER 完成: kat_20251201
   耗时: 120.45 秒
   生成文件:
     ✅ kat_20251201_youtube.mp4
     ✅ kat_20251201_render_complete.flag
```

**验证**：
```bash
# 检查视频文件
ls -lh channels/kat/output/kat_20251201/kat_20251201_youtube.mp4

# 使用 ffprobe 验证视频属性（可选）
ffprobe -v error -show_format -show_streams channels/kat/output/kat_20251201/kat_20251201_youtube.mp4 | grep -E "width|height|bit_rate|duration"
```

**如果失败**：
- 确保 COVER 和 MIX 阶段已成功完成
- 检查 ffmpeg 是否已安装：`which ffmpeg`
- 检查磁盘空间是否充足（4K 视频文件可能很大）

---

## 一键运行所有阶段

如果你想一次性运行所有阶段（按依赖顺序），可以使用 `run-episode` 命令：

```bash
# 运行完整流程
python3 -m mcpos.cli.main run-episode kat kat_20251201
```

**注意**：此命令会按顺序执行所有阶段，但不会显示每个阶段的详细输出。建议在测试时使用 `run-stage` 命令逐个执行。

---

## 检查状态

使用 `check-status` 命令查看节目完成状态：

```bash
# 检查单个节目
python3 -m mcpos.cli.main check-status --channel-id kat --year 2025 --month 12
```

---

## 重置和重试

如果某个阶段失败，你可以：

1. **重置整个节目**（删除所有输出文件）：
   ```bash
   python3 -m mcpos.cli.main reset-episode kat kat_20251201 --confirm
   ```

2. **重置最后一期**（如果这是最新的一期）：
   ```bash
   python3 -m mcpos.cli.main reset-last-ep kat --confirm
   ```

3. **重新运行单个阶段**（幂等性保证，已存在的文件会被跳过）：
   ```bash
   python3 -m mcpos.cli.main run-stage kat kat_20251201 COVER
   ```

---

## 常见问题

### Q: TEXT_BASE 阶段失败，提示 "未收到 API key"
**A**: 设置 `OPENAI_API_KEY` 环境变量：
```bash
export OPENAI_API_KEY="sk-..."
```

### Q: COVER 阶段失败，提示 "No available images found"
**A**: 检查 `images_pool/available/` 目录是否有图片文件（支持 .png, .jpg, .jpeg）。

### Q: MIX 阶段失败，提示 "Track not found"
**A**: 检查 `playlist.csv` 中的曲目名称是否与 `channels/kat/library/songs/` 中的文件名匹配。可能需要更新 `tracklist.csv`。

### Q: RENDER 阶段很慢
**A**: 这是正常的，4K 视频渲染需要较长时间（通常 1-3 分钟，取决于音频长度）。

### Q: 如何查看详细的错误信息？
**A**: 查看终端输出，或检查 `mcpos/logs/` 目录（如果配置了日志）。

---

## 完整示例脚本

```bash
#!/bin/bash
# 生成 kat_20251201 的所有资产

CHANNEL="kat"
EPISODE="kat_20251201"

echo "=========================================="
echo "开始生成 $EPISODE 的所有资产"
echo "=========================================="

# 步骤 1: INIT
echo ""
echo "步骤 1: 初始化..."
python3 -m mcpos.cli.main init-episode $CHANNEL $EPISODE || exit 1

# 步骤 2: TEXT_BASE
echo ""
echo "步骤 2: 生成基础文本..."
python3 -m mcpos.cli.main run-stage $CHANNEL $EPISODE TEXT_BASE || exit 1

# 步骤 3: COVER
echo ""
echo "步骤 3: 生成封面..."
python3 -m mcpos.cli.main run-stage $CHANNEL $EPISODE COVER || exit 1

# 步骤 4: MIX
echo ""
echo "步骤 4: 音频混音..."
python3 -m mcpos.cli.main run-stage $CHANNEL $EPISODE MIX || exit 1

# 步骤 5: TEXT_SRT
echo ""
echo "步骤 5: 生成字幕..."
python3 -m mcpos.cli.main run-stage $CHANNEL $EPISODE TEXT_SRT || exit 1

# 步骤 6: RENDER
echo ""
echo "步骤 6: 视频渲染..."
python3 -m mcpos.cli.main run-stage $CHANNEL $EPISODE RENDER || exit 1

echo ""
echo "=========================================="
echo "✅ 所有资产生成完成！"
echo "=========================================="
echo ""
echo "生成的文件："
ls -lh channels/$CHANNEL/output/$EPISODE/
```

保存为 `generate_episode.sh`，然后运行：
```bash
chmod +x generate_episode.sh
./generate_episode.sh
```

---

## 下一步

生成完成后，你可以：
1. 检查所有生成的文件
2. 预览封面和视频
3. 上传到 YouTube（如果实现了 UPLOAD 阶段）

