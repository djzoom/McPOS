# YouTube上传模块完整复盘报告

## 📋 执行摘要

本报告全面梳理了Kat_Rec工作区中所有与YouTube上传相关的模块、方法和脚本，并分析了它们的用途、调用关系和推荐使用场景。

**关键发现**：
- 工作区共有 **6个主要上传模块** 和 **10+个上传相关脚本**
- 所有模块最终都调用 `scripts/uploader/upload_to_youtube.py` 作为核心上传引擎
- 视频已成功上传到正确的账号（频道ID: UCeeAiCtRL3Ti1cH1p64pYpw），状态为 `private`，排播时间已设置

---

## 🔍 一、核心上传模块（6个）

### 1. **scripts/uploader/upload_to_youtube.py** ⭐⭐⭐⭐⭐
**推荐度：最高（核心引擎）**

**代码规模**：1295行

**功能特点**：
- ✅ **功能最完整**：支持所有YouTube上传功能
- ✅ **可恢复上传**：支持大文件分块上传，断点续传
- ✅ **完整的错误处理**：指数退避重试机制，区分临时/永久错误
- ✅ **配额感知**：自动检测和限流，防止API配额耗尽
- ✅ **状态管理集成**：与`src/core/state_manager`集成
- ✅ **结构化日志**：JSON格式日志记录
- ✅ **定时发布**：支持`schedule`参数，自动计算发布时间
- ✅ **完整元数据支持**：标题、描述、标签、字幕、缩略图、播放列表
- ✅ **智能元数据读取**：自动查找期数目录，支持多种目录结构
- ✅ **缩略图自动调整**：自动调整大小（最大1280x720，2MB）
- ✅ **OAuth自动刷新**：自动处理token过期和刷新

**核心函数**：
- `upload_video()` - 主上传函数
- `get_authenticated_service()` - 认证服务
- `read_metadata_files()` - 元数据读取
- `build_youtube_metadata()` - 元数据构建
- `resumable_upload()` - 可恢复上传（通过upload_helpers）

**使用场景**：
- ✅ 生产环境的主要上传工具
- ✅ 被其他所有模块调用（直接导入或subprocess）

**被引用情况**：
- `mcpos/adapters/uploader.py` - 通过subprocess调用
- `scripts/upload_episodes_direct.py` - 直接导入使用
- `scripts/upload_episodes_27_30.py` - 通过subprocess调用
- `kat_rec_web/backend/t2r/routes/upload.py` - 导入函数
- `kat_rec_web/backend/t2r/services/upload_queue.py` - 导入函数

---

### 2. **mcpos/adapters/uploader.py** ⭐⭐⭐⭐⭐
**推荐度：最高（McPOS标准接口）**

**代码规模**：721行

**功能特点**：
- ✅ **McPOS边界模块**：符合McPOS架构设计
- ✅ **通过subprocess调用**：调用`upload_to_youtube.py`，保持边界清晰
- ✅ **严格的资产检查**：必需文件缺失时hard fail
- ✅ **适配McPOS数据模型**：使用`EpisodeSpec`、`AssetPaths`、`McPOSConfig`
- ✅ **上传和验证分离**：`upload_episode_video()`和`verify_episode_upload()`
- ✅ **符合No Unreasonable Fallback**：必需文件缺失时失败，不使用默认值

**核心函数**：
- `upload_episode_video()` - 上传边界函数
- `verify_episode_upload()` - 验证边界函数
- `_build_upload_params()` - 构建上传参数
- `_ensure_video_asset_ok()` - 视频资产检查

**使用场景**：
- ✅ McPOS pipeline的标准上传接口
- ✅ 自动化工作流
- ✅ 符合McPOS架构规范

**被引用情况**：
- `mcpos/cli/main.py` - CLI命令使用
- `mcpos/core/pipeline.py` - Pipeline集成（未来）

**调用链**：
```
mcpos/adapters/uploader.py
  └─> subprocess调用
      └─> scripts/uploader/upload_to_youtube.py
```

---

### 3. **kat_rec_web/backend/t2r/services/upload_queue.py** ⭐⭐⭐⭐
**推荐度：高（Web后端队列服务）**

**代码规模**：550行

**功能特点**：
- ✅ **串行上传队列**：确保同一时间只有一个上传任务
- ✅ **防止重复上传**：跟踪已上传的episode
- ✅ **异步任务管理**：使用asyncio队列
- ✅ **状态跟踪**：跟踪上传状态（queued, uploading, uploaded, failed）
- ✅ **重试机制**：支持任务重试
- ✅ **恢复扫描**：启动时自动扫描并恢复未完成的上传

