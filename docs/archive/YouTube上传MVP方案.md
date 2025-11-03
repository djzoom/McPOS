# YouTube上传功能MVP方案

**版本**: v1.0  
**日期**: 2025-11-01  
**状态**: 待用户确认

---

## 1. 技术调研总结

### YouTube Data API v3 核心信息

#### API配额限制
- **默认配额**: 10,000 units/天（免费账户）
- **上传视频消耗**: ~1,600 units/视频
- **每日上传能力**: 约6个视频（免费配额）
- **配额恢复**: 每日UTC 00:00重置
- **配额提升**: 可在Google Cloud Console申请

#### OAuth 2.0认证流程
- **必需**: Google Cloud Project + OAuth 2.0 Client ID/Secret
- **授权范围**: `https://www.googleapis.com/auth/youtube.upload`
- **Token类型**: Access Token + Refresh Token
- **Token有效期**: Access Token 1小时，Refresh Token长期有效
- **刷新机制**: 使用Refresh Token自动获取新的Access Token

#### 视频上传方式
- **标准上传**: 适用于<256MB的视频
- **分块上传**: 适用于大文件，支持断点续传
- **必需参数**: 标题、描述、可见性（privacyStatus）
- **可选参数**: 标签、分类ID、缩略图、字幕

---

## 2. 技术方案设计

### 2.1 OAuth 2.0认证流程

#### 凭证配置
**文件位置**: `config/google/client_secrets.json`
```json
{
  "installed": {
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"]
  }
}
```

#### Token存储
**文件位置**: `config/google/youtube_token.json`
```json
{
  "token": "ACCESS_TOKEN",
  "refresh_token": "REFRESH_TOKEN",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "CLIENT_ID",
  "client_secret": "CLIENT_SECRET",
  "scopes": ["https://www.googleapis.com/auth/youtube.upload"],
  "expiry": "2025-11-01T12:00:00Z"
}
```

#### 首次授权流程
1. 检查 `config/google/youtube_token.json` 是否存在
2. 如果不存在，打开浏览器引导用户授权
3. 用户授权后，获取并保存Token
4. 后续使用自动加载Token

#### Token刷新机制
1. 检查Token是否过期（expiry字段）
2. 如果过期，使用Refresh Token获取新Token
3. 更新保存的Token文件
4. 如果Refresh Token也失效，提示用户重新授权

---

### 2.2 视频上传流程

#### 单视频上传流程
```
1. 读取视频文件（output/{ID}_{Title}/{ID}_youtube.mp4）
2. 读取元数据：
   - 标题：{ID}_youtube_title.txt
   - 描述：{ID}_youtube_description.txt
   - 封面：{ID}_cover.png（可选，作为缩略图）
   - 字幕：{ID}_youtube.srt（可选）
3. 构建上传请求：
   - 视频文件
   - 元数据（标题、描述、标签、分类ID）
   - 可见性设置（默认：unlisted）
4. 执行上传（支持大文件分块上传）
5. 获取Video ID
6. 上传字幕（如果存在SRT文件）
7. 上传缩略图（如果存在封面）
8. 保存上传结果（Video ID、URL）
```

#### 批量上传策略
- **串行上传**: 避免API配额冲突，易于错误处理
- **进度跟踪**: 实时显示上传进度（1/10, 2/10...）
- **失败重试**: 失败后自动重试（最多3次）
- **配额检查**: 每次上传前检查剩余配额
- **限流控制**: 如果接近配额限制，暂停并提示

---

### 2.3 错误处理方案

#### 错误类型和处理
1. **认证错误**
   - Token过期 → 自动刷新
   - Refresh Token失效 → 提示重新授权
   - 凭证文件不存在 → 引导用户配置

2. **上传错误**
   - 网络错误 → 重试（最多3次）
   - 文件格式错误 → 跳过并记录
   - 配额超限 → 暂停并生成报告
   - API错误 → 记录详细错误信息

3. **元数据错误**
   - 标题/描述缺失 → 使用默认值或跳过
   - 文件不存在 → 标记为失败并继续

#### 重试机制
- **重试次数**: 最多3次
- **重试间隔**: 指数退避（1s, 2s, 4s）
- **重试条件**: 网络错误、临时API错误
- **不重试**: 认证错误、格式错误、配额超限

---

### 2.4 配额管理策略

#### 配额检查
- **上传前检查**: 确保有足够配额（至少1,600 units）
- **配额跟踪**: 实时跟踪已使用配额
- **配额预警**: 当剩余配额<3,000 units时发出警告
- **配额耗尽**: 自动停止上传，生成报告

#### 配额优化
- **批量上传**: 一次性处理多个视频，减少API调用
- **元数据合并**: 上传视频时同时设置所有元数据（单次API调用）
- **跳过重复**: 检查视频是否已上传（避免重复消耗配额）

