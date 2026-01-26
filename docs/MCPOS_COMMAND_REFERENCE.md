# McPOS 命令详解

## 概述

McPOS (Media Content Production Operating System) 是节目生产操作系统，提供命令行接口用于管理节目生产流程。

## 安装与使用

### 方法 1：使用临时脚本（推荐，无需安装）

```bash
# 确保虚拟环境已激活
source .venv311/bin/activate

# 直接运行脚本
python3 mcpos_cli.py <command> [options]
```

### 方法 2：使用 mcpos 命令（需要先安装）

```bash
# 确保虚拟环境已激活
source .venv311/bin/activate

# 安装项目（如果还没安装）
pip install -e .

# 使用 mcpos 命令
mcpos <command> [options]
```

## 命令列表

### 1. init-episode

**功能**：初始化单期节目，生成 `playlist.csv` 和 `recipe.json`。

**语法**：
```bash
mcpos init-episode <channel_id> <episode_id>
# 或
python3 mcpos_cli.py init-episode <channel_id> <episode_id>
```

**参数**：
- `channel_id`（必需）：频道 ID，如 `kat`、`rbr`
- `episode_id`（必需）：节目 ID，如 `kat_20241201`

**示例**：
```bash
mcpos init-episode kat kat_20241201
mcpos init-episode rbr rbr_20241215
```

**说明**：
- 此命令会执行 INIT 阶段，生成节目的基础文件
- 生成的 `playlist.csv` 包含曲目列表
- 生成的 `recipe.json` 包含节目配置信息
- 输出目录：`channels/<channel_id>/output/<episode_id>/`

---

### 2. run-episode

**功能**：处理单期节目的完整流程，按顺序执行所有阶段。

**语法**：
```bash
mcpos run-episode <channel_id> <episode_id>
# 或
python3 mcpos_cli.py run-episode <channel_id> <episode_id>
```

**参数**：
- `channel_id`（必需）：频道 ID，如 `kat`、`rbr`
- `episode_id`（必需）：节目 ID，如 `kat_20241201`

**示例**：
```bash
mcpos run-episode kat kat_20241201
```

**执行流程**：
1. **INIT** - 初始化（如果尚未完成）
2. **TEXT_BASE** - 生成文本资产（标题、描述、标签）
3. **COVER** - 生成封面图像
4. **MIX** - 音频混音
5. **TEXT_SRT** - 生成字幕文件
6. **RENDER** - 视频渲染

**说明**：
- 如果某个阶段已完成，会自动跳过
- 如果某个阶段失败，会显示错误信息
- 完成后会显示所有阶段的完成状态

---

### 3. run-day

**功能**：处理某一天的所有节目。

**语法**：
```bash
mcpos run-day <channel_id> <date>
# 或
python3 mcpos_cli.py run-day <channel_id> <date>
```

**参数**：
- `channel_id`（必需）：频道 ID
- `date`（必需）：日期，格式 `YYYYMMDD`，如 `20241201`

**示例**：
```bash
mcpos run-day kat 20241201
mcpos run-day rbr 20241215
```

**说明**：
- 会自动查找该日期下的所有节目
- 按顺序处理每个节目
- 显示完成统计：`完成 X/Y 期`

---

### 4. run-month

**功能**：处理某个月的所有节目。

**语法**：
```bash
mcpos run-month <channel_id> <year> <month>
# 或
python3 mcpos_cli.py run-month <channel_id> <year> <month>
```

**参数**：
- `channel_id`（必需）：频道 ID
- `year`（必需）：年份，如 `2024`
- `month`（必需）：月份，范围 1-12

**示例**：
```bash
mcpos run-month kat 2024 12
mcpos run-month rbr 2024 11
```

**说明**：
- 会自动查找该月份下的所有节目
- 按顺序处理每个节目
- 显示完成统计：`完成 X/Y 期` 和 `失败 X 期`

---

### 5. check-status

**功能**：检查节目完成状态，显示各阶段的完成率。

**语法**：
```bash
mcpos check-status [--channel-id CHANNEL_ID] [--year YEAR] [--month MONTH]
# 或
python3 mcpos_cli.py check-status [--channel-id CHANNEL_ID] [--year YEAR] [--month MONTH]
```

**参数**：
- `--channel-id`（可选）：频道 ID，如不指定则使用默认值
- `--year`（可选）：年份
- `--month`（可选）：月份（1-12）

**示例**：
```bash
# 检查指定月份
mcpos check-status --channel-id kat --year 2024 --month 12

# 检查所有节目（如果支持）
mcpos check-status --channel-id kat
```

**输出示例**：
```
2024年12月完成情况:
  INIT: 100.0%
  TEXT_BASE: 95.0%
  COVER: 90.0%
  MIX: 85.0%
  TEXT_SRT: 80.0%
  RENDER: 75.0%
```

**说明**：
- 显示各阶段的完成百分比
- 可用于监控批量生成进度

---

### 6. reset-episode

**功能**：重置期数，删除所有输出文件，恢复图、曲使用状态。