**核心类/函数**：
- `UploadQueue` - 上传队列管理器
- `UploadTask` - 上传任务数据类
- `enqueue_upload()` - 入队上传任务
- `_worker()` - 工作线程处理上传

**使用场景**：
- ✅ Web后端的上传队列服务
- ✅ 通过API触发上传
- ✅ 批量上传管理

**被引用情况**：
- `kat_rec_web/backend/t2r/routes/upload.py` - API路由使用
- `scripts/trigger_upload.py` - 命令行触发使用

**调用链**：
```
kat_rec_web/backend/t2r/services/upload_queue.py
  └─> 调用 _execute_upload_task()
      └─> 导入 upload_to_youtube.py 的函数
          └─> scripts/uploader/upload_to_youtube.py
```

---

### 4. **kat_rec_web/backend/t2r/routes/upload.py** ⭐⭐⭐
**推荐度：中等（Web API接口）**

**功能特点**：
- ✅ FastAPI路由接口
- ✅ 上传启动、状态查询、验证接口
- ✅ 批量上传支持
- ⚠️ 部分功能为TODO（未完全实现）

**核心接口**：
- `POST /upload/start` - 启动上传
- `GET /upload/status` - 查询上传状态
- `POST /upload/verify` - 验证上传结果
- `POST /upload/batch-start` - 批量上传

**使用场景**：
- ✅ Web前端调用
- ✅ API集成

**调用链**：
```
kat_rec_web/backend/t2r/routes/upload.py
  └─> 调用 upload_queue.enqueue_upload()
      └─> kat_rec_web/backend/t2r/services/upload_queue.py
          └─> 导入 upload_to_youtube.py
              └─> scripts/uploader/upload_to_youtube.py
```

---

### 5. **scripts/uploader/upload_helpers.py** ⭐⭐⭐⭐
**推荐度：高（辅助工具）**

**功能特点**：
- ✅ **可恢复上传实现**：分块上传逻辑
- ✅ **上传进度跟踪**：实时反馈上传进度
- ✅ **错误恢复**：断点续传支持

**核心函数**：
- `resumable_upload()` - 可恢复上传实现
- `get_upload_progress()` - 获取上传进度

**使用场景**：
- ✅ 被`upload_to_youtube.py`调用
- ✅ 大文件上传的核心逻辑

**被引用情况**：
- `scripts/uploader/upload_to_youtube.py` - 直接导入使用

---

### 6. **scripts/uploader/token_manager.py** ⭐⭐⭐
**推荐度：中等（OAuth管理）**

**功能特点**：
- ✅ OAuth token管理
- ✅ Token刷新逻辑
- ✅ 认证状态检查

**使用场景**：
- ✅ 被`upload_to_youtube.py`调用
- ✅ OAuth认证管理

---

## 📜 二、上传脚本（10+个）

### 1. **scripts/upload_episodes_direct.py**
**用途**：直接上传多个期数视频

**特点**：
- 直接导入`upload_to_youtube.py`的函数
- 支持批量上传
- 命令行工具

**调用链**：
```
scripts/upload_episodes_direct.py
  └─> 导入 upload_to_youtube.py
      └─> scripts/uploader/upload_to_youtube.py
```

---

### 2. **scripts/upload_episodes_27_30.py**
**用途**：批量上传27-30期视频

**特点**：
- 通过subprocess调用`upload_to_youtube.py`
- 硬编码期数列表
- 默认语言为English

**调用链**：
```
scripts/upload_episodes_27_30.py
  └─> subprocess调用
      └─> scripts/uploader/upload_to_youtube.py
```

---

### 3. **scripts/trigger_upload.py**
**用途**：触发上传任务到队列

**特点**：
- 使用`upload_queue.py`的队列服务
- 支持批量触发
- 检查文件存在性

**调用链**：
```
scripts/trigger_upload.py
  └─> upload_queue.enqueue_upload()
      └─> kat_rec_web/backend/t2r/services/upload_queue.py
          └─> 导入 upload_to_youtube.py
              └─> scripts/uploader/upload_to_youtube.py
```

---

### 4. **scripts/test_youtube_upload.py**
**用途**：测试YouTube上传功能

**特点**：
- 测试脚本
- 验证上传流程

---

### 5. **scripts/setup_youtube_oauth.py**
**用途**：设置YouTube OAuth认证

**特点**：
- OAuth初始化
- Token生成

---

