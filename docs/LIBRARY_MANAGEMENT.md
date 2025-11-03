# 歌库与曲库管理指南

## 📚 概念区分

### 1. **歌库（Song Library）**
**定义**：物理音频文件的存储目录和对应的索引数据库

**位置**：
- **物理文件**：由配置文件 `config/library_settings.yml` 中的 `song_library_root` 指定
- **索引文件**：`data/song_library.csv` 和 `data/schedule_master.json动态查询（已弃用独立文件）`

**特点**：
- 包含实际音频文件（.mp3, .wav, .flac等）
- 自动检测音频时长（使用 `mutagen` 库）
- 追踪使用历史（何时添加、最后使用时间、使用次数）
- 支持监听模式（自动检测新增文件）

### 2. **曲库（Tracklist）**
**定义**：用于生成专辑的歌曲列表数据文件

**位置**：
- **默认**：`data/song_library.csv`（由歌库生成的索引）
- **备选**：`data/google_sheet/*.tsv`（Google Sheets 导出的数据）

**特点**：
- CSV/TSV 格式
- 必需字段：`title`（或 `name`）、`duration_seconds`（或 `duration`）
- 用于选曲生成专辑
- 不包含文件路径，只有元数据

## 🔄 工作流程

```
歌库物理文件目录
    ↓
[generate_song_library.py]
    ↓
data/song_library.csv  ← 歌库索引（包含文件路径、使用历史）
    ↓
[create_mixtape.py]
    ↓
选曲 → 生成专辑
```

## 📁 文件结构

```
项目根目录/
├── config/
│   └── library_settings.yml      # 歌库配置
├── data/
│   ├── song_library.csv          # 歌库索引（可被选为曲库）
│   ├── schedule_master.json动态查询（已弃用独立文件）            # 使用历史记录（与song_library.csv同步）
│   └── google_sheet/
│       └── *.tsv                  # Google Sheets 导出的曲库备选
└── [song_library_root]/          # 实际音频文件目录（由配置指定）
    ├── song1.mp3
    ├── song2.wav
    └── ...
```

## 🛠️ 歌库管理

### 配置文件：`config/library_settings.yml`

```yaml
# 歌库根目录（物理音频文件位置）
song_library_root: "/path/to/audio/files"

# 音频文件扩展名
audio_extensions:
  - ".mp3"
  - ".wav"
  - ".flac"
  - ".m4a"
  - ".aac"

# 使用记录文件
usage_log: "data/schedule_master.json动态查询（已弃用独立文件）"

# 输出目录索引文件
output_catalog: "data/song_library.csv"
```

### 生成/更新歌库索引

**单次生成**：
```bash
python scripts/local_picker/generate_song_library.py
```

**监听模式**（自动检测新增文件）：
```bash
python scripts/local_picker/generate_song_library.py --watch
```

**输出**：
- `data/song_library.csv` - 完整索引
- `data/schedule_master.json动态查询（已弃用独立文件）` - 使用历史（与索引同步）

### 歌库索引字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `file_path` | 音频文件完整路径 | `/path/to/song.mp3` |
| `file_name` | 文件名 | `song.mp3` |
| `title` | 曲目标题（从文件名提取） | `song` |
| `duration_seconds` | 时长（秒） | `180.5` |
| `added_at` | 添加时间（ISO格式） | `2025-11-01T10:30:00+08:00` |
| `last_used_at` | 最后使用时间 | `2025-11-01T15:20:00+08:00` |
| `times_used` | 使用次数 | `3` |

### 使用历史追踪

- **保留历史**：如果文件已存在记录，保留 `added_at`、`last_used_at`、`times_used`
- **自动更新**：生成专辑时更新使用历史（通过排播表系统）
- **新文件检测**：新添加的文件使用文件修改时间作为 `added_at`

## 📊 曲库管理

### 曲库文件格式

**CSV/TSV 格式**，必需字段：

| 字段名 | 说明 | 示例 |
|--------|------|------|
| `title` 或 `name` | 曲目标题 | `Midnight Dreams` |
| `duration_seconds` 或 `duration` | 时长（秒或 "mm:ss" 格式） | `180` 或 `3:00` |

**示例 CSV**：
```csv
title,duration_seconds
Midnight Dreams,180
Sunset Vibes,240
```

**示例 TSV**：
```tsv
Title	Duration
Midnight Dreams	3:00
Sunset Vibes	4:00
```

### 曲库来源

#### 1. 从歌库索引（推荐）
```bash
# 默认使用 data/song_library.csv
python scripts/local_picker/create_mixtape.py --font_name Lora-Regular
```

#### 2. 从 Google Sheets 导出
```bash
# 自动查找 data/google_sheet/*.tsv
python scripts/local_picker/create_mixtape.py --font_name Lora-Regular
```

#### 3. 指定自定义曲库
```bash
python scripts/local_picker/create_mixtape.py \
  --tracklist /path/to/custom.csv \
  --font_name Lora-Regular
```

## 🔗 与排播表的集成

### 歌曲使用追踪