**语法**：
```bash
mcpos reset-episode <channel_id> <episode_id> [--confirm]
# 或
python3 mcpos_cli.py reset-episode <channel_id> <episode_id> [--confirm]
```

**参数**：
- `channel_id`（必需）：频道 ID
- `episode_id`（必需）：节目 ID
- `--confirm` 或 `-y`（可选）：确认删除，跳过提示

**示例**：
```bash
# 交互式确认
mcpos reset-episode kat kat_20241201

# 自动确认（跳过提示）
mcpos reset-episode kat kat_20241201 --confirm
```

**说明**：
- ⚠️ **警告**：此操作会删除该期数的所有输出文件
- 恢复图片使用状态（从 used 移回 available）
- 不会将图、曲移至 used（因为 reset 意味着取消，不是真正使用）
- 只有检查上传排播后，才会记录使用情况并移动图到 used

**输出示例**：
```
重置 kat_20241201 (channel: kat)...
✅ 重置完成: kat_20241201
   删除文件数: 15
   已恢复图片到 available
```

---

## 查看帮助

### 查看主帮助

```bash
mcpos --help
# 或
python3 mcpos_cli.py --help
```

### 查看特定命令的帮助

```bash
mcpos init-episode --help
mcpos run-episode --help
mcpos run-day --help
mcpos run-month --help
mcpos check-status --help
mcpos reset-episode --help
```

---

## 工作流程示例

### 示例 1：生成单期节目

```bash
# 1. 初始化节目
mcpos init-episode kat kat_20241201

# 2. 运行完整流程
mcpos run-episode kat kat_20241201
```

### 示例 2：批量生成12月所有节目

```bash
# 一次性生成12月所有节目
mcpos run-month kat 2024 12

# 检查完成状态
mcpos check-status --channel-id kat --year 2024 --month 12
```

### 示例 3：生成某一天的节目

```bash
# 生成12月1日的节目
mcpos run-day kat 20241201
```

### 示例 4：重置失败的节目

```bash
# 重置并重新生成
mcpos reset-episode kat kat_20241201 --confirm
mcpos run-episode kat kat_20241201
```

---

## 故障排除

### 问题 1：`ModuleNotFoundError: No module named 'typer'`

**解决方案**：
```bash
# 确保虚拟环境已激活
source .venv311/bin/activate

# 安装 typer
pip install typer
```

### 问题 2：`mcpos: command not found`

**解决方案**：
- **方法 1**：使用临时脚本
  ```bash
  python3 mcpos_cli.py <command>
  ```

- **方法 2**：安装项目
  ```bash
  pip install -e .
  # 安装后可能需要重新加载 shell
  ```

### 问题 3：找不到虚拟环境

**解决方案**：
```bash
# 检查虚拟环境是否存在
ls -la .venv311/bin/activate

# 如果不存在，创建新的虚拟环境
python3 -m venv .venv311
source .venv311/bin/activate
pip install typer
pip install -e .
```

### 问题 4：命令执行失败

**检查步骤**：
1. 确认虚拟环境已激活
2. 确认依赖已安装：`pip list | grep typer`
3. 查看详细错误信息
4. 检查输出目录权限
5. 检查配置文件是否正确

---

## 文件结构

执行命令后，会在以下目录生成文件：

```
channels/<channel_id>/output/<episode_id>/
├── playlist.csv              # 曲目列表（INIT 阶段）
├── recipe.json               # 节目配置（INIT 阶段）
├── <episode_id>_youtube_title.txt        # 标题（TEXT_BASE 阶段）
├── <episode_id>_youtube_description.txt   # 描述（TEXT_BASE 阶段）
├── <episode_id>_youtube_tags.txt          # 标签（TEXT_BASE 阶段）
├── <episode_id>_cover.png                 # 封面（COVER 阶段）
├── <episode_id>_full_mix.mp3              # 完整混音（MIX 阶段）
├── <episode_id>_final_mix.mp3              # 最终混音（MIX 阶段）
├── <episode_id>_full_mix_timeline.csv     # 时间轴（MIX 阶段）
├── <episode_id>_youtube.srt               # 字幕（TEXT_SRT 阶段）
├── <episode_id>_youtube.mp4               # 视频（RENDER 阶段）
└── <episode_id>_render_complete.flag      # 渲染完成标志（RENDER 阶段）
```

---

## 注意事项

1. **依赖顺序**：各阶段有依赖关系，建议使用 `run-episode` 自动处理依赖
2. **文件检查**：如果某个阶段的文件已存在，会自动跳过该阶段
3. **错误处理**：如果某个阶段失败，会显示错误信息，但不会自动重试
4. **资源使用**：批量生成时注意系统资源（CPU、内存、磁盘空间）
5. **日志记录**：执行过程中的日志会记录在 `mcpos/logs/` 目录

---

## 相关文档

- `mcpos/README_CLI.md` - CLI 快速开始指南
- `mcpos/Doc/ASSET_CONTRACT.md` - 资产文件契约
- `mcpos/Doc/ASSET_DEPENDENCY_FLOW.md` - 资产依赖流程
- `mcpos/Dev_Bible.md` - 开发规范






