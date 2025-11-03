# YouTube Upload 测试指南

**日期**: 2025-11-02  
**状态**: 准备测试

---

## 🔧 环境准备

### 1. 安装依赖

确保在虚拟环境中安装 Google API 依赖：

```bash
cd /Users/z/Downloads/Kat_Rec
.venv/bin/pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

验证安装：

```bash
.venv/bin/python3 -c "import google.auth; print('✅ 依赖已安装')"
```

### 2. 配置 OAuth 凭证

#### 步骤 A: 创建 Google Cloud 项目

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目或选择现有项目

#### 步骤 B: 启用 YouTube Data API v3

1. 转到 "APIs & Services" → "Library"
2. 搜索 "YouTube Data API v3"
3. 点击 "启用"

#### 步骤 C: 创建 OAuth 2.0 凭证

1. 转到 "APIs & Services" → "Credentials"
2. 如果首次创建，需要先配置 OAuth 同意屏幕：
   - 用户类型：外部
   - 应用名称：Kat Records Uploader
   - 支持邮箱：您的邮箱
   - 点击"保存并继续"，完成其余步骤
3. 点击 "Create Credentials" → "OAuth 2.0 Client ID"
4. 应用类型：选择 "Desktop app"
5. 名称：Kat Records Uploader
6. 点击 "Create"
7. 点击 "Download JSON" 下载凭证文件

#### 步骤 D: 放置凭证文件

```bash
# 将下载的 JSON 文件移动到项目目录
mv ~/Downloads/client_secret_*.json \
   /Users/z/Downloads/Kat_Rec/config/google/client_secrets.json
```

### 3. 验证配置

运行设置向导：

```bash
.venv/bin/python3 scripts/setup_youtube_oauth.py
```

---

## 🧪 测试步骤

### 测试 1: 基础环境检查

```bash
.venv/bin/python3 scripts/test_youtube_upload.py
```

预期结果：
- ✅ 依赖导入成功
- ✅ 配置加载成功
- ⚠️  认证状态：需要首次授权（正常）
- ✅ 文件检测成功
- ✅ 排播表检查成功

### 测试 2: 文件准备检查

检查是否有可用的视频文件：

```bash
# 查找视频文件
find output -name "*_youtube.mp4" -type f

# 检查期数 20251102 的文件
ls -la output/2025-11-02_*/20251102_* 2>/dev/null
```

### 测试 3: 首次授权（Dry Run）

**注意**: 这一步会打开浏览器进行 OAuth 授权

```bash
# 使用一个小的测试文件或准备测试视频
.venv/bin/python3 scripts/uploader/upload_to_youtube.py \
  --episode 20251102 \
  --video output/20251102_youtube.mp4 \
  --privacy unlisted  # 使用 unlisted 进行测试
```

首次运行时：
1. 会检测到未授权
2. 自动打开浏览器进行 OAuth 授权
3. 选择 Google 账号并授权
4. 授权成功后，Token 会保存到 `config/google/youtube_token.json`
5. 然后开始上传流程

### 测试 4: 验证上传结果

上传成功后检查：

```bash
# 检查上传结果 JSON
cat output/*/20251102_youtube_upload.json

# 检查 schedule_master.json 是否更新
grep -A 5 "20251102" config/schedule_master.json | grep youtube

# 检查日志
tail -20 logs/katrec.log | grep upload
```

---

## 📋 测试检查清单

- [ ] 依赖已安装（`pip list | grep google`）
- [ ] OAuth 凭证文件存在（`config/google/client_secrets.json`）
- [ ] 视频文件存在（`output/*_youtube.mp4`）
- [ ] 元数据文件存在（`*_youtube_title.txt`, `*_youtube_description.txt`）
- [ ] 首次授权完成（`config/google/youtube_token.json` 存在）
- [ ] 上传成功（`*_youtube_upload.json` 生成）
- [ ] 状态更新（`schedule_master.json` 中有 `youtube_video_id`）
- [ ] 日志记录（`logs/katrec.log` 中有上传记录）

---

## 🚨 常见问题

### 问题 1: "ModuleNotFoundError: No module named 'google'"

**解决方案**:
```bash
# 确保在虚拟环境中
cd /Users/z/Downloads/Kat_Rec
source .venv/bin/activate  # 如果使用 bash/zsh
# 或直接使用完整路径
.venv/bin/pip install --force-reinstall google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 问题 2: "OAuth credentials file not found"

**解决方案**:
- 运行 `python3 scripts/setup_youtube_oauth.py` 查看详细说明
- 确保 `config/google/client_secrets.json` 文件存在
- 检查文件权限：`chmod 600 config/google/client_secrets.json`

### 问题 3: "API quota exceeded"

**解决方案**:
- YouTube Data API 每日配额：10,000 单位
- 上传一个视频消耗约 200 单位
- 如果配额用完，需要等待 24 小时或申请增加配额

### 问题 4: "Video file not found"

**解决方案**:
- 先运行 Stage 9 (视频渲染) 生成视频
- 检查视频文件路径是否正确
- 可以使用 `--video` 参数明确指定路径

---

## 📊 测试结果验证

### 成功指标

1. **上传成功**:
   ```json
   {
     "event": "upload",
     "episode": "20251102",
     "status": "completed",
     "video_id": "abc123xyz",
     "latency": 42.5
   }
   ```

2. **状态更新**:
   ```json
   {
     "episode_id": "20251102",
     "youtube_video_id": "abc123xyz",
     "youtube_video_url": "https://www.youtube.com/watch?v=abc123xyz",
     "youtube_uploaded_at": "2025-11-02T20:30:00"
   }
   ```

3. **结果文件**:
   - `output/{episode_dir}/20251102_youtube_upload.json` 已生成

4. **YouTube 验证**:
   - 在 [YouTube Studio](https://studio.youtube.com/) 中可以看到上传的视频
   - 视频状态与配置的隐私设置一致（unlisted/private/public）

---

## 🔗 相关文档

- [YouTube Upload Guide](./YOUTUBE_UPLOAD_GUIDE.md) - 完整使用指南
- [Architecture](./ARCHITECTURE.md) - 系统架构
- [Roadmap](./ROADMAP.md) - 开发路线图

---

**测试准备完成时间**: 2025-11-02  
**下一步**: 配置 OAuth 凭证后即可开始实际测试

