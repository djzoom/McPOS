# Kat Rec 项目系统整理与模块化方案

## 📋 执行摘要

本方案旨在将 Kat Rec 项目整理为**模块化、可迁移、功能边界清晰**的生产级项目，清理冗余代码、废弃文件和旧世界组件。

---

## 🎯 目标

1. **模块化**：清晰的模块边界，易于理解和维护
2. **可迁移**：可部署到服务器环境
3. **功能边界清楚**：每个模块职责单一明确
4. **清理冗余**：删除废弃代码和中间过程文件
5. **统一架构**：以 McPOS 为核心，其他模块作为适配层

---

## 📊 当前项目结构分析

### 核心模块（保留）

#### 1. **McPOS 核心** ⭐⭐⭐⭐⭐
**位置**：`mcpos/`
**状态**：✅ 核心，必须保留
**职责**：
- 节目制播流程的核心引擎
- 阶段化处理：INIT → TEXT_BASE → COVER → MIX → TEXT_SRT → RENDER
- 文件系统作为 SSOT（Single Source of Truth）
- 自包含，不依赖外部模块

**关键文件**：
- `mcpos/core/pipeline.py` - 主流程引擎
- `mcpos/assets/*.py` - 各阶段实现
- `mcpos/adapters/*.py` - 边界适配器
- `mcpos/cli/main.py` - 命令行接口

#### 2. **Web 后端** ⭐⭐⭐⭐
**位置**：`kat_rec_web/backend/`
**状态**：✅ 保留，作为 McPOS 的 Web 适配层
**职责**：
- FastAPI Web 服务
- 提供 REST API 和 WebSocket
- 调用 McPOS 核心功能
- 队列管理和任务调度

**关键文件**：
- `kat_rec_web/backend/t2r/routes/*.py` - API 路由
- `kat_rec_web/backend/t2r/services/*.py` - 业务服务
- `kat_rec_web/backend/t2r/plugins/*.py` - 插件系统

#### 3. **Web 前端** ⭐⭐⭐⭐
**位置**：`kat_rec_web/frontend/`
**状态**：✅ 保留
**职责**：
- React/TypeScript 前端界面
- 用户交互和可视化

#### 4. **上传引擎** ⭐⭐⭐⭐⭐
**位置**：`scripts/uploader/upload_to_youtube.py`
**状态**：✅ 核心，必须保留
**职责**：
- YouTube 上传的核心实现
- 被 McPOS uploader 和 Web 后端调用

---

### 冗余/废弃模块（需要清理）

#### 1. **旧世界脚本** ⚠️ 需要评估
**位置**：`scripts/local_picker/`
**状态**：⚠️ 部分废弃，需要评估
**问题**：
- `create_mixtape.py` (2833行) - 旧世界封面生成，已被 McPOS 替代
- `batch_generate_covers.py` - 依赖旧世界脚本
- 其他旧世界工具脚本

**建议**：
- ✅ 保留：`youtube_auth.py`, `reauthorize_kat_records_studio.py` 等工具脚本
- ❌ 删除：`create_mixtape.py`, `batch_generate_covers.py` 等已被 McPOS 替代的脚本
- ⚠️ 评估：其他脚本，确认是否仍在使用

#### 2. **src/ 目录** ⚠️ 需要评估
**位置**：`src/`
**状态**：⚠️ 可能冗余
**问题**：
- 与 McPOS 功能重叠
- `src/core/` 与 `mcpos/core/` 功能重复
- `src/configuration.py` 与 `mcpos/config.py` 可能重复

**建议**：
- ✅ 保留：如果被 Web 后端或旧脚本依赖
- ❌ 删除：如果功能已被 McPOS 完全替代
- ⚠️ 评估：检查依赖关系，逐步迁移到 McPOS

#### 3. **中间过程脚本** ⚠️ 需要清理
**位置**：`scripts/`
**状态**：⚠️ 大量一次性脚本
**问题**：
- 大量测试脚本（`test_*.py`, `check_*.py`）
- 一次性修复脚本（`fix_*.py`）
- 调试脚本（`diagnose_*.py`）

**建议**：
- ✅ 保留：生产环境使用的脚本（如 `batch_upload_from_date.py`）
- ❌ 删除：一次性测试/修复脚本
- 📦 归档：历史脚本移至 `scripts/archive/`

#### 4. **废弃目录** ❌ 需要删除
**位置**：多个
**状态**：❌ 废弃
**问题**：
- `#/` 目录（745个文件）- 可能是临时目录
- `desktop/` 目录（3061个文件）- 可能废弃
- `essentia/` 目录（2114个文件）- 如果不再使用

**建议**：
- ❌ 删除：确认废弃后删除
- 📦 归档：如果不确定，先归档

---

## 🗂️ 模块化架构设计

### 目标架构