### 6. **scripts/reauthorize_youtube_with_captions.py**
**用途**：重新授权YouTube（带字幕权限）

**特点**：
- OAuth重新授权
- 扩展权限范围

---

### 7. **scripts/refresh_youtube_token.py**
**用途**：刷新YouTube token

**特点**：
- Token刷新
- 认证维护

---

### 8. **scripts/diagnose_youtube_oauth.py**
**用途**：诊断YouTube OAuth问题

**特点**：
- 诊断工具
- 问题排查

---

### 9. **scripts/delete_youtube_video.py**
**用途**：删除YouTube视频

**特点**：
- 视频删除
- 清理工具

---

### 10. **scripts/check_youtube_api.py**
**用途**：检查YouTube API状态

**特点**：
- API状态检查
- 连接测试

---

## 🔗 三、调用关系图

```
┌─────────────────────────────────────────────────────────────┐
│                    YouTube Data API v3                      │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │
                            │
        ┌───────────────────┴───────────────────┐
        │                                         │
        │                                         │
┌───────▼────────────┐              ┌────────────▼──────────┐
│ upload_to_youtube  │              │   upload_helpers.py   │
│      .py           │◄─────────────│  (可恢复上传实现)     │
│  (核心上传引擎)     │              └──────────────────────┘
└───────┬────────────┘
        │
        │ 被以下模块调用：
        │
        ├─► mcpos/adapters/uploader.py (subprocess)
        │
        ├─► scripts/upload_episodes_direct.py (直接导入)
        │
        ├─► scripts/upload_episodes_27_30.py (subprocess)
        │
        ├─► kat_rec_web/backend/t2r/routes/upload.py (导入函数)
        │   └─► kat_rec_web/backend/t2r/services/upload_queue.py
        │       └─► scripts/trigger_upload.py
        │
        └─► 其他测试/诊断脚本
```

---

## 📊 四、使用统计

### 代码规模对比

| 模块 | 代码行数 | 复杂度 | 推荐度 |
|------|---------|--------|--------|
| `upload_to_youtube.py` | 1295行 | 高 | ⭐⭐⭐⭐⭐ |
| `uploader.py` (McPOS) | 721行 | 中 | ⭐⭐⭐⭐⭐ |
| `upload_queue.py` | 550行 | 中 | ⭐⭐⭐⭐ |
| `upload_helpers.py` | ~300行 | 中 | ⭐⭐⭐⭐ |
| `routes/upload.py` | 693行 | 中 | ⭐⭐⭐ |

### 被引用次数（基于代码分析）

| 模块 | 被引用次数 | 主要使用者 |
|------|-----------|-----------|
| `upload_to_youtube.py` | **最多（6+）** | 所有上传模块的底层引擎 |
| `uploader.py` (McPOS) | 中等（2） | McPOS CLI、Pipeline |
| `upload_queue.py` | 较少（2） | Web后端路由、trigger脚本 |
| `routes/upload.py` | 较少（1） | Web前端API |

---

## 🎯 五、推荐使用方案

### 方案1：生产环境（推荐）⭐⭐⭐⭐⭐

**使用 `scripts/uploader/upload_to_youtube.py`**

**理由**：
1. ✅ **功能最完整**：支持所有必需功能
2. ✅ **最稳定**：经过最多测试和使用
3. ✅ **错误处理最完善**：重试机制、配额管理、错误分类
4. ✅ **文档最完整**：有详细的使用文档
5. ✅ **被最多模块使用**：所有上传模块的底层引擎

**使用方式**：
```bash
# 命令行直接使用
python3 scripts/uploader/upload_to_youtube.py \
    --episode kat_20260201 \
    --video channels/kat/output/kat_20260201/kat_20260201_youtube.mp4
```

---

### 方案2：McPOS自动化工作流（推荐）⭐⭐⭐⭐⭐

**使用 `mcpos/adapters/uploader.py`**

**理由**：
1. ✅ **符合McPOS架构**：边界清晰，职责单一
2. ✅ **严格的资产验证**：确保所有必需文件存在
3. ✅ **适配McPOS数据模型**：使用EpisodeSpec、AssetPaths
4. ✅ **符合No Unreasonable Fallback**：不使用默认值

**使用方式**：
```python
from mcpos.adapters.uploader import upload_episode_video
from mcpos.models import EpisodeSpec
from mcpos.adapters.filesystem import build_asset_paths
from mcpos.config import get_config

spec = EpisodeSpec(channel_id='kat', date='20260201', episode_id='kat_20260201')
config = get_config()
paths = build_asset_paths(spec, config)

result = await upload_episode_video(spec, paths, config)
```

