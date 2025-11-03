# YouTube 自动上传 - 快速开始

**最后更新**: 2025-11-02

---

## 🚀 5分钟快速开始

### 步骤 1: 配置 OAuth 凭证（仅首次需要）

#### 1.1 创建 Google Cloud 项目

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目（或选择现有项目）

#### 1.2 启用 YouTube Data API v3

1. 转到 **APIs & Services** → **Library**
2. 搜索 **"YouTube Data API v3"**
3. 点击 **"启用"**

#### 1.3 创建 OAuth 2.0 凭证

1. 转到 **APIs & Services** → **Credentials**
2. 首次创建需要配置 **OAuth 同意屏幕**：
   - 用户类型：**外部**
   - 应用名称：`Kat Records Uploader`
   - 支持邮箱：您的邮箱
   - 保存并继续完成其余步骤
3. 点击 **"Create Credentials"** → **"OAuth 2.0 Client ID"**
4. 应用类型：选择 **"Desktop app"**
5. 名称：`Kat Records Uploader`
6. 点击 **"Create"**
7. **下载 JSON 文件**

#### 1.4 放置凭证文件

将下载的 JSON 文件移动到项目目录：

```bash
# 找到下载的文件（通常在 Downloads 目录）
mv ~/Downloads/client_secret_*.json \
   /Users/z/Downloads/Kat_Rec/config/google/client_secrets.json
```

或运行设置向导查看详细说明：

```bash
python3 scripts/setup_youtube_oauth.py
```

---

### 步骤 2: 运行上传

#### 方式 1: 使用 CLI 命令（推荐）

```bash
# 在虚拟环境中
.venv/bin/python3 scripts/kat_cli.py upload --episode 20251102

# 如果需要指定隐私设置
.venv/bin/python3 scripts/kat_cli.py upload --episode 20251102 --privacy unlisted
```

#### 方式 2: 直接调用脚本

```bash
.venv/bin/python3 scripts/uploader/upload_to_youtube.py \
  --episode 20251102 \
  --video output/20251102_youtube.mp4
```

**首次运行时会自动触发 OAuth 授权**：
1. 自动打开浏览器
2. 选择 Google 账号
3. 授权应用访问 YouTube
4. Token 自动保存（无需再次授权）

---

### 步骤 3: 验证上传结果

#### 检查上传状态

```bash
# 查看上传结果 JSON
cat output/*/20251102_youtube_upload.json

# 检查排播表是否更新
grep -A 5 "20251102" config/schedule_master.json | grep youtube

# 查看日志
tail -5 logs/katrec.log | grep upload
```

#### 在 YouTube Studio 验证

访问 [YouTube Studio](https://studio.youtube.com/) 查看上传的视频

---

## 📋 常用命令

### 基本上传

```bash
# 上传指定期数（自动检测文件）
.venv/bin/python3 scripts/kat_cli.py upload --episode 20251102
```

### 带选项的上传

```bash
# 指定隐私设置
.venv/bin/python3 scripts/kat_cli.py upload --episode 20251102 --privacy public

# 强制重新上传（即使已上传）
.venv/bin/python3 scripts/kat_cli.py upload --episode 20251102 --force

# 指定文件路径
.venv/bin/python3 scripts/kat_cli.py upload \
  --episode 20251102 \
  --video output/20251102_youtube.mp4 \
  --title-file output/2025-11-02_Title/20251102_youtube_title.txt \
  --desc-file output/2025-11-02_Title/20251102_youtube_description.txt
```

---

## 🔧 测试环境

### 运行测试脚本

```bash
.venv/bin/python3 scripts/test_youtube_upload.py
```

这会检查：
- ✅ 依赖是否安装
- ✅ 配置是否正确
- ✅ OAuth 凭证是否存在
- ✅ 视频文件是否可用
- ✅ 元数据文件是否完整

---

## ⚙️ 配置说明

编辑 `config/config.yaml`（如果不存在，复制 `config/config.example.yaml`）：

```yaml
youtube:
  client_secrets_file: "config/google/client_secrets.json"
  token_file: "config/google/youtube_token.json"
  upload_defaults:
    privacyStatus: "unlisted"  # private, unlisted, public
    categoryId: 10  # Music
    tags:
      - "lofi"
      - "music"
      - "Kat Records"
      - "chill"
```

---

## ❓ 常见问题

### Q: 首次运行提示 "OAuth credentials file not found"

**A**: 需要先配置 OAuth 凭证：
1. 运行 `python3 scripts/setup_youtube_oauth.py` 查看详细说明
2. 按照步骤创建并下载凭证文件
3. 将文件放置到 `config/google/client_secrets.json`

### Q: 上传失败，提示 "API quota exceeded"

**A**: YouTube API 每日配额有限（默认 10,000 单位）：
- 上传一个视频消耗约 200 单位
- 如果配额用完，需要等待 24 小时或申请增加配额

### Q: 视频文件或元数据文件找不到

**A**: 
- 确保已运行 Stage 9 (视频渲染) 生成视频
- 元数据文件应在最终文件夹中（`output/YYYY-MM-DD_Title/`）
- 可以使用 `--title-file` 和 `--desc-file` 明确指定路径

### Q: 上传成功但 schedule_master.json 没有更新

**A**: 
- 检查状态管理器是否正常工作
- 查看日志文件了解详细错误：`logs/katrec.log`
- 即使状态更新失败，上传结果 JSON 文件仍会生成

---

## 📖 更多文档

- [完整使用指南](./YOUTUBE_UPLOAD_GUIDE.md) - 详细功能说明
- [测试指南](./TEST_UPLOAD_GUIDE.md) - 测试步骤和问题排查
- [系统架构](./ARCHITECTURE.md) - 技术架构说明

---

## 🎯 下一步

1. ✅ 配置 OAuth 凭证
2. ✅ 运行首次上传测试
3. ✅ 验证上传结果
4. 🚀 开始自动化批量上传！

