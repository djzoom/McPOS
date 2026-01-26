# Phase E 最终整合计划

## 执行目标
对 Upload v2 / Verify v2 进行系统级结构对齐与文档落盘，使整个上传验证流水线成为可维护、可回溯、可发布的状态。

---

## 1. 对齐代码结构

### 1.1 Helper 函数命名一致性检查
**文件**: `kat_rec_web/backend/t2r/routes/upload.py`

**当前 Helper 列表**:
- `_ensure_upload_entry()` ✅
- `_set_upload_state()` ✅
- `_broadcast_upload_state()` ✅
- `_resolve_video_path()` ✅
- `_parse_episode_id_from_upload_id()` ✅
- `_load_upload_status_from_log()` ✅
- `_persist_upload_log()` ✅
- `_enqueue_serial_upload()` ✅
- `_wait_for_upload_completion()` ✅
- `_compute_publish_plan()` ✅
- `_apply_publish_plan()` ✅
- `_update_manifest_and_emit()` ✅
- `_build_verification_checks()` ✅
- `_execute_upload_task()` ✅

**文件**: `kat_rec_web/backend/t2r/services/verify_worker.py`

**当前 Helper 列表**:
- `_ensure_worker_running()` ✅
- `_worker_loop()` ✅
- `_execute_verify()` ✅
- `_verify_via_videos_list()` ✅
- `_update_upload_log()` ⚠️ **需要统一**
- `_emit_verification_event()` ✅
- `_update_work_cursor()` ✅

### 1.2 发现的问题
1. **日志写入不一致**: 
   - `upload.py` 使用 `_persist_upload_log()`
   - `verify_worker.py` 使用 `_update_upload_log()` (内联 JSON 写入)
   - **需要**: 创建统一的 `_write_upload_log()` wrapper

2. **状态字段不一致**:
   - `upload.py` 使用 `status="uploaded"` 和 `state="uploaded"`
   - `verify_worker.py` 使用 `state="verified"` 或 `state="failed"`
   - **需要**: 统一状态值枚举

### 1.3 执行计划
- [ ] 创建统一的 `_write_upload_log()` helper (在 `upload.py` 中)
- [ ] 修改 `verify_worker.py` 使用统一的 helper
- [ ] 确认所有状态值使用统一枚举
- [ ] 清理未使用的导入和变量

---

## 2. 对齐日志格式

### 2.1 当前日志结构分析

**`_persist_upload_log()` 写入的字段**:
```python
{
    "episode_id": str,
    "channel_id": str,
    "upload_id": str,
    "video_file": str,
    "video_id": Optional[str],
    "video_url": Optional[str],
    "state": "uploaded" | "failed",
    "status": "completed" | "failed",
    "error": Optional[str],
    "errors": List[str],
    "upload_status": Dict,
    "verified": Optional[bool],
    "created_at": Optional[str],
    "completed_at": Optional[str],
}
```

**`verify_worker._update_upload_log()` 写入的字段**:
```python
{
    "episode_id": str,
    "channel_id": str,
    "video_id": str,
    "status": "completed",
    "state": "verified" | "failed" | "uploaded",
    "verified": bool,
    "verified_at": str,
    "verification_errors": Optional[List[str]],
    "error": Optional[str],
}
```

### 2.2 统一日志格式规范

**标准字段（必须）**:
- `episode_id`: str
- `channel_id`: str
- `video_id`: Optional[str]
- `state`: "queued" | "uploading" | "uploaded" | "verifying" | "verified" | "failed"
- `error`: Optional[str] (单行错误消息)
- `errors`: List[str] (详细错误列表)

**可选字段**:
- `upload_id`: Optional[str]
- `video_file`: Optional[str]
- `video_url`: Optional[str]
- `status`: "completed" | "failed" (向后兼容)
- `verified`: Optional[bool]
- `verified_at`: Optional[str]
- `created_at`: Optional[str]
- `completed_at`: Optional[str]
- `verification_errors`: Optional[List[str]]

### 2.3 执行计划
- [ ] 创建 `_write_upload_log()` 统一 wrapper
- [ ] 定义 `UploadLogSchema` 类型/常量
- [ ] 修改 `_persist_upload_log()` 使用 wrapper
- [ ] 修改 `verify_worker._update_upload_log()` 使用 wrapper
- [ ] 确保所有日志写入都通过 wrapper

---

## 3. 对齐 WebSocket 行为

### 3.1 当前 WebSocket 事件分析

**后端发送**: `broadcast_upload_state_changed()`
```python
{
    "episode_id": str,
    "channel_id": str,
    "state": "queued" | "uploading" | "uploaded" | "verifying" | "verified" | "failed",
    "upload_id": Optional[str],
    "video_id": Optional[str],
    "error": Optional[str],
    "errors": Optional[List[str]],
    "timestamp": str,
}
```

