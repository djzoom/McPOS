# ASR Residual Reference Scan Report

**日期**: 2025-01-XX  
**目的**: Stateflow V4 - 识别所有剩余的 ASR 相关代码  
**状态**: 仅扫描，无代码修改

---

## 执行摘要

扫描了整个 Kat_Rec 工作区，识别出 **27 个文件**包含 ASR 相关引用。其中：
- **DEFINITELY TO REMOVE**: 8 个文件（仍在写入或读取 ASR 状态）
- **MAYBE TO REMOVE**: 12 个文件（已弃用但可能仍被引用）
- **SAFE/IGNORE**: 7 个文件（仅在注释或文档中提及）

---

## A. DEFINITELY TO REMOVE

这些文件仍然直接使用或写入 ASR 状态，需要立即修复。

### 后端文件

#### 1. `kat_rec_web/backend/t2r/services/filesystem_monitor.py`
- **行数**: 225-248
- **问题**: 在 `_on_asset_changed` 方法中调用 `registry.update_asset_state()` 写入 ASR
- **说明**: 文件系统监控器仍在将文件状态写入 ASR，违反了 Stateflow V4 原则
- **修复建议**: 移除所有 `update_asset_state` 调用，或转换为纯审计日志记录

#### 2. `kat_rec_web/backend/t2r/services/auto_complete_episodes.py`
- **行数**: 48-55
- **问题**: 调用 `asset_service.scan_and_update_episode_assets()` 和 `check_episode_assets_status()`，这些方法可能写入 ASR
- **说明**: 自动完成功能仍依赖 ASR 来检查资产状态
- **修复建议**: 替换为 `file_detect.py` 的直接文件系统检查

#### 3. `kat_rec_web/backend/t2r/services/render_queue_sync.py`
- **行数**: 61-71, 183, 226
- **问题**: 使用 `asset_service` 和 `registry.get_all_assets_for_episode()` 从 ASR 读取资产状态
- **说明**: 渲染队列同步功能仍从 ASR 读取资产信息
- **修复建议**: 替换为 `file_detect.py` 的直接文件系统检查

#### 4. `kat_rec_web/backend/t2r/services/asset_state_service.py`
- **行数**: 54, 80, 97
- **问题**: 直接调用 `registry.update_asset_state()` 和 `get_asset_state_registry()`
- **说明**: 虽然已标记为弃用，但仍包含写入 ASR 的逻辑
- **修复建议**: 移除所有 ASR 写入逻辑，或完全删除此服务

#### 5. `kat_rec_web/backend/t2r/services/data_migration.py`
- **行数**: 196
- **问题**: 在迁移过程中调用 `registry.update_asset_state()`
- **说明**: 数据迁移脚本仍在写入 ASR
- **修复建议**: 如果迁移已完成，可以删除此代码；否则转换为仅迁移元数据

### 前端文件

#### 6. `kat_rec_web/frontend/components/mcrb/RenderQueuePanel.tsx`
- **行数**: 7, 51, 111, 244, 280, 489
- **问题**: 多处调用 `calculateStageStatus()`，虽然函数已禁用，但仍在使用其返回值
- **说明**: 渲染队列面板仍依赖已弃用的 `calculateStageStatus` 来判断状态
- **修复建议**: 替换为文件系统检查（类似 OverviewGrid 的更新方式）

#### 7. `kat_rec_web/frontend/components/mcrb/UploadQueuePanel.tsx`
- **行数**: 7, 65, 104, 131, 418
- **问题**: 多处调用 `calculateStageStatus()` 来判断上传状态
- **说明**: 上传队列面板仍依赖已弃用的 `calculateStageStatus`
- **修复建议**: 替换为文件系统检查 + `useVideoProgress` hook

#### 8. `kat_rec_web/frontend/hooks/useAssetCheckWorker.ts`
- **行数**: 18, 24-25, 75, 76, 285-286
- **问题**: 调用 `calculateStageStatus()` 和 `calculateAssetStageReadiness()`
- **说明**: 虽然 hook 已禁用，但代码仍包含 ASR 相关的逻辑
- **修复建议**: 完全删除此 hook，或移除所有 ASR 相关逻辑

