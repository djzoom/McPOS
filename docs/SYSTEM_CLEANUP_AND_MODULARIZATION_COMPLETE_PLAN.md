# Kat Rec 项目系统整理与模块化完整方案

## 📋 执行摘要

本方案旨在将 Kat Rec 项目整理为**模块化、可迁移、功能边界清晰**的生产级项目。通过系统清理和重构，实现：
- ✅ 清晰的模块边界
- ✅ 可部署到服务器环境
- ✅ 易于维护和扩展
- ✅ 功能边界清楚

---

## 🎯 核心原则

### 1. McPOS 是核心
- **McPOS** (`mcpos/`) 是节目制播流程的核心引擎
- 所有其他模块都是适配层，调用 McPOS
- McPOS 自包含，不依赖外部模块

### 2. 文件系统是 SSOT
- 状态从文件系统推导
- 不依赖数据库或外部状态存储
- 所有资产文件在 `channels/<channel_id>/output/<episode_id>/`

### 3. 边界清晰
- **核心层**：McPOS（自包含）
- **适配层**：Web 后端、工具脚本
- **数据层**：channels/, images_pool/, config/

---

## 📊 当前问题分析

### 问题 1：冗余模块
- **src/ 目录**：与 McPOS 功能重叠
- **旧世界脚本**：`create_mixtape.py` 等已被 McPOS 替代
- **重复实现**：多个模块实现相同功能

### 问题 2：废弃代码
- **`#/` 目录**：745个文件，可能是临时目录
- **`desktop/` 目录**：3061个文件，可能废弃
- **一次性脚本**：34个测试/修复/调试脚本

### 问题 3：模块边界不清
- **src/ 和 mcpos/ 功能重叠**
- **脚本目录混乱**：生产脚本和测试脚本混杂
- **依赖关系复杂**：模块间相互依赖

---

## 🏗️ 目标架构

### 模块化架构图

```
kat_rec/
├── mcpos/                          # 核心引擎（自包含）
│   ├── core/                       # 核心逻辑
│   │   ├── pipeline.py             # 主流程引擎
│   │   ├── logging.py              # 统一日志
│   │   └── state.py                # 状态管理
│   ├── assets/                     # 阶段实现
│   │   ├── init.py                 # INIT 阶段
│   │   ├── text.py                 # TEXT_BASE/TEXT_SRT 阶段
│   │   ├── cover.py                # COVER 阶段
│   │   ├── mix.py                  # MIX 阶段
│   │   └── render.py               # RENDER 阶段
│   ├── adapters/                   # 边界适配器
│   │   ├── render_engine.py        # 视频渲染
│   │   ├── mix_engine.py           # 音频混音
│   │   ├── uploader.py             # 上传引擎
│   │   ├── ai_title_generator.py   # AI 标题生成
│   │   └── filesystem.py           # 文件系统适配
│   ├── cli/                        # 命令行接口
│   │   └── main.py                 # CLI 主入口
│   └── Doc/                         # 文档
│
├── kat_rec_web/                    # Web 服务（适配层）
│   ├── backend/                     # FastAPI 后端
│   │   ├── t2r/                     # T2R 业务逻辑
│   │   │   ├── routes/              # API 路由
│   │   │   ├── services/            # 业务服务
│   │   │   └── plugins/             # 插件系统
│   │   └── routes/                  # 其他路由
│   └── frontend/                    # React 前端
│
├── scripts/                         # 工具脚本（精简）
│   ├── uploader/                    # 上传引擎（核心）
│   │   └── upload_to_youtube.py     # YouTube 上传核心
│   ├── batch_*.py                   # 批量操作脚本
│   ├── upload_*.py                  # 上传脚本
│   └── archive/                      # 归档脚本
│       ├── test/                     # 测试脚本
│       ├── fix/                      # 修复脚本
│       └── debug/                    # 调试脚本
│
├── channels/                        # 频道数据（SSOT）
│   ├── kat/
│   │   ├── library/                 # 曲库
│   │   └── output/                  # 输出目录
│   └── rbr/
│
├── images_pool/                     # 图片池（SSOT）
│   ├── available/                   # 可用图片
│   └── used/                        # 已使用图片
│
├── config/                          # 配置文件
│   ├── config.yaml                  # 主配置
│   └── google/                      # Google API 配置
│
└── docs/                            # 项目文档
```