**前端接收**: `useWebSocket.ts`
```typescript
{
    state: 'pending' | 'queued' | 'uploading' | 'uploaded' | 'verifying' | 'verified' | 'failed',
    upload_id?: string,
    video_id?: string,
    error?: string,
    errors?: string[],
    timestamp?: string,
}
```

### 3.2 发现的问题
- ✅ 状态值基本一致
- ⚠️ 前端有 `pending` 状态，后端没有（后端从 `queued` 开始）
- ✅ 字段名称一致

### 3.3 执行计划
- [ ] 确认所有 `broadcast_upload_state_changed()` 调用使用统一状态值
- [ ] 检查是否有旧事件名称或 payload 格式不一致
- [ ] 统一前后端状态枚举定义

---

## 4. 对齐前端依赖

### 4.1 当前前端调用分析

**使用 `getUploadStatus()` 轮询**:
- `OverviewGrid.tsx` (line 1152): 轮询上传状态
  - **问题**: 应该使用 WebSocket 推送，而不是轮询
  - **修复**: 移除轮询逻辑，依赖 WebSocket 事件

**使用 `verifyUpload()` API**:
- `ChannelTimeline.tsx` (line 294)
- `TaskPanel.tsx` (line 19, 可能使用)
- `PostUploadVerify.tsx` (line 46)
  - **问题**: 这些组件可能还在使用旧的同步验证 API
  - **修复**: 改为使用 WebSocket 推送或异步状态

### 4.2 执行计划
- [ ] 移除 `OverviewGrid.tsx` 中的 `getUploadStatus()` 轮询逻辑
- [ ] 检查 `ChannelTimeline.tsx` 的 `verifyUpload()` 使用情况
- [ ] 检查 `TaskPanel.tsx` 的 `verifyUpload()` 使用情况
- [ ] 检查 `PostUploadVerify.tsx` 的 `verifyUpload()` 使用情况
- [ ] 确保所有组件依赖 WebSocket 推送或新的异步状态结构

---

## 5. 更新项目文档

### 5.1 文档生成计划

**文档 A: Upload Pipeline v2 Architecture**
- 文件: `docs/ARCHITECTURE_UPLOAD_V2.md`
- 内容:
  - UploadQueue 架构
  - 串行上传流程
  - 状态机转换
  - API 端点
  - 日志格式
  - WebSocket 事件

**文档 B: Verify Pipeline v2 Architecture**
- 文件: `docs/ARCHITECTURE_VERIFY_V2.md`
- 内容:
  - VerifyWorker 架构
  - 延迟验证策略
  - 状态机转换
  - Work cursor 更新逻辑
  - WebSocket 事件

**文档 C: End-to-End Upload→Verify→Manifest→WebSocket Lifecycle**
- 文件: `docs/LIFECYCLE_UPLOAD_VERIFY.md`
- 内容:
  - 完整生命周期流程图
  - 各阶段状态转换
  - Manifest 更新时机
  - WebSocket 事件序列
  - 错误处理流程

### 5.2 执行计划
- [ ] 扫描代码生成 Upload Pipeline 架构图
- [ ] 扫描代码生成 Verify Pipeline 架构图
- [ ] 生成端到端生命周期文档
- [ ] 确保文档与代码同步

---

## 6. 对齐测试

### 6.1 测试 Skeleton 结构

**文件**: `kat_rec_web/backend/t2r/tests/test_upload_pipeline_v2.py`
- Fixtures:
  - `mock_upload_queue()`
  - `mock_verify_worker()`
  - `mock_youtube_api()`
  - `sample_episode_setup()`
- Test Classes:
  - `TestUploadQueue`
  - `TestVerifyWorker`
  - `TestUploadVerifyIntegration`
  - `TestWebSocketEvents`

**文件**: `kat_rec_web/backend/t2r/tests/test_verify_pipeline_v2.py`
- Fixtures:
  - `mock_verify_worker()`
  - `mock_youtube_api()`
  - `sample_upload_log()`
- Test Classes:
  - `TestVerifyWorker`
  - `TestWorkCursorUpdate`
  - `TestVerificationEvents`

### 6.2 执行计划
- [ ] 创建测试文件结构
- [ ] 定义 fixtures 和 mocks
- [ ] 创建测试类 skeleton（不写完整测试）
- [ ] 确保测试结构可扩展

---

## 执行顺序

1. **步骤 1-2**: 代码结构对齐 + 日志格式统一（同时进行，相互依赖）
2. **步骤 3**: WebSocket 行为对齐
3. **步骤 4**: 前端依赖对齐
4. **步骤 5**: 文档生成
5. **步骤 6**: 测试 skeleton

---

## 禁止修改

- ❌ `channels/*/output/**` 的任何文件
- ❌ 任何公共 API 的函数签名
- ❌ 除非发现引用错误，否则不准重写内部逻辑

---

## 预期输出

1. 统一的日志写入 wrapper
2. 统一的 WebSocket 事件格式
3. 前端移除所有 polling 逻辑
4. 三份架构文档
5. 测试 skeleton 结构

---

**等待用户确认后开始执行**