---

## B. MAYBE TO REMOVE

这些文件包含已弃用的函数或遗留代码，但可能仍被某些地方引用。需要检查依赖关系。

### 后端文件

#### 1. `kat_rec_web/backend/t2r/services/asset_state_registry.py`
- **状态**: 核心 ASR 实现，已标记为弃用
- **问题**: 仍被多个文件导入和使用
- **建议**: 检查所有导入此模块的文件，逐步移除依赖

#### 2. `kat_rec_web/backend/t2r/services/asset_service.py`
- **状态**: 已标记为弃用，但方法已改为 no-op
- **问题**: 仍被 `auto_complete_episodes.py` 和 `render_queue_sync.py` 使用
- **建议**: 在移除依赖后删除此服务

#### 3. `kat_rec_web/backend/t2r/scripts/migrate_assets_to_asr.py`
- **状态**: 迁移脚本，可能不再需要
- **问题**: 如果迁移已完成，此脚本可以删除
- **建议**: 确认迁移状态后删除

#### 4. `kat_rec_web/backend/t2r/tests/test_asset_state_registry.py`
- **状态**: ASR 的单元测试
- **问题**: 如果 ASR 将被移除，这些测试也应删除
- **建议**: 在移除 ASR 时一并删除

### 前端文件

#### 5. `kat_rec_web/frontend/stores/scheduleStore.ts`
- **行数**: 930-943, 956-969
- **状态**: `calculateStageStatus()` 和 `calculateAssetStageReadiness()` 已禁用但未删除
- **问题**: 仍被多个组件导入和使用
- **建议**: 在所有使用处替换后，删除这些函数

#### 6. `kat_rec_web/frontend/utils/runbookStageMapper.ts`
- **状态**: 用于将 runbook 阶段映射到 stage keys
- **问题**: 仍被 `scheduleStore.ts` 导入，但可能不再需要
- **建议**: 检查是否仍在使用，如果不需要则删除

#### 7. `kat_rec_web/frontend/components/mcrb/FileMatrix.tsx`
- **行数**: 15, 18, 80-127
- **状态**: 使用 `AssetStageReadiness` 类型，依赖已弃用的 readiness 计算
- **问题**: 组件仍依赖 readiness 数据结构
- **建议**: 重构为使用 `useEpisodeAssets` hook，或标记为弃用

#### 8. `kat_rec_web/frontend/stores/__tests__/scheduleStore.test.ts`
- **状态**: 测试 `calculateStageStatus` 函数
- **问题**: 测试已弃用的函数
- **建议**: 更新测试以使用新的统一 hooks，或删除这些测试

#### 9. `kat_rec_web/frontend/utils/__tests__/runbookStageMapper.test.ts`
- **状态**: 测试 runbook stage mapper
- **问题**: 如果 mapper 不再需要，这些测试也应删除
- **建议**: 检查 mapper 的使用情况后决定

#### 10. `kat_rec_web/frontend/scripts/atlas-debug-17.js`
- **行数**: 119-120, 158-159, 171-193
- **状态**: 调试脚本，使用已弃用的函数
- **问题**: 调试工具仍依赖旧的状态计算
- **建议**: 更新调试脚本以使用新的 hooks，或标记为弃用

#### 11. `kat_rec_web/frontend/__tests__/README.md`
- **状态**: 测试文档，提及 `calculateStageStatus`
- **问题**: 文档仍描述已弃用的函数
- **建议**: 更新文档以反映新的架构

#### 12. `kat_rec_web/frontend/components/mcrb/GridProgressV3.mdx`
- **状态**: 文档文件，描述旧的 V3 架构
- **问题**: 文档描述已弃用的 readiness 逻辑
- **建议**: 标记为历史文档，或更新为 V4 架构

---

## C. SAFE / IGNORE

这些文件仅在注释、文档或类型定义中提及 ASR，不包含实际的 ASR 使用逻辑。

### 后端文件

#### 1. `kat_rec_web/backend/t2r/services/episode_metadata_registry.py`
- **行数**: 2
- **说明**: 仅在注释中提及 "Refactored from ASR"，说明其历史
- **状态**: ✅ 安全，无需修改