### 模块职责划分

#### 1. McPOS 核心（自包含）
- **职责**：节目制播流程的核心引擎
- **接口**：`run_episode(spec) -> EpisodeState`
- **依赖**：文件系统、配置、adapters
- **禁止**：导入 `src/`, `scripts/`, `kat_rec_web/`

#### 2. Web 后端（适配层）
- **职责**：提供 Web API，调用 McPOS
- **接口**：REST API、WebSocket
- **依赖**：McPOS、FastAPI
- **禁止**：直接实现制播逻辑（应调用 McPOS）

#### 3. 工具脚本（精简）
- **职责**：批量操作、一次性任务
- **接口**：命令行参数
- **依赖**：McPOS、上传引擎
- **禁止**：重复实现 McPOS 功能

---

## 📋 详细清理清单

### 阶段 1：删除废弃目录（高优先级）

#### 1.1 删除 `#/` 目录
```bash
# 检查目录内容
ls -la "#/" | head -20

# 如果确认废弃，删除
rm -rf "#/"
git add "#/"
git commit -m "chore: 删除废弃的 #/ 目录"
```

**风险评估**：低（临时目录）

#### 1.2 删除 `desktop/` 目录
```bash
# 检查目录内容
ls -la desktop/ | head -20

# 如果确认废弃，删除
rm -rf desktop/
git add desktop/
git commit -m "chore: 删除废弃的 desktop/ 目录"
```

**风险评估**：中（需要确认是否仍在使用）

#### 1.3 评估 `essentia/` 目录
```bash
# 检查是否仍被使用
grep -r "essentia" mcpos/ scripts/ kat_rec_web/ --include="*.py" | head -10

# 如果不再使用，删除或归档
# 如果仍在使用，保留
```

**风险评估**：中（需要确认依赖关系）

---

### 阶段 2：清理旧世界脚本（高优先级）

#### 2.1 删除已被 McPOS 替代的脚本
```bash
# 删除旧世界封面生成脚本
rm scripts/local_picker/create_mixtape.py
rm scripts/local_picker/batch_generate_covers.py

git add scripts/local_picker/
git commit -m "chore: 删除已被 McPOS 替代的旧世界脚本"
```

**风险评估**：低（已被 McPOS 完全替代）

#### 2.2 评估其他 local_picker 脚本

**保留的脚本**（工具类）：
- ✅ `youtube_auth.py` - YouTube 认证工具
- ✅ `reauthorize_kat_records_studio.py` - 重新授权工具
- ✅ `api_config.py` - API 配置工具
- ✅ `episode_status.py` - 期数状态检查

**需要评估的脚本**：
- ⚠️ `create_schedule_master.py` - 如果已被 McPOS 替代，删除
- ⚠️ `remix_mixtape.py` - 如果已被 McPOS 替代，删除
- ⚠️ 其他脚本根据实际使用情况决定

---

### 阶段 3：整理脚本目录（中优先级）

#### 3.1 创建归档目录
```bash
mkdir -p scripts/archive/{test,fix,debug,deprecated}
```

#### 3.2 归档测试脚本（24个）
```bash
# 使用自动生成的脚本
bash scripts/execute_cleanup.sh

# 或手动归档
cd scripts
for script in test_*.py check_*.py; do
    if [ -f "$script" ]; then
        mv "$script" archive/test/
    fi
done
```

**归档的脚本**：
- `test_*.py` - 测试脚本
- `check_*.py` - 检查脚本（非生产用）