```
kat_rec/
├── mcpos/                    # 核心引擎（自包含）
│   ├── core/                 # 核心逻辑
│   ├── assets/               # 阶段实现
│   ├── adapters/              # 边界适配器
│   ├── cli/                   # 命令行接口
│   └── Doc/                   # 文档
│
├── kat_rec_web/              # Web 服务（适配层）
│   ├── backend/               # FastAPI 后端
│   │   ├── t2r/               # T2R 业务逻辑
│   │   └── routes/            # API 路由
│   └── frontend/              # React 前端
│
├── scripts/                   # 工具脚本（精简）
│   ├── uploader/              # 上传引擎（核心）
│   ├── batch_*.py             # 批量操作脚本
│   └── archive/                # 归档脚本
│
├── channels/                  # 频道数据（SSOT）
│   ├── kat/
│   └── rbr/
│
├── images_pool/               # 图片池（SSOT）
│   ├── available/
│   └── used/
│
├── config/                    # 配置文件
│   ├── config.yaml
│   └── google/
│
├── docs/                      # 项目文档
│
└── requirements.txt           # 依赖管理
```

### 模块边界定义

#### 1. **McPOS 核心**（自包含）
- **职责**：节目制播流程的核心引擎
- **边界**：
  - ✅ 可以：文件 I/O、subprocess 调用（通过 adapters）、被外部导入
  - ❌ 禁止：导入 `src/`, `scripts/`, `kat_rec_web/`
- **依赖**：标准库、PIL、配置文件和文件系统

#### 2. **Web 后端**（适配层）
- **职责**：提供 Web API，调用 McPOS
- **边界**：
  - ✅ 可以：导入 McPOS、提供 REST API、队列管理
  - ❌ 禁止：直接实现制播逻辑（应调用 McPOS）
- **依赖**：McPOS、FastAPI、WebSocket

#### 3. **工具脚本**（精简）
- **职责**：批量操作、一次性任务
- **边界**：
  - ✅ 可以：导入 McPOS、调用上传引擎
  - ❌ 禁止：重复实现 McPOS 功能
- **依赖**：McPOS、上传引擎

---

## 📝 清理计划（分阶段执行）

### 阶段 1：识别和分类（1-2天）

#### 1.1 分析依赖关系
```bash
# 检查哪些文件被实际使用
# 检查导入关系
# 识别废弃代码
```

#### 1.2 创建清理清单
- [ ] 列出所有需要删除的文件
- [ ] 列出所有需要归档的文件
- [ ] 列出所有需要重构的文件

#### 1.3 验证核心功能
- [ ] 确认 McPOS 核心功能完整
- [ ] 确认 Web 后端功能完整
- [ ] 确认上传功能完整

### 阶段 2：清理废弃代码（2-3天）

#### 2.1 删除废弃目录
- [ ] 删除 `#/` 目录（如果确认废弃）
- [ ] 删除 `desktop/` 目录（如果确认废弃）
- [ ] 评估 `essentia/` 目录（如果不再使用，删除或归档）

#### 2.2 清理旧世界脚本
- [ ] 删除 `scripts/local_picker/create_mixtape.py`
- [ ] 删除 `scripts/local_picker/batch_generate_covers.py`
- [ ] 评估其他 `scripts/local_picker/` 脚本

#### 2.3 清理测试/调试脚本
- [ ] 归档一次性测试脚本到 `scripts/archive/test/`
- [ ] 归档一次性修复脚本到 `scripts/archive/fix/`
- [ ] 归档调试脚本到 `scripts/archive/debug/`

#### 2.4 清理 src/ 目录
- [ ] 检查 `src/` 目录的依赖关系
- [ ] 如果功能已被 McPOS 替代，删除或归档
- [ ] 如果仍被使用，标记为"待迁移"

### 阶段 3：模块化重构（3-5天）

#### 3.1 统一配置管理
- [ ] 统一使用 `mcpos/config.py`
- [ ] 删除重复的配置模块
- [ ] 确保配置路径统一

#### 3.2 统一日志系统
- [ ] 所有模块使用 `mcpos/core/logging.py`
- [ ] 删除重复的日志模块
- [ ] 确保日志格式统一

#### 3.3 清理重复功能
- [ ] 合并重复的状态管理代码
- [ ] 合并重复的文件检测代码
- [ ] 统一错误处理

#### 3.4 边界模块审计
- [ ] 确保所有 subprocess 调用都在 adapters 中
- [ ] 确保所有外部 SDK 调用都在 adapters 中
- [ ] 修复违反 Dev_Bible 的代码

### 阶段 4：文档和测试（2-3天）

#### 4.1 更新文档
- [ ] 更新 README.md
- [ ] 更新架构文档
- [ ] 更新部署文档

#### 4.2 创建迁移指南
- [ ] 服务器部署指南
- [ ] 模块依赖说明
- [ ] 配置说明

#### 4.3 验证功能
- [ ] 测试完整制播流程
- [ ] 测试批量操作
- [ ] 测试上传功能

---

## 🔍 详细清理清单

### 需要删除的文件/目录

