# 项目清理日志

**日期**: 2025-11-XX  
**阶段**: Phase IV - 架构收尾与一致性治理

## 📋 清理目标

本文档记录在一致性审计过程中发现的过期文件、未使用的导入、以及需要更新的文档引用。

---

## 🗂️ 过期文件清单

### 标记为已弃用（仍在使用，需迁移）

以下文件已标记为已弃用，但仍有部分代码在使用，需要逐步迁移：

1. **`config/schedule_master.json（新架构单一数据源）`**
   - **状态**: 已弃用
   - **原因**: 统一状态架构以`schedule_master.json`为单一数据源
   - **替代方案**: 使用`state_manager`查询状态，或通过`unified_sync.py`从文件系统重建
   - **使用位置**:
     - `scripts/local_picker/create_schedule_with_confirmation.py`
     - `scripts/local_picker/modify_schedule.py`
     - `scripts/local_picker/create_mixtape.py`
     - `scripts/local_picker/batch_generate_videos.py`
     - `scripts/local_picker/unified_sync.py`
   - **迁移计划**: 逐步替换为`state_manager`调用

2. **`data/schedule_master.json动态查询（已弃用独立文件）`**
   - **状态**: 已弃用
   - **原因**: 应从`schedule_master.json`动态查询，不需要独立文件
   - **替代方案**: 使用`state_manager.get_all_used_tracks()`动态查询
   - **迁移计划**: 删除文件，所有查询通过状态管理器

3. **`scripts/local_picker/state_manager（已迁移）.py`**
   - **状态**: 已弃用但保留（向后兼容）
   - **原因**: 旧代码仍在使用，但新代码应使用`state_manager`
   - **替代方案**: 使用`src/core/state_manager.py`
   - **保留原因**: 确保向后兼容性，允许旧代码继续运行

### 已确认可删除

4. **`config/pppschedule_master.json（新架构单一数据源）`** (如果存在)
   - **状态**: 可删除
   - **原因**: 重复或错误命名的文件

5. **`scripts/local_picker/unified_sync.py（已替代）`** (如果不再使用)
   - **状态**: 待确认
   - **原因**: 已由`unified_sync.py`替代
   - **需要验证**: 确认没有其他脚本引用

---

## 📝 文档更新需求

### 需要更新的文档

1. **`docs/PRODUCTION_LOG.md`**
   - 添加"已弃用"标记
   - 更新为推荐使用`state_manager`
   - 说明通过`unified_sync.py`重建的方法

2. **`docs/SCHEDULE_CREATION_WITH_CONFIRMATION.md`**
   - 检查是否引用`schedule_master.json（新架构单一数据源）`
   - 更新为新架构说明

3. **`README.md`**
   - 更新状态管理架构说明
   - 移除对`schedule_master.json（新架构单一数据源）`的直接引用

4. **`docs/COMMAND_LINE_WORKFLOW.md`**
   - 更新命令示例，使用新架构

---

## 🔧 代码清理需求

### 未使用的导入

需要检查并清理以下文件中的未使用导入：

1. `scripts/local_picker/create_mixtape.py`
   - 检查是否有未使用的`state_manager（已迁移）`导入
   - 检查是否有未使用的其他导入

2. `scripts/local_picker/batch_generate_videos.py`
   - 检查`state_manager（已迁移）`使用情况

3. `scripts/local_picker/modify_schedule.py`
   - 检查是否仍在使用旧的状态更新方式

### 函数签名一致性

需要验证以下函数签名在各模块中保持一致：

1. **状态更新函数**
   - `state_manager.update_status()` - 核心实现
   - 确保所有调用点参数一致

2. **回滚函数**
   - `state_manager.rollback_status()` - 核心实现
   - 确保所有调用点参数一致

3. **指标记录函数**
   - `metrics_manager.record_event()` - 核心实现
   - 确保所有调用点参数一致

---

## 🧪 测试覆盖

### 新增测试需求

1. **`tests/test_consistency.py`** ✅ 已创建
   - 模块导入测试
   - CLI命令测试
   - JSON模式测试
   - 函数签名测试
   - 冒烟测试

2. **状态管理器一致性测试**
   - 验证所有状态转换
   - 验证并发安全性
   - 验证回滚机制

---

## 📊 清理统计

### 文件统计

- **过期文件**: 2个（`schedule_master.json（新架构单一数据源）`, `schedule_master.json动态查询（已弃用独立文件）`）
- **弃用但保留**: 1个（`state_manager（已迁移）.py`）
- **待验证**: 1个（`unified_sync.py（已替代）`）

### 代码迁移

- **需要迁移的模块**: 约5-8个
- **需要更新的文档**: 约4个
- **需要清理的导入**: 待统计

---

## ✅ 清理检查清单

- [ ] 运行审计工具生成完整报告
- [ ] 更新所有文档引用
- [ ] 迁移`state_manager（已迁移）`调用到`state_manager`
- [ ] 清理未使用的导入
- [ ] 验证函数签名一致性
- [ ] 运行一致性测试套件
- [ ] 验证CLI命令对齐
- [ ] 更新`state_refactor.md`文档

---

## 🚀 清理计划

### 阶段1: 文档更新（低风险）
1. 更新所有文档，标记已弃用内容
2. 添加迁移指南

### 阶段2: 代码迁移（中风险）
1. 逐步迁移`state_manager（已迁移）`调用
2. 保持向后兼容性
3. 运行测试确保无破坏

### 阶段3: 清理删除（高风险）
1. 确认所有代码已迁移
2. 删除过期文件
3. 清理未使用导入
4. 最终验证

---

## 📌 注意事项

1. **向后兼容**: 在完全迁移前，保持`state_manager（已迁移）.py`可用
2. **渐进式迁移**: 不要一次性删除所有旧代码
3. **测试验证**: 每次迁移后运行测试套件
4. **文档同步**: 确保文档与实际代码一致

---

## 🔗 相关文档

- [系统架构文档](./ARCHITECTURE.md) - 统一状态管理架构说明
- [开发日志](./DEVELOPMENT.md) - 开发进展和成就
- [路线图](./ROADMAP.md) - 未来计划和改进方向

**注意**: 本文档已归档，历史内容请查看 [archive/](./archive/) 目录