#### 3.3 归档修复脚本（6个）
```bash
cd scripts
for script in fix_*.py; do
    if [ -f "$script" ]; then
        mv "$script" archive/fix/
    fi
done
```

#### 3.4 归档调试脚本（3个）
```bash
cd scripts
for script in diagnose_*.py; do
    if [ -f "$script" ]; then
        mv "$script" archive/debug/
    fi
done
```

#### 3.5 保留生产脚本（26个）
**保留的脚本**（生产环境使用）：
- ✅ `batch_upload_from_date.py` - 批量上传（新，推荐）
- ✅ `batch_upload_feb_2_7.py` - 批量上传（特定日期）
- ✅ `batch_produce_month.py` - 批量制作
- ✅ `upload_episodes_direct.py` - 直接上传
- ✅ `rerender_episode.py` - 重新渲染
- ✅ `scripts/uploader/upload_to_youtube.py` - 上传引擎（核心）

---

### 阶段 4：评估 src/ 目录（中优先级）

#### 4.1 分析依赖关系
```bash
# 检查哪些模块依赖 src/
grep -r "from src\." . --include="*.py" | grep -v "src/" | head -20
grep -r "import src\." . --include="*.py" | grep -v "src/" | head -20
```

#### 4.2 检查功能重叠
```bash
# 比较 src/core/ 和 mcpos/core/ 的功能
diff -r src/core/ mcpos/core/ --brief
```

#### 4.3 迁移计划

**如果 `src/` 中的功能已被 McPOS 替代**：
1. ✅ 标记为"待删除"
2. ✅ 更新所有引用
3. ✅ 删除 `src/` 目录

**如果 `src/` 中的功能仍被使用**：
1. ⚠️ 标记为"遗留代码"
2. ⚠️ 计划迁移到 McPOS
3. ⚠️ 暂时保留

---

### 阶段 5：统一配置和日志（低优先级）

#### 5.1 统一配置管理
- ✅ 所有模块使用 `mcpos/config.py`
- ❌ 删除重复的配置模块
- ✅ 确保配置路径统一

#### 5.2 统一日志系统
- ✅ 所有模块使用 `mcpos/core/logging.py`
- ❌ 删除重复的日志模块
- ✅ 确保日志格式统一

---

### 阶段 6：边界模块审计（低优先级）

#### 6.1 检查 subprocess 违规
```bash
# 检查 core/ 和 assets/ 中是否有 subprocess 导入
grep -r "import subprocess" mcpos/core/ mcpos/assets/ --include="*.py"
```

**如果发现违规**：
1. 创建或更新对应的 adapter
2. 将违规代码移到 adapter
3. 更新调用代码

#### 6.2 检查外部 SDK 违规
```bash
# 检查 core/ 和 assets/ 中是否有外部 SDK 导入
grep -r "from openai\|from anthropic\|import ffmpeg\|import youtube" mcpos/core/ mcpos/assets/ --include="*.py"
```

**如果发现违规**：
1. 创建或更新对应的 adapter
2. 将违规代码移到 adapter
3. 更新调用代码

---

## 🚀 执行步骤（按顺序）

### 第 1 天：准备和分析

1. **创建备份分支**
   ```bash
   git checkout -b backup/before-cleanup-$(date +%Y%m%d)
   git push origin backup/before-cleanup-$(date +%Y%m%d)
   ```

2. **运行分析脚本**
   ```bash
   python3 scripts/analyze_project_structure.py
   python3 scripts/create_cleanup_plan.py
   ```

3. **审查清理计划**
   ```bash
   cat docs/cleanup_plan.json | python3 -m json.tool
   ```

### 第 2-3 天：清理废弃代码

1. **删除废弃目录**
   ```bash
   # 确认后删除
   rm -rf "#/" desktop/
   ```

