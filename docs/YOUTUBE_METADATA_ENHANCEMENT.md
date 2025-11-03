# YouTube Metadata Enhancement

**日期**: 2025-11-02  
**状态**: ✅ 已完成

---

## 🎯 概述

增强了 YouTube 上传功能，实现了完整的元数据构建器，支持所有标准和可选的 YouTube Data API v3 字段。

---

## ✨ 新增功能

### 1. **完整的元数据构建器**

新增 `build_youtube_metadata()` 函数，构建包含以下字段的完整元数据：

#### 必需字段 (snippet)
- `title`: 视频标题（从 `*_youtube_title.txt` 加载）
- `description`: 视频描述（从 `*_youtube_description.txt` 加载）
- `tags`: 标签列表（从 `config.yaml` 读取）
- `categoryId`: 分类ID（默认 10 = Music）
- `defaultLanguage`: 默认语言（默认 "en"）

#### 状态字段 (status)
- `privacyStatus`: 隐私设置（private/unlisted/public）
- `license`: 许可类型（默认 "creativeCommon"）
- `embeddable`: 是否可嵌入（默认 true）
- `publicStatsViewable`: 统计是否公开（默认 true）
- `selfDeclaredMadeForKids`: 是否为儿童内容（默认 false）
- `publishAt`: 计划发布时间（可选，需 `--schedule` 参数）

#### 录制详情 (recordingDetails)
- `recordingDate`: 录制日期（从 episode_id 自动派生，ISO 8601 格式）

#### 本地化内容 (snippet.localized)
- `title`: 本地化标题（当前与基础标题相同，为 i18n 扩展准备）
- `description`: 本地化描述（当前与基础描述相同）

#### 主题分类 (topicDetails)
- `topicCategories`: 主题分类列表
  - `https://en.wikipedia.org/wiki/Music`
  - `https://en.wikipedia.org/wiki/Lo-fi_music`

---

### 2. **智能日期解析**

新增 `parse_episode_date()` 函数：
- 从 episode_id (YYYYMMDD 格式) 自动解析日期
- 转换为 UTC 时区的 datetime 对象
- 用于自动填充 `recordingDate` 和 `publishAt`

**示例**:
```python
episode_id = "20251104"
date = parse_episode_date(episode_id)  # 返回 2025-11-04 00:00:00+00:00
```

---

### 3. **缩略图自动调整**

新增 `resize_thumbnail_if_needed()` 函数：
- 自动检测缩略图文件大小（默认限制 2MB）
- 自动检测图片尺寸（默认最大宽度 1280px）
- 超出限制时自动调整并优化
- 保持宽高比，使用高质量重采样算法
- 临时文件自动清理

**处理逻辑**:
1. 检查文件大小 > 2MB → 需要调整
2. 检查宽度 > 1280px → 需要调整
3. 使用 LANCZOS 重采样算法调整尺寸
4. 优化压缩（质量 85% → 70% 如果仍过大）

---

### 4. **计划发布功能**

新增 `--schedule` CLI 参数：
- 启用时，自动设置 `publishAt` 为 episode 日期 + 9:00 AM
- 使用 ISO 8601 / RFC 3339 格式
- 适用于提前上传但延迟发布场景

**使用示例**:
```bash
# 立即上传并发布
.venv/bin/python3 scripts/kat_cli.py upload --episode 20251104

# 上传但计划在期数日期的 9:00 AM 发布
.venv/bin/python3 scripts/kat_cli.py upload --episode 20251104 --schedule
```

---

## 📋 数据源映射

| 字段 | 数据源 | 规则 |
|------|--------|------|
| `snippet.title` | `output/{episode_id}_youtube_title.txt` | 自动检测文件 |
| `snippet.description` | `output/{episode_id}_youtube_description.txt` | 自动检测文件 |
| `snippet.tags` | `config.yaml → youtube.upload_defaults.tags` | 默认值：["lofi", "music", "Kat Records", "chill"] |
| `snippet.categoryId` | `config.yaml → youtube.upload_defaults.categoryId` | 默认值：10 (Music) |
| `snippet.defaultLanguage` | 固定值 | 默认 "en"，可扩展为 "zh" |
| `status.privacyStatus` | CLI 参数 `--privacy` 或配置 | 默认 "unlisted" |
| `recordingDetails.recordingDate` | 从 `episode_id` 派生 | YYYYMMDD → ISO 8601 |
| `status.publishAt` | 从 `episode_id` 派生 + `--schedule` | 期数日期 9:00 AM UTC |
| `topicDetails.topicCategories` | 静态列表 | Music + Lo-fi music |
| `thumbnails` | `output/{episode_id}_cover.png` | 自动检测，>2MB 自动调整 |

---

## 🔧 函数说明

### `build_youtube_metadata()`

**签名**:
```python
def build_youtube_metadata(
    episode_id: str,
    title: str,
    description: str,
    privacy: str = "unlisted",
    tags: Optional[List[str]] = None,
    category_id: int = 10,
    schedule: bool = False,
    default_language: str = "en"
) -> Dict
```