#### 2. `kat_rec_web/backend/t2r/routes/episodes.py`
- **行数**: 175
- **说明**: 仅在注释中说明 "no ASR or registry dependencies"
- **状态**: ✅ 安全，无需修改

#### 3. `kat_rec_web/backend/t2r/services/render_progress_service.py`
- **行数**: 8, 35
- **说明**: 仅在注释中说明 "no ASR or registry dependencies"
- **状态**: ✅ 安全，无需修改

#### 4. `kat_rec_web/backend/t2r/routes/state_snapshot.py`
- **行数**: 9-10
- **说明**: 仅在注释中说明 "ASR-based readiness and stageStatus are deprecated"
- **状态**: ✅ 安全，无需修改

#### 5. `kat_rec_web/backend/t2r/utils/file_detect.py`
- **行数**: 5
- **说明**: 仅在注释中说明 "Does NOT depend on ASR"
- **状态**: ✅ 安全，无需修改

#### 6. `kat_rec_web/backend/t2r/scripts/reset_event_tables.py`
- **行数**: 111-112, 177
- **说明**: 脚本用于重置 ASR 数据库表，这是维护操作
- **状态**: ✅ 安全，保留用于数据库维护

#### 7. `kat_rec_web/backend/t2r/scripts/validate_sqlite_schema.py`
- **行数**: 8-9, 100-140
- **说明**: 验证脚本检查 ASR 表结构，这是维护操作
- **状态**: ✅ 安全，保留用于数据库验证

### 前端文件

#### 8. `kat_rec_web/frontend/components/mcrb/GridProgressSimple.tsx`
- **行数**: 10
- **说明**: 仅在注释中说明 "no ASR dependencies"
- **状态**: ✅ 安全，无需修改

#### 9. `kat_rec_web/frontend/hooks/useVideoProgress.ts`
- **行数**: 10
- **说明**: 仅在注释中说明 "No ASR or registry dependencies"
- **状态**: ✅ 安全，无需修改

#### 10. `kat_rec_web/frontend/utils/assetDetection.ts`
- **行数**: 5, 7
- **说明**: 仅在注释中说明 "Does NOT depend on ASR readiness"
- **状态**: ✅ 安全，无需修改

#### 11. `kat_rec_web/frontend/components/mcrb/OverviewGrid.tsx`
- **行数**: 185, 379, 803, 845, 878, 1064
- **说明**: 仅在注释中说明已替换为文件系统检查
- **状态**: ✅ 安全，无需修改

#### 12. `kat_rec_web/frontend/scripts/atlas-debug-core.js`
- **行数**: 364, 373
- **说明**: 调试脚本中仅提及 ASR snapshot 用于对比，不实际使用
- **状态**: ✅ 安全，保留用于调试

---

## 优先级修复建议

### 🔴 高优先级（立即修复）

1. **filesystem_monitor.py** - 移除 ASR 写入逻辑
2. **auto_complete_episodes.py** - 替换为文件系统检查
3. **render_queue_sync.py** - 替换为文件系统检查
4. **RenderQueuePanel.tsx** - 替换 `calculateStageStatus` 调用
5. **UploadQueuePanel.tsx** - 替换 `calculateStageStatus` 调用

### 🟡 中优先级（逐步移除）

6. **useAssetCheckWorker.ts** - 完全删除或移除 ASR 逻辑
7. **asset_state_service.py** - 移除所有 ASR 写入逻辑
8. **scheduleStore.ts** - 删除已弃用的函数

### 🟢 低优先级（清理）

9. **FileMatrix.tsx** - 重构为使用新 hooks
10. **测试文件** - 更新或删除已弃用函数的测试
11. **文档文件** - 更新以反映新架构

---

## 总结

- **总计**: 27 个文件包含 ASR 引用
- **需要立即修复**: 8 个文件
- **需要逐步移除**: 12 个文件
- **安全保留**: 7 个文件

**下一步行动**: 按照优先级顺序修复 DEFINITELY TO REMOVE 列表中的文件。

