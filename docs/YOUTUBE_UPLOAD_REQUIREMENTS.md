# YouTube API 上传功能需求文档

## 📋 我需要的信息和文档

为了实现批量生成视频和 YouTube API 上传功能，我需要以下信息和文档：

---

## 1. YouTube API 配置信息

### 必需的配置项

1. **Google Cloud Project 信息**
   - 是否有 Google Cloud Project？
   - Project ID 是什么？
   - 是否已启用 YouTube Data API v3？

2. **OAuth 2.0 凭证**
   - 是否已有 OAuth 2.0 Client ID 和 Client Secret？
   - 凭证文件位置（通常是 `client_secrets.json`）
   - 或者是否希望我创建获取凭证的指引？

3. **认证方式偏好**
   - **选项A：OAuth 2.0（用户授权）** - 每次上传需要浏览器授权，适合个人使用
   - **选项B：Service Account（服务账号）** - 无需交互，适合自动化（但 YouTube API 通常不支持）
   - **选项C：API Key（仅用于读取）** - 不支持上传
   - **推荐：OAuth 2.0 + Token 缓存** - 首次授权后保存 token，后续自动使用

4. **Token 存储位置**
   - 希望将 OAuth token 保存在哪里？
   - 推荐：`config/google/youtube_token.json`（已在 .gitignore 中）

---

## 2. 批量生成需求

### 功能需求

1. **批量生成命令**
   ```bash
   make 4kvideo N=10
   ```
   - 生成 10 期完整内容（封面+歌单+混音+视频+YouTube资源）
   - 是否需要并行生成，还是串行？
   - 是否需要在生成过程中显示进度？

2. **输出目录结构**
   - 现在使用统一目录结构：`output/{YYYY-MM-DD}_{标题}/`
   - 批量生成时，每期都有独立文件夹 ✅（已实现）
   - **注意**: DEMO模式已移除，所有输出使用统一目录结构

3. **错误处理**
   - 如果某期生成失败，是否继续生成其他期？
   - 是否需要生成报告总结成功/失败数量？

4. **资源限制**
   - 是否有 API 调用频率限制需要控制？
   - OpenAI API（用于生成标题/描述）的速率限制？
   - YouTube API 的配额限制？

---

## 3. YouTube 上传配置

### 上传参数

1. **视频可见性**
   - 默认设置为：
     - `private`（私有，仅自己可见）
     - `unlisted`（不公开列出，但有链接可看）
     - `public`（公开，所有人可见）
   - 是否有定时发布需求？

2. **视频分类和标签**
   - 默认分类（Category ID）：
     - `10` = Music（推荐）
     - 其他偏好？
   - 是否自动添加标签（tags）？
     - 从描述中提取 hashtag？
     - 固定标签列表？

3. **缩略图**
   - 是否使用封面图作为视频缩略图？
   - 是否需要自动生成或上传自定义缩略图？

4. **字幕**
   - 是否自动上传 SRT 字幕文件？
   - 字幕语言设置？

5. **其他元数据**
   - 是否设置默认的许可类型？
   - 是否添加默认的年龄限制？
   - 是否包含归属信息？

---

## 4. 上传流程设计

### 流程选项

**选项A：生成后立即上传**
```
生成视频 → 生成YouTube资源 → 立即上传到YouTube
```

**选项B：生成后批量上传**
```
生成所有视频 → 收集所有上传信息 → 批量上传（可暂停/重试）
```

**选项C：生成后手动确认上传**
```
生成所有视频 → 生成上传清单 → 用户确认后批量上传
```

**推荐：选项B（批量上传）**
- 生成完所有视频后再上传
- 支持暂停、重试、跳过失败项
- 生成上传报告

---

## 5. 上传状态管理

### 需要跟踪的信息

1. **上传状态**
   - 已上传 / 上传失败 / 待上传 / 跳过
   - 是否需要保存上传状态到文件？（如 `output/batch_upload_status.json`）

2. **YouTube 视频信息**
   - Video ID
   - YouTube URL
   - 上传时间
   - 是否需要记录到 CSV 或数据库？

3. **错误日志**
   - 上传失败的原因
   - 是否需要详细的错误日志？

---

## 6. API 依赖和安装

### Python 库需求

需要安装以下库：
```python
google-api-python-client      # YouTube Data API v3 客户端
google-auth-httplib2         # OAuth 2.0 HTTP 支持
google-auth-oauthlib         # OAuth 2.0 流
```

