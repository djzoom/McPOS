# 🎬 新手小白教程：从零开始生成YouTube视频

**适用对象**: 完全没有编程经验的新手  
**预计时间**: 30-60分钟（首次设置）  
**难度**: ⭐⭐☆☆☆（简单）

---

## 📋 目录

1. [第一步：准备工作](#第一步准备工作)
2. [第二步：配置API密钥](#第二步配置api密钥)
3. [第三步：生成你的第一个视频](#第三步生成你的第一个视频)
4. [第四步：查看生成的文件](#第四步查看生成的文件)
5. [第五步：批量生成多个视频](#第五步批量生成多个视频)
6. [常见问题](#常见问题)
7. [下一步：YouTube上传](#下一步youtube上传)

---

## 第一步：准备工作

### 1.1 确认你的系统

✅ **本教程适用于**: macOS 系统  
⚠️ **其他系统**: 需要修改部分命令，建议参考其他文档

### 1.2 打开终端（Terminal）

1. 按 `⌘ + 空格键`，输入"终端"或"Terminal"
2. 双击打开终端应用
3. 你会看到一个黑色（或白色）的窗口，这就是命令行界面

### 1.3 找到项目文件夹

在终端中输入以下命令（每行后按回车）：

```bash
# 进入项目目录（根据你的实际位置修改路径）
cd ~/Downloads/Kat_Rec

# 查看当前目录的内容
ls
```

你应该能看到类似这样的文件：
- `README.md`
- `Makefile`
- `scripts/` 文件夹
- `config/` 文件夹

### 1.4 初始化环境（自动安装依赖）

在终端输入：

```bash
make ensure-deps
```

**这会自动**：
- 安装Python虚拟环境
- 安装所有必需的软件包
- 可能需要几分钟时间，请耐心等待

**看到类似这样的提示就说明成功了**：
```
✅ 环境已就绪
```

---

## 第二步：配置API密钥

### 2.1 为什么需要API？

这个系统使用**OpenAI API**来自动生成：
- 📝 唱片标题（很有创意！）
- 📄 YouTube视频描述（SEO优化）
- 🏷️ YouTube标题

**没有API密钥，无法生成标题和描述！**

### 2.2 获取OpenAI API密钥

1. **访问OpenAI网站**: https://platform.openai.com/
2. **登录或注册账户**
3. **创建API密钥**:
   - 点击右上角头像 → "View API keys"
   - 点击 "Create new secret key"
   - **立即复制并保存**这个密钥（只显示一次！）
   - 格式类似：`sk-xxxxxxxxxxxxxxxxxxxxx`

### 2.3 配置API密钥

有两种方式，选择一种即可：

#### 方式A：使用配置向导（⭐推荐新手）

```bash
python scripts/local_picker/configure_api.py
```

按提示操作：
1. 选择 `1` （OpenAI）
2. 粘贴你的API密钥
3. 按回车确认

**看到"✅ 配置完成"就成功了！**

#### 方式B：手动配置

1. 创建配置文件：
   ```bash
   mkdir -p config
   ```

2. 编辑配置文件：
   ```bash
   # 方法1：使用nano编辑器（适合新手）
   nano config/api_config.json
   ```
   
   粘贴以下内容（替换`YOUR_API_KEY`）：
   ```json
   {
     "provider": "openai",
     "keys": {
       "openai": "sk-YOUR_API_KEY_HERE"
     }
   }
   ```
   
   按 `Ctrl + X`，然后按 `Y`，再按回车保存

### 2.4 验证配置

运行测试命令：

```bash
python scripts/local_picker/greet_garfield.py
```

**如果看到类似这样的输出，说明配置成功**：
```
✅ API验证成功，已准备就绪
```

如果看到错误，请检查：
- API密钥是否正确复制
- 是否有余额（访问 https://platform.openai.com/account/billing 检查）

---

## 第三步：生成你的第一个视频

### 3.1 最简单的方式：使用交互式终端（⭐强烈推荐新手）

```bash
make terminal
```

这会打开一个**美观的菜单界面**，所有功能一目了然：

```
╔══════════════════════════════════════════════════════════╗
║  🎵 KAT Records Studio 🎵                                 ║
╚══════════════════════════════════════════════════════════╝

主菜单
╭──────────┬───────────────────────────╮
│ 选项     │ 功能                      │
├──────────┼───────────────────────────┤
│ 1        │ 📋 排播表管理              │
│ 2        │ 🎬 视频生成                │
│ 3        │ 🔍 查看状态                │
│ 0        │ 退出                       │
╰──────────┴───────────────────────────╯
```

**操作步骤**：
1. 选择 `2`（视频生成）
2. 选择 `1`（生成单期）
3. 输入期数ID（格式：`YYYYMMDD`，例如：`20251101`）
4. 输入 `n`（不是测试模式）
5. 等待完成（可能需要10-20分钟）

### 3.2 另一种方式：使用工作流控制台（⭐推荐）

如果你想看到**每个步骤的进度**：

```bash
python scripts/workflow_console.py
```

这会显示一个**9阶段的可视化界面**：
```
[✓] Track Selection → [✓] Scheduling → [→] Image Extraction ...
```

你可以：
- 用上下箭头选择阶段
- 按 `ENTER` 查看详情
- 按 `R` 运行当前阶段
- 按 `A` 自动运行所有阶段

### 3.3 命令行方式（适合熟悉命令的用户）

如果你熟悉命令行，可以直接运行：

```bash
# 生成完整视频（包括封面、音频、视频、YouTube资源）
python scripts/local_picker/create_mixtape.py \
    --episode-id 20251101 \
    --font_name Lora-Regular
```

---

## 第四步：查看生成的文件

### 4.1 找到生成的文件

生成完成后，文件会保存在：

```bash
output/20251101_标题名称/
```

每个文件夹包含以下文件：

| 文件 | 说明 | 用途 |
|------|------|------|
| `20251101_cover.png` | 4K封面图片 | 用作视频缩略图 |
| `20251101_playlist.csv` | 歌单文件 | 记录所有曲目 |
| `20251101_full_mix.mp3` | 完整混音音频 | 视频的音频部分 |
| `20251101_youtube.mp4` | 最终视频文件 | **可以直接上传到YouTube！** |
| `20251101_youtube.srt` | 字幕文件 | YouTube字幕 |
| `20251101_youtube_title.txt` | YouTube标题 | 视频标题 |
| `20251101_youtube_description.txt` | YouTube描述 | 视频描述 |

### 4.2 查看文件内容

```bash
# 打开输出文件夹（macOS会自动打开Finder）
open output/

# 查看YouTube标题
cat output/20251101_标题名称/20251101_youtube_title.txt

# 查看YouTube描述
cat output/20251101_标题名称/20251101_youtube_description.txt
```

### 4.3 预览视频

```bash
# 在macOS上自动打开视频（使用默认播放器）
open output/20251101_标题名称/20251101_youtube.mp4
```

---

## 第五步：批量生成多个视频

### 5.1 创建排播表（规划多期节目）

在开始批量生成之前，先创建一个排播表：

```bash
# 使用交互式终端
make terminal
# 选择 1 → 1（创建/扩展排播表）

# 或直接命令行
make schedule EPISODES=10 START_DATE=2025-11-01 INTERVAL=2
```

这会创建一个10期的排播表，每2天一期，从2025年11月1日开始。

### 5.2 生成完整排播表的标题和曲目

```bash
python scripts/local_picker/generate_full_schedule.py \
    --format markdown \
    --update-schedule \
    --output output/schedule_2025_11.md
```

这会为每一期：
- 自动生成标题
- 自动选择曲目（避免重复）
- 更新排播表

### 5.3 批量生成所有视频

**重要提示**: 批量生成可能需要很长时间（每期10-20分钟），建议先测试1-2期。

```bash
# 生成10期完整内容
make 4kvideo N=10

# 或者使用DEMO模式（输出到output/DEMO/）
make 4kvideo N=5 DEMO=1
```

**生成过程中会显示进度**：
```
[1/10] 开始生成第 1 期...
✅ 第 1 期生成完成
[2/10] 开始生成第 2 期...
...
```

### 5.4 检查生成结果

```bash
# 使用交互式终端检查文件
make terminal
# 选择 3 → 3（快速检查文件）

# 或直接运行
python scripts/local_picker/check_episode_files.py
```

---

## 常见问题

### Q1: 提示"未找到API密钥"

**解决方法**:
1. 确认已完成[第二步：配置API密钥](#第二步配置api密钥)
2. 运行 `python scripts/local_picker/configure_api.py` 重新配置
3. 检查 `config/api_config.json` 文件是否存在且格式正确

### Q2: 生成视频时提示错误

**可能原因**:
- API密钥无效或余额不足
- 缺少必要的资源文件（图片、歌曲）
- 系统环境未正确初始化

**解决方法**:
1. 检查API状态：`python scripts/local_picker/greet_garfield.py`
2. 重新初始化环境：`make ensure-deps`
3. 查看错误信息，根据提示修复

### Q3: 视频生成很慢

**这是正常的！** 因为需要：
- 调用API生成标题和描述（需要网络）
- 生成4K封面图片（需要计算）
- 混音所有歌曲（需要音频处理）
- 合成视频（需要视频编码）

**预计时间**：每期10-20分钟

### Q4: 生成的视频在哪里？

所有文件都在 `output/` 目录下，按期数ID和标题组织：
```
output/
├── 20251101_标题名称/
│   ├── 20251101_youtube.mp4  ← 这就是你要上传的视频！
│   ├── 20251101_cover.png
│   ├── 20251101_youtube_title.txt
│   └── ...
└── 20251103_另一个标题/
    └── ...
```

### Q5: 如何修改生成的标题或描述？

可以手动编辑：
```bash
# 编辑标题
nano output/20251101_标题名称/20251101_youtube_title.txt

# 编辑描述
nano output/20251101_标题名称/20251101_youtube_description.txt
```

---

## 下一步：YouTube上传

### 📢 当前状态

⚠️ **重要提示**：YouTube自动上传功能目前**尚未实现**，只有技术方案文档。

但你可以：
1. ✅ 生成完整的视频文件
2. ✅ 生成YouTube标题和描述
3. ✅ 生成SRT字幕文件
4. ⏳ **手动上传到YouTube**（目前唯一方式）

### 🎯 手动上传步骤

1. **登录YouTube Studio**: https://studio.youtube.com/

2. **点击"上传视频"**

3. **选择文件**:
   - 找到 `output/你的期数_标题/你的期数_youtube.mp4`
   - 拖拽或选择文件

4. **填写信息**:
   - **标题**: 复制 `你的期数_youtube_title.txt` 的内容
   - **描述**: 复制 `你的期数_youtube_description.txt` 的内容
   - **缩略图**: 使用 `你的期数_cover.png`

5. **上传字幕**:
   - 在"字幕"选项卡中上传 `你的期数_youtube.srt`

6. **设置可见性**:
   - 选择 `不公开列出`（Unlisted）或 `公开`（Public）

7. **发布！**

### 🚀 未来：自动上传功能

一旦YouTube上传功能实现（根据 `docs/YouTube上传MVP方案.md`），你就可以：

```bash
# 自动上传单个视频
python scripts/local_picker/youtube_upload.py --video output/20251101_标题/20251101_youtube.mp4

# 批量上传所有待上传视频
python scripts/local_picker/batch_youtube_upload.py
```

**目前，请手动上传生成的视频文件。**

---

## 📚 更多帮助

- **遇到问题？** 查看 `docs/文档索引与阅读指南.md`
- **想深入了解？** 阅读 `docs/COMMAND_LINE_WORKFLOW.md`
- **使用工作流控制台？** 查看 `docs/工作流控制台使用指南.md`

---

## ✅ 完成清单

- [ ] 环境已初始化（`make ensure-deps`）
- [ ] API密钥已配置（`python scripts/local_picker/configure_api.py`）
- [ ] API已验证（`python scripts/local_picker/greet_garfield.py`）
- [ ] 已生成第一个视频
- [ ] 已查看生成的文件
- [ ] 已测试预览视频
- [ ] 已了解手动上传流程

**恭喜！你现在已经掌握了生成YouTube视频的基本流程！** 🎉

---

**最后更新**: 2025-11-01  
**维护者**: Kat Records 开发团队

