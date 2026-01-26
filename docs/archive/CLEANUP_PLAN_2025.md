# Kat Rec 项目清理与重构计划

**日期**: 2025-01-XX  
**模式**: 项目清理与重构模式  
**保护规则**: 禁止修改 `channels/*/output/**` 的任何文件

---

## 执行顺序与扫描结果

### 阶段 1: 清理外围层（最安全）✅

#### 1.1 无效文档清理

**发现项**:

1. **docs/archive/** 目录 (78个文件)
   - 大量历史完成总结和执行日志
   - 过时的设计草稿和实现笔记
   - 已完成的 sprint 报告

2. **audit/** 目录
   - `audit/golden_path_v0.9-rc0/` - 旧版本审计报告
   - `audit/ws_probe.py`, `audit/ws_sample.jsonl`, `audit/ws_stats.json` - 临时测试文件

3. **根目录临时文件**
   - `test_upload_20251112.py` - 临时测试脚本
   - `check_episode_status.py` - 临时检查脚本
   - `kat_rec_web/test_playlist_api.py` - 临时测试文件

4. **日志文件**
   - `logs/system_events.log.*` (多个轮转日志)
   - `.herewego-frontend.log`, `.herewego-backend.log` - 临时日志

**清理建议** (风险: 极低):

```
删除文件:
- docs/archive/historical/*.md (除 EPISODE_FLOW_INTEGRATION_*.md 和 README.md)
- docs/archive/sprints/*.md (已完成 sprint 报告)
- docs/archive/*.md (过时的分析报告，保留核心文档)
- audit/golden_path_v0.9-rc0/ (旧版本审计，保留 audit/ 目录结构)
- audit/ws_*.py, audit/ws_*.jsonl, audit/ws_*.json (临时测试文件)
- test_upload_20251112.py
- check_episode_status.py
- kat_rec_web/test_playlist_api.py
- logs/system_events.log.* (保留最新)
- .herewego-*.log (临时日志)
```

**保留文档**:
- `docs/01_SYSTEM_OVERVIEW.md`
- `docs/02_WORKFLOW_AND_AUTOMATION.md`
- `docs/03_DEVELOPMENT_GUIDE.md`
- `docs/04_DEPLOYMENT_AND_ROADMAP.md`
- `docs/archive/historical/EPISODE_FLOW_INTEGRATION_*.md`
- `production-system-enhancement-plan.plan.md`

---

### 阶段 2: 清理"无引用代码层" ⚠️

#### 2.1 未使用的组件和 Hooks

**发现项**:

1. **前端组件**:
   - `kat_rec_web/frontend/components/UploadStatus.tsx` - 需要检查是否被使用
   - `kat_rec_web/frontend/components/t2r/PostUploadVerify.tsx` - 使用旧的 verify_upload API

2. **前端 Hooks**:
   - 所有 hooks 都有引用，但需要检查是否实际使用

3. **后端服务**:
   - ⚠️ `kat_rec_web/backend/t2r/services/upload_verification.py` - **仍在使用**
     - `verify_upload_from_log()` - 仍被 `verify_and_update_work_cursor()` 使用
     - `verify_upload_via_youtube_api()` - 仍被 `verify_and_update_work_cursor()` 使用
     - `verify_and_update_work_cursor()` - 仍被 `upload.py` 和 `schedule.py` 使用
     - **建议**: 保留,但考虑与 VerifyWorker 整合 (work cursor 更新逻辑)

**清理建议** (风险: 中等):

```
需要进一步分析:
- 检查 UploadStatus.tsx 是否被任何组件导入
- 检查 PostUploadVerify.tsx 是否仍在使用旧的 verify_upload API
- 确认 upload_verification.py 中的函数是否完全被 VerifyWorker 替代
```

#### 2.2 已迁移到新架构的旧代码

**发现项**:

1. **upload_to_youtube.py**:
   - `_upload_video_legacy()` 函数 (第 504-521 行) - 标记为 "Legacy implementation fallback"，但从未被调用

2. **upload.py 路由**:
   - ⚠️ `upload_full()` 路由 (第 413-777 行) - **仍被 `render_queue.py` 导入,但 `render_queue.py` 已迁移到 UploadQueue**
     - **问题**: `render_queue.py` 第 25 行导入 `upload_full`,但第 472-500 行实际使用 `UploadQueue`
     - **建议**: 删除 `render_queue.py` 中未使用的导入,或确认 `upload_full()` 是否仍需要
   - ⚠️ `verify_upload()` 路由 (第 782-930 行) - **仍被前端使用** (`PostUploadVerify.tsx`, `TaskPanel.tsx`, `ChannelTimeline.tsx`)
     - **建议**: 保持向后兼容,但内部改为使用 VerifyWorker

**清理建议** (风险: 高 - 需要确认):

```
需要确认:
1. upload_full() 是否应该迁移到使用 UploadQueue?
   - 当前: render_queue.py 调用 upload_full()
   - 新架构: 应该使用 UploadQueue.enqueue_upload()
   
2. verify_upload() 是否应该迁移到使用 VerifyWorker?
   - 当前: 前端直接调用 /upload/verify
   - 新架构: 应该通过 VerifyWorker 延迟验证
   
3. _upload_video_legacy() 可以安全删除 (从未被调用)
```

---

### 阶段 3: 清理"Legacy 旧逻辑层" ⚠️⚠️

#### 3.1 OLD 4K Workflow 残留

**发现项**:
- `scripts/oneclick_4k.sh` - **独立的4K视频生成脚本**
  - 内容: 调用 `create_mixtape.py --fps 1` 生成4K静帧视频
  - 状态: 未发现被其他脚本引用
  - **建议**: 保留 (可能是手动使用的工具脚本)

#### 3.2 已弃用的 Playlist 生成路由

**发现项**:
- 未发现独立的 `/generate-playlist` 路由
- `plan.py` 和 `automation.py` 中有播放列表生成逻辑，但这是核心功能，不应删除

**清理建议** (风险: 无):
- 无需清理（播放列表生成是核心功能）

#### 3.3 旧的 Upload/Verify Pipeline

**发现项**:

1. **upload_full() 路由**:
   - 位置: `kat_rec_web/backend/t2r/routes/upload.py:413-777`
   - 状态: 仍被 `render_queue.py` 使用
   - 问题: 内部使用 `asyncio.create_task(_execute_upload_task())` 直接执行，未使用 UploadQueue
   - 建议: 迁移到使用 UploadQueue

2. **verify_upload() 路由**:
   - 位置: `kat_rec_web/backend/t2r/routes/upload.py:782-930`
   - 状态: 仍被前端使用
   - 问题: 立即执行验证，未使用 VerifyWorker 延迟验证
   - 建议: 迁移到使用 VerifyWorker，或标记为 deprecated

3. **upload_verification.py 服务**:
   - 位置: `kat_rec_web/backend/t2r/services/upload_verification.py`
   - 状态: 仍被 `upload.py` 和 `schedule.py` 使用
   - 函数: `verify_and_update_work_cursor()` - 用于更新 work cursor
   - 建议: 保留，但考虑与 VerifyWorker 整合

**清理建议** (风险: 高 - 需要重构):

```
重构建议:
1. upload_full() 应该改为使用 UploadQueue:
   - 当前: asyncio.create_task(_execute_upload_task())
   - 改为: await upload_queue.enqueue_upload()

2. verify_upload() 应该改为使用 VerifyWorker:
   - 当前: 立即执行验证
   - 改为: await verify_worker.schedule_verify()

3. 保留 upload_verification.py 中的 verify_and_update_work_cursor()
   - 这是 work cursor 更新逻辑，与验证逻辑分离
   - 可以考虑在 VerifyWorker 验证成功后调用
```

#### 3.4 Legacy Store / 旧事件广播

**发现项**:

1. **Zustand Stores**:
   - ✅ `channelSlice.ts` - **仍被使用** (`ChannelCard.tsx`, `useDiagnosticsWebSocket.ts`, `index.tsx`)
   - ✅ `feedSlice.ts` - **仍被使用** (`SystemFeed.tsx`, `useDiagnosticsWebSocket.ts`)
   - ✅ `runbookStore.ts` - **仍被使用** (部分功能)
   - ✅ `t2rScheduleStore.ts`, `t2rAssetsStore.ts`, `t2rSrtStore.ts`, `t2rDescStore.ts` - **T2R 页面使用**

2. **WebSocket 事件**:
   - 所有事件都有使用，但需要检查格式一致性

**清理建议** (风险: 中等):

```
需要检查:
- channelSlice.ts 是否被任何组件导入使用
- 确认所有 WebSocket 事件格式是否统一
```

---

### 阶段 4: 优化"主干轻量层" ⚠️⚠️⚠️

#### 4.1 EpisodeFlow / RenderQueue / UploadQueue / VerifyWorker 轻量整理

**发现项**:

1. **upload.py 路由**:
   - `upload_full()` 和 `verify_upload()` 有重复的验证逻辑
   - `_execute_upload_task()` 内部有重复的错误处理

2. **upload_verification.py**:
   - `verify_upload_from_log()` 和 `verify_upload_via_youtube_api()` 可以合并部分逻辑

3. **WebSocket 事件格式**:
   - `upload_state_changed` 事件已统一
   - 需要确认所有上传相关事件都使用统一格式

**清理建议** (风险: 中等):

```
优化建议:
1. 提取 upload.py 中的重复错误处理逻辑
2. 统一验证逻辑到 VerifyWorker
3. 确认 WebSocket 事件格式一致性
```

---

### 阶段 5: 全项目健康检查 ✅

#### 5.1 未被使用的文件

**发现项**:
- `scripts/uploader/upload_to_youtube.py` 中的 `_upload_video_legacy()` 函数
- `kat_rec_web/frontend/components/UploadStatus.tsx` - 需要确认
- `kat_rec_web/frontend/stores/channelSlice.ts` - 需要确认

#### 5.2 新旧 Pipeline 混合调用

**发现项**:
- ✅ `render_queue.py` 使用 `upload_full()` (旧方式)
- ✅ 前端直接调用 `verify_upload()` (旧方式)
- ✅ `start_upload()` 已迁移到使用 UploadQueue (新方式)

**问题**:
- 存在新旧 pipeline 混合使用的情况

#### 5.3 前后端事件枚举一致性

**发现项**:
- ✅ 后端: `kat_rec_web/backend/t2r/events/upload_stage.py` 定义了 `UploadState` 枚举
- ✅ 前端: `kat_rec_web/frontend/stores/scheduleStore.ts` 定义了 `uploadState` 类型
- ⚠️ 需要确认两者是否完全一致

---

## 最终清理建议列表（按风险从低到高排序）

### 🔵 风险: 极低 (可立即执行)

1. **删除无效文档**:
   - `docs/archive/historical/` 中除 EPISODE_FLOW_INTEGRATION_*.md 和 README.md 外的所有文件
   - `docs/archive/sprints/` 中已完成的 sprint 报告
   - `audit/golden_path_v0.9-rc0/` 目录
   - `audit/ws_*.py`, `audit/ws_*.jsonl`, `audit/ws_*.json`
   - `test_upload_20251112.py`
   - `check_episode_status.py`
   - `kat_rec_web/test_playlist_api.py`
   - `logs/system_events.log.*` (保留最新)
   - `.herewego-*.log`

2. **删除未使用的函数**:
   - `scripts/uploader/upload_to_youtube.py` 中的 `_upload_video_legacy()` 函数 (第 504-521 行)

### 🟡 风险: 低 (需要确认后执行)

3. **删除未使用的组件**:
   - ✅ `kat_rec_web/frontend/components/UploadStatus.tsx` - **确认未使用,可删除**

4. **检查旧脚本**:
   - `scripts/oneclick_4k.sh` - **保留** (可能是手动使用的工具脚本)

### 🟠 风险: 中等 (需要重构)

5. **清理 render_queue.py 中未使用的导入**:
   - 文件: `kat_rec_web/backend/t2r/services/render_queue.py`
   - 位置: 第 25 行
   - 操作: 删除 `from ..routes.upload import UploadFullRequest, upload_full` (未使用)
   - 影响: 无 (render_queue.py 已使用 UploadQueue)
   
6. **迁移 upload_full() 到 UploadQueue (可选)**:
   - 文件: `kat_rec_web/backend/t2r/routes/upload.py`
   - 位置: 第 413-777 行
   - 状态: 当前未被使用 (render_queue.py 已迁移)
   - 操作: 考虑标记为 deprecated 或删除
   - 影响: 需要确认是否有其他调用者

7. **迁移 verify_upload() 到 VerifyWorker**:
   - 文件: `kat_rec_web/backend/t2r/routes/upload.py`
   - 位置: 第 782-930 行
   - 操作: 改为使用 `verify_worker.schedule_verify()` 延迟验证
   - 影响: 前端调用需要更新（或保持兼容，内部使用 VerifyWorker）

8. **整合 upload_verification.py 与 VerifyWorker**:
   - 文件: `kat_rec_web/backend/t2r/services/upload_verification.py`
   - 操作: 将 `verify_and_update_work_cursor()` 逻辑整合到 VerifyWorker
   - 影响: `upload.py` 和 `schedule.py` 中的调用需要更新

### 🔴 风险: 高 (需要仔细规划)

9. **统一前后端事件枚举**:
   - 后端: `kat_rec_web/backend/t2r/events/upload_stage.py`
   - 前端: `kat_rec_web/frontend/stores/scheduleStore.ts`
   - 操作: 确保 `UploadState` 枚举与前端 `uploadState` 类型完全一致

10. **清理重复验证逻辑**:
   - `upload_full()` 和 `verify_upload()` 中的验证逻辑
   - `upload_verification.py` 和 `verify_worker.py` 中的验证逻辑
   - 操作: 统一到 VerifyWorker

---

## 详细操作清单

### 阶段 1: 外围层清理 (风险: 极低)

#### 1.1 删除无效文档

```bash
# 删除历史文档 (保留核心文档)
rm -rf docs/archive/historical/COMPLETION_SUMMARY.md
rm -rf docs/archive/historical/FINAL_IMPLEMENTATION_*.md
rm -rf docs/archive/historical/P1_P2_COMPLETION_SUMMARY.md
# ... (其他历史文档)

# 删除已完成 sprint 报告
rm -rf docs/archive/sprints/SPRINT1_*.md
rm -rf docs/archive/sprints/SPRINT2_*.md
rm -rf docs/archive/sprints/SPRINT3_*.md
rm -rf docs/archive/sprints/SPRINT6_*.md

# 删除旧审计报告
rm -rf audit/golden_path_v0.9-rc0/

# 删除临时测试文件
rm -f test_upload_20251112.py
rm -f check_episode_status.py
rm -f kat_rec_web/test_playlist_api.py
rm -f audit/ws_*.py audit/ws_*.jsonl audit/ws_*.json

# 清理日志文件
rm -f logs/system_events.log.*
rm -f .herewego-*.log
```

#### 1.2 删除未使用的函数

**文件**: `scripts/uploader/upload_to_youtube.py`
- 删除 `_upload_video_legacy()` 函数 (第 504-521 行)

---

### 阶段 2: 无引用代码层清理 (风险: 低-中等)

#### 2.1 删除未使用的组件

**确认未使用**:
- ✅ `kat_rec_web/frontend/components/UploadStatus.tsx` - **可删除** (未被导入)

#### 2.2 检查旧脚本

**保留**:
- `scripts/oneclick_4k.sh` - 可能是手动使用的工具脚本,保留

---

### 阶段 3: Legacy 旧逻辑层清理 (风险: 高 - 需要重构)

#### 3.1 清理 render_queue.py 中未使用的导入

**文件**: `kat_rec_web/backend/t2r/services/render_queue.py`

**当前代码** (第 25 行):
```python
from ..routes.upload import UploadFullRequest, upload_full
```

**问题**: `render_queue.py` 已迁移到使用 UploadQueue (第 472-500 行),不再使用 `upload_full`

**建议**: 删除此导入

---

#### 3.2 迁移 upload_full() 到 UploadQueue (可选)

**文件**: `kat_rec_web/backend/t2r/routes/upload.py`

**当前代码** (第 483-492 行):
```python
# Start upload task
try:
    task = asyncio.create_task(
        _execute_upload_task(
            upload_id,
            request.episode_id,
            request.video_file,
            request.metadata
        )
    )
```

**建议改为**:
```python
# ✅ Enqueue upload to serial queue
from ..services.upload_queue import get_upload_queue

upload_queue = get_upload_queue()
try:
    upload_id = await upload_queue.enqueue_upload(
        episode_id=request.episode_id,
        channel_id=request.channel_id,
        video_file=str(video_path),
        metadata=request.metadata
    )
```

**影响文件**:
- 无 (render_queue.py 已迁移到 UploadQueue)

**注意**: 如果确认 `upload_full()` 不再被使用,可以考虑标记为 deprecated 或删除

---

#### 3.3 迁移 verify_upload() 到 VerifyWorker

**文件**: `kat_rec_web/backend/t2r/routes/upload.py`

**当前代码** (第 782-930 行):
```python
@router.post("/upload/verify")
async def verify_upload(request: UploadVerifyRequest) -> Dict:
    # 立即执行验证
```

**建议改为**:
```python
@router.post("/upload/verify")
async def verify_upload(request: UploadVerifyRequest) -> Dict:
    """
    Schedule verification via VerifyWorker (delayed verification).
    
    ⚠️ DEPRECATED: This endpoint is kept for backward compatibility.
    New code should use VerifyWorker directly.
    """
    from ..services.verify_worker import get_verify_worker
    from src.core.config_access import get_youtube_config
    
    verify_worker = get_verify_worker()
    youtube_config = get_youtube_config()
    verify_delay = youtube_config.get("verify_delay_seconds", 180)
    
    await verify_worker.schedule_verify(
        episode_id=request.episode_id,
        channel_id=request.channel_id or "kat_lofi",
        video_id=request.video_id,
        delay_seconds=verify_delay
    )
    
    return {
        "status": "ok",
        "message": "Verification scheduled",
        "scheduled_at": datetime.utcnow().isoformat(),
        "verify_delay_seconds": verify_delay
    }
```

**影响文件**:
- `kat_rec_web/frontend/components/t2r/PostUploadVerify.tsx`
- `kat_rec_web/frontend/components/mcrb/TaskPanel.tsx`
- `kat_rec_web/frontend/components/mcrb/ChannelTimeline.tsx`
- `kat_rec_web/frontend/services/t2rApi.ts`

**注意**: 保持向后兼容,内部改为使用 VerifyWorker

---

#### 3.4 整合 upload_verification.py 与 VerifyWorker

**建议**:
- 保留 `verify_and_update_work_cursor()` 函数（用于 work cursor 更新）
- 在 `VerifyWorker._execute_verify()` 验证成功后调用 `verify_and_update_work_cursor()`

---

### 阶段 4: 主干轻量层优化 (风险: 中等)

#### 4.1 提取重复逻辑

**建议**:
- 统一错误处理逻辑
- 统一验证逻辑到 VerifyWorker
- 统一 WebSocket 事件格式

---

### 阶段 5: 健康检查

#### 5.1 检查前后端事件枚举一致性

**后端** (`kat_rec_web/backend/t2r/events/upload_stage.py`):
```python
class UploadState(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    FAILED = "failed"
```

**前端** (`kat_rec_web/frontend/stores/scheduleStore.ts`):
```typescript
uploadState?: {
  state: 'pending' | 'queued' | 'uploading' | 'uploaded' | 'verifying' | 'verified' | 'failed'
  ...
}
```

**状态**: ✅ 一致

---

## 执行优先级

### 立即执行 (风险: 极低)
1. 删除无效文档
2. 删除 `_upload_video_legacy()` 函数
3. 删除 `kat_rec_web/frontend/components/UploadStatus.tsx` (未使用)

### 确认后执行 (风险: 低)
4. 清理 `render_queue.py` 中未使用的导入 (`upload_full`)

### 规划后执行 (风险: 中等-高)
5. 迁移 verify_upload() 到 VerifyWorker (保持向后兼容)
6. 整合 upload_verification.py 与 VerifyWorker
7. 统一前后端事件枚举 (已确认一致)
8. 清理重复验证逻辑

---

## 注意事项

1. **保护规则**: 禁止修改 `channels/*/output/**` 的任何文件
2. **向后兼容**: 迁移旧 API 时，考虑保持向后兼容性
3. **测试**: 每次删除或重构后，需要运行测试确保功能正常
4. **文档**: 删除文件前，确认没有重要信息需要保留

---

## 下一步

等待用户确认后，按阶段执行清理操作。