这些需要添加到 `requirements.txt` 吗？

---

## 7. 用户交互流程

### OAuth 授权流程

首次使用时：
1. 运行上传命令
2. 自动打开浏览器进行 Google 授权
3. 用户授权后，token 保存到本地
4. 后续使用自动读取 token（除非过期）

**问题：**
- 是否接受这种方式？
- 是否需要更详细的授权指引文档？

---

## 8. 批量生成的具体需求

### 当前实现

已有 `batch_generate_covers.sh`，但仅生成封面（`--no-remix`）。

### 需要实现

`make 4kvideo N=10` 应该：
1. ✅ 生成 10 期完整内容（封面+歌单+混音+视频）
2. ✅ 每期在独立的 `output/{ID}_{标题}/` 目录
3. ✅ 生成 YouTube 资源（SRT、标题、描述）
4. ✅ 串行生成（避免资源竞争）
5. ❓ 显示总体进度（1/10, 2/10...）
6. ❓ 生成完成后自动批量上传？

**问题：**
- 批量生成时是否需要并行？（不建议，可能造成资源竞争）
- 是否需要在生成过程中显示详细进度？
- 生成完成后是否自动触发上传？

---

## 📝 请提供的信息

### 必需信息

1. **YouTube API 凭证状态**
   - [ ] 已有 Google Cloud Project？
   - [ ] 已启用 YouTube Data API v3？
   - [ ] 已有 OAuth 2.0 凭证？
   - [ ] 如果没有，是否需要我提供获取凭证的步骤？

2. **上传偏好**
   - 默认视频可见性：`private` / `unlisted` / `public`？
   - 是否需要支持上传时选择？

3. **批量生成流程**
   - 生成后立即上传，还是批量完成后统一上传？
   - 是否需要上传状态追踪和报告？

### 可选信息

1. **高级配置**
   - 自定义视频分类（Category ID）
   - 默认标签列表
   - 缩略图处理方式

2. **错误处理策略**
   - 生成失败：继续 / 停止？
   - 上传失败：重试次数？重试间隔？

---

## 🚀 实施方案预览

基于以上信息，我将实现：

### 1. 批量生成脚本

**文件：** `scripts/local_picker/batch_generate_videos.py`

**功能：**
- 接受 `N` 参数，生成 N 期完整内容
- 串行生成，避免资源竞争
- 显示进度：`[1/10] 生成中...`
- 错误处理：记录失败项，继续生成
- 生成完成后输出报告

### 2. YouTube 上传模块

**文件：** `scripts/local_picker/youtube_upload.py`

**功能：**
- OAuth 2.0 认证（首次需浏览器授权）
- Token 缓存管理（自动刷新）
- 视频上传（支持大文件分块上传）
- 自动上传字幕（SRT）
- 上传缩略图（封面图）
- 错误处理和重试机制

### 3. 批量上传脚本

**文件：** `scripts/local_picker/batch_youtube_upload.py`

**功能：**
- 扫描 `output/` 目录，找到所有待上传视频
- 读取 `*_youtube_upload.csv` 获取元数据
- 批量上传，显示进度
- 生成上传报告（成功/失败列表）

### 4. Makefile 更新

添加命令：
```makefile
4kvideo: ensure-deps
    # 批量生成 N 期视频
    # 可选：自动触发批量上传
```

---

## 📚 参考文档

### YouTube Data API v3 官方文档
- https://developers.google.com/youtube/v3/docs
- https://developers.google.com/youtube/v3/guides/uploading_a_video

### Python 客户端库
- https://github.com/googleapis/google-api-python-client

---

## ⚠️ 注意事项

1. **API 配额限制**
   - YouTube Data API v3 每日配额：通常 10,000 units/天
   - 上传一个视频：~1600 units
   - 每日约可上传 6 个视频（免费配额）
   - 如需更多，需要申请配额增加

2. **文件大小限制**
   - 单次上传限制：256GB
   - 视频时长限制：无（但超过12小时需要特殊处理）

3. **安全性**
   - OAuth token 需妥善保管
   - 不应提交到 git
   - 已在 `.gitignore` 中包含 `config/google/*.json`

---

**请提供上述信息，我将开始实现批量生成和 YouTube 上传功能！** 🚀