排播表（`config/schedule_master.json`）记录：
- **每期使用的歌曲列表**（`tracks_used`）
- **起始曲目**（`starting_track`）

### 新歌识别

系统通过比较：
- **曲库中的所有歌曲** vs **排播表中已使用的歌曲**

识别：
- **新歌**：未在排播表中使用过的歌曲
- **旧歌**：已在排播表中使用过的歌曲

### 选曲策略

1. **优先新歌**（70%）
2. **穿插旧歌**（30%）
3. **避免临近期数重复**（排除最近5期）
4. **确保起始曲目独特**

## 🔄 完整工作流程示例

### 步骤1：配置歌库
```bash
# 编辑配置文件
vim config/library_settings.yml
# 设置 song_library_root 指向音频文件目录
```

### 步骤2：生成歌库索引
```bash
# 扫描音频文件，生成索引
python scripts/local_picker/generate_song_library.py
# 输出：data/song_library.csv
```

### 步骤3：使用监听模式（可选）
```bash
# 监听文件变更，自动更新索引
python scripts/local_picker/generate_song_library.py --watch
```

### 步骤4：创建排播表
```bash
# 创建永恒排播表（一次性）
python scripts/local_picker/create_schedule_master.py --episodes 100
```

### 步骤5：生成专辑
```bash
# 自动使用 data/song_library.csv 作为曲库
make 4kvideo N=10
```

**系统会自动**：
1. 从曲库选曲（优先新歌，穿插旧歌）
2. 更新排播表（记录使用的歌曲）
3. 更新使用历史（用于下次识别新歌）

## 📈 数据流向图

```
┌─────────────────┐
│ 音频文件目录    │ (物理文件)
│ song_library_   │
│ root/           │
└────────┬────────┘
         │
         │ [generate_song_library.py]
         │ 扫描、检测时长、提取标题
         ▼
┌─────────────────┐
│ song_library.csv│ (歌库索引)
│ schedule_master.json动态查询（已弃用独立文件）  │ (使用历史)
└────────┬────────┘
         │
         │ [create_mixtape.py]
         │ 读取作为曲库
         ▼
┌─────────────────┐
│   选曲生成      │
│   专辑         │
└────────┬────────┘
         │
         │ 记录使用
         ▼
┌─────────────────┐
│ schedule_master. │ (排播表)
│ json            │
│ - tracks_used   │
│ - starting_track │
└─────────────────┘
         │
         │ 用于下次识别新歌
         ▼
    [循环]
```

## ⚙️ 高级功能

### 监听模式

自动检测歌库目录变更：
```bash
python scripts/local_picker/generate_song_library.py --watch
```

**特点**：
- 实时监听文件系统变更
- 自动更新索引
- 保留已有记录的使用历史
- 新文件自动添加

### 使用历史保留

- 即使删除后重新添加，历史记录会保留
- 基于文件完整路径（`file_path`）匹配
- 保留：`added_at`、`last_used_at`、`times_used`

### 时长自动检测

使用 `mutagen` 库检测音频文件时长：
- 支持 MP3、WAV、FLAC、M4A、AAC 等格式
- 自动读取文件元数据
- 如果检测失败，时长字段为空

## 🔍 常见问题

### Q: 歌库和曲库有什么区别？

**A**: 
- **歌库**：物理音频文件 + 索引数据库（包含文件路径和使用历史）
- **曲库**：仅包含元数据（标题、时长）的 CSV/TSV 文件，用于选曲

### Q: 如何添加新歌？

**A**: 
1. 将音频文件放入歌库目录（`song_library_root`）
2. 运行 `generate_song_library.py` 更新索引
3. 或使用监听模式自动检测

### Q: 如何确保新歌被优先使用？

**A**: 
- 系统自动识别新歌（未在排播表中使用过的）
- 默认 70% 新歌，30% 旧歌
- 优先选择新歌作为起始曲目

### Q: 曲库文件格式要求？

**A**: 
- CSV 或 TSV 格式
- 必需字段：`title`（或 `name`）、`duration_seconds`（或 `duration`）
- 时长可以是秒数（整数）或 "mm:ss" 格式

### Q: 如何查看歌库规模？

**A**: 
```bash
# 查看索引文件
wc -l data/song_library.csv
# 或查看排播表中的统计
python -c "from scripts.local_picker.schedule_master import ScheduleMaster; m=ScheduleMaster.load(); print(f'已使用：{len(m.get_all_used_tracks())} 首')"
```

## 📝 最佳实践

1. **定期更新歌库索引**
   - 每次添加新文件后运行 `generate_song_library.py`
   - 或使用监听模式持续更新

2. **保持曲库同步**
   - 使用 `data/song_library.csv` 作为曲库（推荐）
   - 确保索引文件是最新的

3. **备份使用历史**
   - `data/schedule_master.json动态查询（已弃用独立文件）` 包含重要使用历史
   - 定期备份，避免丢失

4. **使用排播表追踪**
   - 通过排播表系统追踪歌曲使用
   - 自动识别新歌和旧歌