#### 高优先级（确认废弃）
1. **`#/` 目录** - 745个文件，可能是临时目录
2. **`desktop/` 目录** - 3061个文件，可能废弃
3. **`scripts/local_picker/create_mixtape.py`** - 2833行，已被 McPOS 替代
4. **`scripts/local_picker/batch_generate_covers.py`** - 依赖旧世界脚本

#### 中优先级（需要评估）
1. **`src/` 目录** - 检查是否仍被使用
2. **`essentia/` 目录** - 如果不再使用
3. **`scripts/archive_rename/`** - 如果重命名已完成
4. **一次性测试脚本** - `test_*.py`, `check_*.py`（非生产用）

#### 低优先级（归档而非删除）
1. **历史文档** - 移至 `docs/archive/`
2. **旧脚本** - 移至 `scripts/archive/`

### 需要重构的模块

#### 1. **src/ 目录重构**
- **问题**：与 McPOS 功能重叠
- **方案**：
  - 如果功能已被 McPOS 替代：删除
  - 如果仍被使用：标记为"待迁移"，逐步迁移到 McPOS
  - 如果 Web 后端依赖：保留但标记为"遗留代码"

#### 2. **脚本目录整理**
- **问题**：大量一次性脚本混杂
- **方案**：
  - 保留生产脚本：`batch_*.py`, `upload_*.py` 等
  - 归档测试脚本：移至 `scripts/archive/test/`
  - 归档修复脚本：移至 `scripts/archive/fix/`
  - 删除明显废弃的脚本

#### 3. **配置统一**
- **问题**：多个配置模块
- **方案**：
  - 统一使用 `mcpos/config.py`
  - 其他配置模块作为适配层或删除

---

## 🏗️ 模块化架构设计

### 核心原则

1. **McPOS 是核心**：所有制播逻辑在 McPOS 中
2. **其他模块是适配层**：Web 后端、脚本都是适配层
3. **文件系统是 SSOT**：状态从文件系统推导
4. **边界清晰**：模块间通过明确的接口交互

### 模块依赖图

```
┌─────────────────┐
│   Web Frontend  │
└────────┬────────┘
         │
┌────────▼────────┐
│  Web Backend    │ ──┐
│  (FastAPI)      │   │
└────────┬────────┘   │
         │            │ 调用
         │            │
┌────────▼────────┐   │
│  McPOS Core     │◄──┘
│  (Pipeline)     │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐  ┌──▼────┐
│Adapters│  │Assets│
└────────┘  └──────┘
    │
┌───▼──────────────┐
│ External Tools   │
│ (ffmpeg, API)    │
└──────────────────┘
```

### 模块职责划分

#### McPOS 核心
- **职责**：制播流程引擎
- **接口**：`run_episode(spec) -> EpisodeState`
- **依赖**：文件系统、配置、adapters

#### Web 后端
- **职责**：提供 Web API
- **接口**：REST API、WebSocket
- **依赖**：McPOS、FastAPI

#### 工具脚本
- **职责**：批量操作、一次性任务
- **接口**：命令行参数
- **依赖**：McPOS、上传引擎

---

## 📋 执行步骤

### 第一步：创建备份和分支
```bash
# 创建备份分支
git checkout -b backup/before-cleanup
git push origin backup/before-cleanup

# 创建清理分支
git checkout -b cleanup/modularization
```

### 第二步：分析依赖关系
```bash
# 分析导入关系
python scripts/analyze_dependencies.py

# 识别废弃代码
python scripts/find_unused_code.py
```

### 第三步：逐步清理
1. 先删除明显废弃的目录（`#/`, `desktop/`）
2. 再清理旧世界脚本
3. 最后整理脚本目录

### 第四步：验证功能
```bash
# 测试完整流程
python -m mcpos.cli.main run-episode kat kat_20260208

# 测试批量操作
python scripts/batch_upload_from_date.py --start-date 20260208
```

### 第五步：更新文档
- 更新 README.md
- 更新架构文档
- 创建迁移指南

---

## ⚠️ 注意事项

1. **不要一次性删除太多**：分阶段执行，每步验证
2. **保留备份**：创建备份分支，确保可以回滚
3. **测试验证**：每次清理后测试核心功能
4. **文档更新**：及时更新文档，记录变更

---

## 📊 预期成果

### 清理后项目结构
- **代码量减少**：预计减少 30-40% 的冗余代码
- **模块清晰**：每个模块职责单一明确
- **易于维护**：清晰的依赖关系
- **可迁移**：可部署到服务器环境

### 模块统计
- **核心模块**：McPOS（自包含）
- **适配层**：Web 后端、工具脚本
- **数据层**：channels/, images_pool/, config/

---

## 🎯 下一步行动

1. **立即执行**：创建备份分支
2. **本周完成**：阶段 1-2（识别和清理废弃代码）
3. **下周完成**：阶段 3-4（模块化重构和文档）

---

**报告生成时间**：2026-01-26
**预计完成时间**：2-3周
**负责人**：开发团队