---

### 方案3：Web后端服务（推荐）⭐⭐⭐⭐

**使用 `kat_rec_web/backend/t2r/services/upload_queue.py`**

**理由**：
1. ✅ **队列管理**：防止重复上传，串行执行
2. ✅ **异步处理**：适合Web后端
3. ✅ **状态跟踪**：完整的任务状态管理

**使用方式**：
```python
from kat_rec_web.backend.t2r.services.upload_queue import get_upload_queue

upload_queue = get_upload_queue()
upload_id = await upload_queue.enqueue_upload(
    episode_id='kat_20260201',
    channel_id='kat',
    video_file='channels/kat/output/kat_20260201/kat_20260201_youtube.mp4',
    metadata={...}
)
```

---

## 🔍 六、当前上传状态检查

### 视频上传验证结果

**视频ID**: `4b7sQPvdhDs`

**验证结果**：
- ✅ **视频存在**：已通过YouTube API确认
- ✅ **频道匹配**：视频在正确的账号下（频道ID: UCeeAiCtRL3Ti1cH1p64pYpw）
- ✅ **上传状态**：`processed`（已处理完成）
- ✅ **隐私状态**：`private`（私有，仅你可见）
- ✅ **排播时间**：2026-02-01T01:00:00Z (2026年2月1日 09:00 北京时间)

**账号信息**：
- 频道名称：0xGarfield
- 频道ID：UCeeAiCtRL3Ti1cH1p64pYpw
- 频道URL：https://www.youtube.com/channel/UCeeAiCtRL3Ti1cH1p64pYpw

**OAuth配置**：
- Token文件：`config/google/youtube_token.json` ✅
- Client Secret：`config/google/client_secret.json` ✅
- 刷新令牌：✅ 存在

---

## ⚠️ 七、可能的问题和解决方案

### 问题1：在YouTube Studio找不到视频

**可能原因**：
1. **视频是private状态**：需要特定的查看方式
2. **登录了错误的Google账号**：视频在另一个账号下
3. **视频被过滤或隐藏**：Studio的筛选设置

**解决方案**：
1. **确认登录账号**：
   - 检查当前登录的Google账号是否为 "0xGarfield"
   - 频道ID应为：UCeeAiCtRL3Ti1cH1p64pYpw

2. **在YouTube Studio查看**：
   - 访问：https://studio.youtube.com/
   - 点击左侧菜单的"内容"
   - 确保筛选器设置为"所有视频"（包括private）
   - 搜索标题："Kat Records Lo-Fi Mix - 20260201"

3. **直接访问视频URL**：
   - https://www.youtube.com/watch?v=4b7sQPvdhDs
   - 需要登录正确的Google账号

4. **使用API查询验证**：
   ```python
   # 已验证视频存在且频道匹配
   # 视频ID: 4b7sQPvdhDs
   # 频道ID: UCeeAiCtRL3Ti1cH1p64pYpw
   ```

---

## 📝 八、总结

### 模块数量统计

- **核心上传模块**：6个
- **上传相关脚本**：10+个
- **所有模块最终调用**：`scripts/uploader/upload_to_youtube.py`

### 推荐使用顺序

1. **生产环境**：`scripts/uploader/upload_to_youtube.py` ⭐⭐⭐⭐⭐
2. **McPOS工作流**：`mcpos/adapters/uploader.py` ⭐⭐⭐⭐⭐
3. **Web后端**：`kat_rec_web/backend/t2r/services/upload_queue.py` ⭐⭐⭐⭐
4. **批量上传**：`scripts/upload_episodes_direct.py` 或 `scripts/trigger_upload.py`

### 关键发现

1. ✅ **视频已成功上传**：API验证确认视频存在
2. ✅ **账号匹配正确**：视频在正确的频道下
3. ✅ **排播时间已设置**：2026年2月1日 09:00（北京时间）
4. ⚠️ **视频为private状态**：需要在YouTube Studio或直接URL访问

### 下一步建议

1. **确认登录账号**：确保在YouTube Studio登录的是正确的Google账号
2. **检查Studio筛选**：确保显示所有视频（包括private）
3. **直接访问URL**：https://www.youtube.com/watch?v=4b7sQPvdhDs
4. **如果仍找不到**：可能需要检查是否有多个Google账号或OAuth配置

---

**报告生成时间**：2026-01-26
**最后验证时间**：2026-01-26
**视频状态**：✅ 已上传，✅ 已处理，✅ 排播时间已设置