---

## 3. 文件结构设计

### 3.1 新增文件

```
scripts/local_picker/
├── youtube_upload.py          # 核心上传模块
├── youtube_auth.py            # OAuth认证模块
└── batch_youtube_upload.py    # 批量上传脚本

config/google/
├── client_secrets.json        # OAuth凭证（用户配置）
└── youtube_token.json         # Token缓存（自动生成）

output/
└── upload_logs/
    ├── upload_2025-11-01.json    # 上传日志
    └── upload_report_2025-11-01.txt  # 上传报告
```

### 3.2 配置文件

**config/youtube_settings.yml** (可选):
```yaml
default_privacy: "unlisted"  # private, unlisted, public
default_category_id: 10      # Music
default_tags:
  - "lofi"
  - "kat records"
  - "vibe coding"
auto_upload_subtitles: true
auto_upload_thumbnail: true
```

---

## 4. 实现细节

### 4.1 依赖库

需要在 `requirements.txt` 中添加：
```
google-api-python-client>=2.100.0
google-auth-httplib2>=0.1.1
google-auth-oauthlib>=1.1.0
```

### 4.2 核心函数设计

#### `youtube_auth.py`
```python
def get_authenticated_service() -> googleapiclient.discovery.Resource
def authorize() -> None  # 首次授权
def refresh_token_if_needed() -> None  # 自动刷新
```

#### `youtube_upload.py`
```python
def upload_video(
    video_path: Path,
    title: str,
    description: str,
    privacy_status: str = "unlisted",
    tags: List[str] = None,
    category_id: int = 10,
    thumbnail_path: Path = None,
    subtitle_path: Path = None
) -> Dict[str, str]  # 返回 {video_id, video_url}

def upload_subtitle(video_id: str, srt_path: Path, language: str = "zh-CN") -> None
def upload_thumbnail(video_id: str, thumbnail_path: Path) -> None
```

#### `batch_youtube_upload.py`
```python
def scan_episodes_for_upload(output_dir: Path) -> List[Dict]
def batch_upload(episodes: List[Dict], max_retries: int = 3) -> Dict
def generate_upload_report(results: Dict) -> str
```

---

## 5. 用户流程

### 5.1 首次使用
1. 运行 `python scripts/local_picker/youtube_upload.py --setup`
2. 系统提示配置OAuth凭证
3. 打开浏览器进行授权
4. Token保存到本地
5. 配置完成，可以开始上传

### 5.2 日常上传
1. 生成视频和YouTube资源
2. 运行 `python scripts/local_picker/batch_youtube_upload.py --episodes output/`
3. 系统自动：
   - 扫描待上传视频
   - 检查Token有效性（自动刷新）
   - 批量上传
   - 生成上传报告

### 5.3 与工作流集成
- 在工作流控制台中添加"上传"阶段
- 自动检测视频是否已上传
- 支持一键上传所有待上传视频

---

## 6. 风险评估

### 高风险项
1. **API配额限制**: 每日最多6个视频，可能无法满足批量需求
   - **缓解**: 实现配额检查和预警，支持分批上传

2. **OAuth Token安全**: Token泄露可能导致账户安全问题
   - **缓解**: Token文件权限600，已在.gitignore中

3. **网络稳定性**: 上传大文件可能因网络问题失败
   - **缓解**: 实现分块上传和断点续传

### 中风险项
1. **Token刷新失败**: Refresh Token可能失效
   - **缓解**: 友好的重新授权提示

2. **文件格式兼容性**: YouTube对视频格式有要求
   - **缓解**: 验证文件格式，提供转换建议

---

## 7. 时间估算

- **Week 1**: OAuth认证流程（3-4天）
  - OAuth授权流程实现
  - Token存储和刷新机制
  - 配置向导
  
- **Week 2**: 视频上传功能（5天）
  - 单视频上传实现
  - 元数据设置
  - 字幕和缩略图上传
  - 错误处理
  
- **Week 3**: 批量上传和优化（3-4天）
  - 批量上传脚本
  - 配额管理
  - 进度跟踪和报告
  - 测试和文档

**总计**: 约3周完成MVP

---

## 8. 验收标准

- ✅ 能够成功上传单个视频到YouTube
- ✅ 自动设置标题、描述、标签（从生成的文件读取）
- ✅ 支持批量上传，带进度显示
- ✅ OAuth token自动刷新，无需重复授权
- ✅ 错误处理完善，有重试机制
- ✅ 配额检查和管理
- ✅ 上传日志和报告

---

## 9. 后续优化（超出MVP范围）

- 定时发布功能
- 视频分析和统计
- 多账户支持
- 上传队列管理
- Webhook通知

---

**请确认此方案是否符合需求，确认后开始实施。**

