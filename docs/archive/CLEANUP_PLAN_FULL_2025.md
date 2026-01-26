# Kat Rec 项目全面清理计划

**日期**: 2025-01-XX  
**模式**: 全项目清理模式  
**保护规则**: 禁止修改 `channels/*/output/**` 的任何文件

---

## 📊 扫描结果摘要

### 已确认不存在的文件（可能已删除）
- ✅ `kat_rec_web/frontend/components/UploadStatus.tsx` - 不存在
- ✅ `kat_rec_web/frontend/hooks/useAutoProductionWorkflow.ts` - 不存在

### 代码错误（需要修复）
- ❌ `ChannelTimeline.tsx` - 缺失函数导入：
  - `regenerateAsset` - 在 `t2rApi.ts` 中定义，但未导入
  - `setPreviewModal` - 在 `TaskPanel.tsx` 中定义，但在 `ChannelTimeline.tsx` 中未定义
  - `openOutputFolder` - 函数不存在，需要实现或使用后端 API

---

## 🎯 清理计划（按风险等级排序）

### 🔵 阶段 1: 极低风险 - 立即执行

#### 1.1 删除日志文件

**文件列表**:
```
logs/system_events.log.1
logs/system_events.log.2
logs/system_events.log.3
logs/system_events.log.4
logs/system_events.log.5
logs/system_events.log.6
logs/system_events.log.7
logs/system_events.log.8
logs/system_events.log.9
logs/system_events.log.10
```

**操作**: 删除所有轮转日志文件，保留最新的 `logs/system_events.log`

**风险**: 无（日志文件可以重新生成）

---

#### 1.2 删除临时测试文件

**文件列表**:
```
test_upload_20251112.py (如果存在)
check_episode_status.py (如果存在)
kat_rec_web/test_playlist_api.py (如果存在)
```

**操作**: 删除所有临时测试文件

**风险**: 无（临时文件）

---

#### 1.3 清理 audit 目录

**目录**: `audit/`

**状态**: 目录为空，无需操作

---

### 🟡 阶段 2: 低风险 - 需要确认

#### 2.1 修复代码错误

**文件**: `kat_rec_web/frontend/components/mcrb/ChannelTimeline.tsx`

**问题**:
1. 第 178, 197 行: 使用 `regenerateAsset` 但未导入
2. 第 210, 216 行: 使用 `setPreviewModal` 但未定义
3. 第 246 行: 使用 `openOutputFolder` 但函数不存在

**修复方案**:

```typescript
// 1. 添加 regenerateAsset 导入
import { 
  runEpisode, 
  startUpload, 
  verifyUpload,
  logTelemetry,
  regenerateAsset,  // ✅ 添加
} from '@/services/t2rApi'

// 2. 添加 setPreviewModal 状态
const [previewModal, setPreviewModal] = useState<{
  type: 'cover' | 'text'
  src: string
  title: string
} | null>(null)

// 3. 实现 openOutputFolder 函数
const openOutputFolder = async (event: ScheduleEvent) => {
  const folderPath = getOutputFolderPath(event)
  const apiBase = getApiBase()
  try {
    await fetch(`${apiBase}/api/t2r/open-folder?path=${encodeURIComponent(folderPath)}`)
  } catch (error) {
    console.error('Failed to open folder:', error)
    toast.error('无法打开文件夹', { duration: 2000 })
  }
}

// 4. 添加 PreviewModal 组件导入（如果存在）
import { PreviewModal } from '@/components/mcrb/PreviewModal'
```

**风险**: 低（修复代码错误）

---

#### 2.2 清理未使用的导入

**文件**: `kat_rec_web/backend/t2r/services/render_queue.py`

**问题**: 第 24 行可能导入 `upload_full` 但未使用（需要确认）

**操作**: 检查并删除未使用的导入

**风险**: 低（需要确认是否真的未使用）

---

### 🟠 阶段 3: 中等风险 - 需要重构

#### 3.1 清理历史文档（选择性删除）

**目录**: `docs/archive/`

**保留的文档**:
- `docs/archive/historical/EPISODE_FLOW_INTEGRATION_COMPLETE.md`
- `docs/archive/historical/EPISODE_FLOW_INTEGRATION_PLAN.md`
- `docs/archive/historical/README.md`

**建议删除的文档**（已完成总结和执行日志）:
```
docs/archive/historical/COMPLETION_SUMMARY.md
docs/archive/historical/FINAL_IMPLEMENTATION_REPORT.md
docs/archive/historical/FINAL_IMPLEMENTATION_SUMMARY.md
docs/archive/historical/P1_P2_COMPLETION_SUMMARY.md
docs/archive/historical/INTEGRATION_SUMMARY_2025_11_09.md
docs/archive/historical/PR_SUMMARY.md
docs/archive/historical/REFACTORING_EXECUTION_LOG.md
docs/archive/historical/PROJECT_LOG.md
docs/archive/historical/ASSET_GENERATION_FIX.md
docs/archive/historical/ASSET_GENERATION_OPTIMIZATION_SUMMARY.md
docs/archive/historical/BLOCKING_ISSUES_RESOLVED.md
docs/archive/historical/CLEANUP_SUMMARY.md
docs/archive/historical/DOCUMENTATION_UPDATE_LOG.md
docs/archive/historical/HIGH_PRIORITY_FIXES_COMPLETED.md
docs/archive/historical/RECHECK_FIXES_SUMMARY.md
docs/archive/historical/TEST_CLEANUP_SUMMARY.md
docs/archive/historical/TEST_FIXES_SUMMARY.md
```