**功能**:
- 构建完整的 YouTube API v3 元数据 JSON
- 自动从 episode_id 派生日期信息
- 支持计划发布（schedule=True）
- 包含所有标准和可选字段
- 向后兼容（可选字段缺失时仍可成功上传）

**返回示例**:
```json
{
  "snippet": {
    "title": "20251104 | Lo-Fi Rainy Jazz",
    "description": "Gentle lofi jazz beats...",
    "tags": ["lofi", "music", "Kat Records"],
    "categoryId": "10",
    "defaultLanguage": "en",
    "localized": {
      "title": "20251104 | Lo-Fi Rainy Jazz",
      "description": "Gentle lofi jazz beats..."
    }
  },
  "status": {
    "privacyStatus": "unlisted",
    "license": "creativeCommon",
    "embeddable": true,
    "publicStatsViewable": true,
    "selfDeclaredMadeForKids": false,
    "publishAt": "2025-11-04T09:00:00.000Z"
  },
  "recordingDetails": {
    "recordingDate": "2025-11-04T00:00:00.000Z"
  },
  "topicDetails": {
    "topicCategories": [
      "https://en.wikipedia.org/wiki/Music",
      "https://en.wikipedia.org/wiki/Lo-fi_music"
    ]
  }
}
```

---

### `parse_episode_date()`

**签名**:
```python
def parse_episode_date(episode_id: str) -> Optional[datetime]
```

**功能**:
- 从 episode_id (YYYYMMDD) 解析日期
- 返回 UTC 时区的 datetime 对象
- 解析失败返回 None

---

### `resize_thumbnail_if_needed()`

**签名**:
```python
def resize_thumbnail_if_needed(
    thumbnail_path: Path,
    max_size_mb: float = 2.0,
    max_width: int = 1280
) -> Path
```

**功能**:
- 检查缩略图文件大小和尺寸
- 超出限制时自动调整
- 保持宽高比
- 优化文件大小
- 返回调整后的路径（可能是临时文件）

---

## 📝 使用示例

### 基本上传

```bash
.venv/bin/python3 scripts/kat_cli.py upload --episode 20251104 --privacy unlisted
```

### 计划发布

```bash
.venv/bin/python3 scripts/kat_cli.py upload --episode 20251104 --schedule --privacy public
```

### 使用完整选项

```bash
.venv/bin/python3 scripts/kat_cli.py upload \
  --episode 20251104 \
  --video output/20251104_youtube.mp4 \
  --title-file output/2025-11-04_Title/20251104_youtube_title.txt \
  --desc-file output/2025-11-04_Title/20251104_youtube_description.txt \
  --privacy unlisted \
  --schedule
```

---

## 🔍 验证和日志

### 元数据验证

上传前会自动记录元数据结构到日志：
- 记录包含的字段部分（snippet, status, recordingDetails, topicDetails）
- 验证 JSON 结构完整性
- 错误时提供详细诊断信息

### 日志输出

```json
{
  "event": "upload",
  "episode": "20251104",
  "status": "started",
  "metadata_keys": ["snippet", "status", "recordingDetails", "topicDetails"]
}
```

---

## 🚀 SEO 优化

通过完整填充元数据字段，实现了：

1. **更好的搜索排名**:
   - 完整的标签和主题分类
   - 准确的录制日期
   - 本地化内容支持（为多语言扩展准备）

2. **更专业的内容**:
   - Creative Commons 许可标识
   - 准确的录制信息
   - 完整的主题分类

3. **更好的可发现性**:
   - 公开统计信息
   - 可嵌入内容
   - 正确的年龄分级

---

## 📚 技术细节

### API Part 参数

动态构建 `part` 参数，只包含有数据的部分：
```python
parts = ['snippet', 'status']
if 'recordingDetails' in body:
    parts.append('recordingDetails')
if 'topicDetails' in body:
    parts.append('topicDetails')
```

### 时区处理

- 所有日期使用 UTC 时区
- `publishAt` 设置为期数日期的 9:00 AM UTC
- 可扩展为支持本地时区转换

### 向后兼容

- 所有可选字段缺失时不影响上传
- 旧代码继续正常工作
- 逐步迁移到新元数据格式

---

## 📖 相关文档

- [YouTube Upload Guide](./YOUTUBE_UPLOAD_GUIDE.md) - 完整使用指南
- [Quick Start Guide](./QUICK_START_YOUTUBE.md) - 快速开始
- [Architecture](./ARCHITECTURE.md) - 系统架构

---

## ✅ 完成状态

- [x] 实现 `build_youtube_metadata()` 函数
- [x] 实现 `parse_episode_date()` 函数
- [x] 实现 `resize_thumbnail_if_needed()` 函数
- [x] 添加 `--schedule` CLI 参数
- [x] 更新 `upload_video()` 使用新构建器
- [x] 更新 CLI 命令传递参数
- [x] 添加元数据验证和日志
- [x] 测试所有功能

---

**最后更新**: 2025-11-02  
**版本**: 1.0.0