2. **删除旧世界脚本**
   ```bash
   rm scripts/local_picker/create_mixtape.py
   rm scripts/local_picker/batch_generate_covers.py
   ```

3. **归档测试/修复/调试脚本**
   ```bash
   bash scripts/execute_cleanup.sh
   ```

### 第 4-5 天：评估和重构

1. **评估 src/ 目录**
   - 分析依赖关系
   - 决定删除或迁移

2. **统一配置和日志**
   - 统一使用 `mcpos/config.py`
   - 统一使用 `mcpos/core/logging.py`

3. **边界模块审计**
   - 检查违规代码
   - 修复违规代码

### 第 6-7 天：验证和文档

1. **功能验证**
   ```bash
   # 测试完整流程
   python3 -m mcpos.cli.main run-episode kat kat_20260208
   
   # 测试批量操作
   python3 scripts/batch_upload_from_date.py --start-date 20260218 --help
   ```

2. **更新文档**
   - 更新 README.md
   - 更新架构文档
   - 创建迁移指南

---

## 📊 清理统计

### 预期清理结果

- **删除目录**：2个（`#/`, `desktop/`）
- **删除文件**：2个（旧世界脚本）
- **归档脚本**：35个（测试/修复/调试脚本）
- **代码量减少**：预计减少 30-40%

### 清理后结构

- **核心模块**：McPOS（69个文件，自包含）
- **适配层**：Web 后端、工具脚本
- **数据层**：channels/, images_pool/, config/

---

## ⚠️ 风险控制

### 1. 备份策略
- ✅ 创建备份分支
- ✅ 每次清理前提交
- ✅ 保留清理历史

### 2. 验证策略
- ✅ 每次清理后测试核心功能
- ✅ 分阶段执行，逐步验证
- ✅ 保留回滚能力

### 3. 文档策略
- ✅ 及时更新文档
- ✅ 记录所有变更
- ✅ 创建迁移指南

---

## 🎯 成功标准

### 清理完成标准

1. ✅ **模块边界清晰**：McPOS 自包含，其他模块是适配层
2. ✅ **无冗余代码**：删除所有废弃代码和重复实现
3. ✅ **功能完整**：所有核心功能正常工作
4. ✅ **可迁移**：可以部署到服务器环境
5. ✅ **文档完整**：架构文档和迁移指南完整

### 验证方法

1. **功能测试**
   ```bash
   # 测试完整制播流程
   python3 -m mcpos.cli.main run-episode kat kat_20260208
   ```

2. **依赖检查**
   ```bash
   # 检查 McPOS 是否违反 Dev_Bible
   grep -r "from src\|from scripts\|from kat_rec_web" mcpos/ --include="*.py"
   ```

3. **边界审计**
   ```bash
   # 检查 subprocess 违规
   grep -r "import subprocess" mcpos/core/ mcpos/assets/ --include="*.py"
   ```

---

## 📝 下一步行动

### 立即执行（今天）

1. ✅ 创建备份分支
2. ✅ 运行分析脚本
3. ✅ 审查清理计划

### 本周完成

1. ✅ 删除废弃目录（`#/`, `desktop/`）
2. ✅ 删除旧世界脚本
3. ✅ 归档测试/修复/调试脚本

### 下周完成

1. ⚠️ 评估 `src/` 目录
2. ⚠️ 统一配置和日志
3. ⚠️ 边界模块审计
4. ⚠️ 更新文档

---

## 📚 相关文档

- **清理计划**：`docs/PROJECT_CLEANUP_AND_MODULARIZATION_PLAN.md`
- **执行指南**：`docs/CLEANUP_EXECUTION_GUIDE.md`
- **项目分析**：`docs/project_structure_analysis.json`
- **清理清单**：`docs/cleanup_plan.json`
- **Dev_Bible**：`mcpos/Dev_Bible.md`

---

**报告生成时间**：2026-01-26
**预计完成时间**：1-2周
**负责人**：开发团队