**其他可删除的文档**（过时的分析报告）:
```
docs/archive/AUDIT_REPORT_副本.md (与 AUDIT_REPORT.md 重复)
docs/archive/CLEANUP_PLAN.md (已有 CLEANUP_PLAN_2025.md)
docs/archive/CLEANUP_SUMMARY.md (已完成)
docs/archive/cleanup_log.md (已完成)
docs/archive/GRID_PROGRESS_CLEANUP_SUMMARY.md (已完成)
```

**风险**: 低（历史文档，不影响功能）

---

#### 3.2 清理注释掉的代码

**文件**: `kat_rec_web/backend/routes/websocket.py`

**问题**: 第 58-81 行有注释掉的 `broadcast_events()` 函数，标记为 DEPRECATED

**操作**: 删除注释掉的代码，或确认是否仍需要保留

**风险**: 低（已标记为 DEPRECATED）

---

#### 3.3 清理未使用的函数

**文件**: `scripts/uploader/upload_to_youtube.py`

**问题**: `_upload_video_legacy()` 函数（如果存在）标记为 "Legacy implementation fallback"，但从未被调用

**操作**: 删除未使用的函数

**风险**: 低（从未被调用）

---

### 🔴 阶段 4: 高风险 - 需要仔细规划

#### 4.1 迁移 upload_full() 到 UploadQueue

**文件**: `kat_rec_web/backend/t2r/routes/upload.py`

**问题**: `upload_full()` 路由（第 574 行）使用 `asyncio.create_task()` 直接执行，未使用 UploadQueue

**状态**: 需要确认是否仍被使用

**建议**: 
- 如果不再使用，标记为 deprecated 或删除
- 如果仍在使用，迁移到使用 UploadQueue

**风险**: 高（可能影响现有功能）

---

#### 4.2 迁移 verify_upload() 到 VerifyWorker

**文件**: `kat_rec_web/backend/t2r/routes/upload.py`

**问题**: `verify_upload()` 路由（第 731 行）立即执行验证，未使用 VerifyWorker 延迟验证

**状态**: 仍被前端使用（`TaskPanel.tsx`, `ChannelTimeline.tsx`）

**建议**: 
- 保持向后兼容，内部改为使用 VerifyWorker
- 或标记为 deprecated，引导前端使用新 API

**风险**: 高（影响前端功能）

---

#### 4.3 整合 upload_verification.py 与 VerifyWorker

**文件**: `kat_rec_web/backend/t2r/services/upload_verification.py`

**问题**: `verify_and_update_work_cursor()` 函数仍被 `upload.py` 和 `schedule.py` 使用

**建议**: 
- 保留函数（用于 work cursor 更新）
- 在 `VerifyWorker._execute_verify()` 验证成功后调用

**风险**: 高（需要重构验证逻辑）

---

## 📋 执行清单

### 立即执行（风险: 极低）

- [ ] 删除日志文件 `logs/system_events.log.*`（保留最新）
- [ ] 删除临时测试文件（如果存在）

### 确认后执行（风险: 低）

- [ ] 修复 `ChannelTimeline.tsx` 中的代码错误
  - [ ] 添加 `regenerateAsset` 导入
  - [ ] 添加 `setPreviewModal` 状态
  - [ ] 实现 `openOutputFolder` 函数
  - [ ] 添加 `PreviewModal` 组件（如果存在）
- [ ] 清理 `render_queue.py` 中未使用的导入
- [ ] 删除历史文档（选择性）

### 规划后执行（风险: 中等-高）

- [ ] 清理注释掉的代码
- [ ] 删除未使用的函数
- [ ] 迁移 `upload_full()` 到 UploadQueue（如果仍在使用）
- [ ] 迁移 `verify_upload()` 到 VerifyWorker（保持向后兼容）
- [ ] 整合 `upload_verification.py` 与 VerifyWorker

---

## ⚠️ 注意事项

1. **保护规则**: 禁止修改 `channels/*/output/**` 的任何文件
2. **向后兼容**: 迁移旧 API 时，考虑保持向后兼容性
3. **测试**: 每次删除或重构后，需要运行测试确保功能正常
4. **文档**: 删除文件前，确认没有重要信息需要保留
5. **代码错误**: 优先修复代码错误，确保项目可以正常运行

---

## 🚀 下一步

等待用户确认后，按阶段执行清理操作。

