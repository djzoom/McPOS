# Kat Rec 项目清理执行指南

## 🎯 目标

将 Kat Rec 项目整理为**模块化、可迁移、功能边界清晰**的生产级项目。

---

## 📋 执行步骤（按顺序执行）

### 阶段 0：准备工作（30分钟）

#### 0.1 创建备份
```bash
# 创建备份分支
git checkout -b backup/before-cleanup-$(date +%Y%m%d)
git push origin backup/before-cleanup-$(date +%Y%m%d)

# 创建清理工作分支
git checkout -b cleanup/modularization
```

#### 0.2 运行分析脚本
```bash
# 分析项目结构
python3 scripts/analyze_project_structure.py

# 查看分析结果
cat docs/project_structure_analysis.json | python3 -m json.tool
```

---

### 阶段 1：清理明显废弃的目录（1小时）

#### 1.1 删除 `#/` 目录（如果确认废弃）
```bash
# 先检查目录内容
ls -la "#/"

# 如果确认废弃，删除
rm -rf "#/"
git add "#/"
git commit -m "chore: 删除废弃的 #/ 目录"
```

#### 1.2 删除 `desktop/` 目录（如果确认废弃）
```bash
# 先检查目录内容
ls -la desktop/ | head -20

# 如果确认废弃，删除
rm -rf desktop/
git add desktop/
git commit -m "chore: 删除废弃的 desktop/ 目录"
```

#### 1.3 评估 `essentia/` 目录
```bash
# 检查是否仍被使用
grep -r "essentia" mcpos/ scripts/ kat_rec_web/ --include="*.py" | head -10

# 如果不再使用，删除或归档
# 如果仍在使用，保留
```

---

### 阶段 2：清理旧世界脚本（2小时）

#### 2.1 删除已被 McPOS 替代的脚本
```bash
# 删除旧世界封面生成脚本
rm scripts/local_picker/create_mixtape.py
rm scripts/local_picker/batch_generate_covers.py

git add scripts/local_picker/
git commit -m "chore: 删除已被 McPOS 替代的旧世界脚本"
```

#### 2.2 评估其他 local_picker 脚本
```bash
# 检查哪些脚本仍在使用
cd scripts/local_picker
for script in *.py; do
    echo "检查: $script"
    grep -r "$(basename $script .py)" ../.. --include="*.py" --include="*.sh" | grep -v "$script" | head -3
done
```

**保留的脚本**（工具类）：
- `youtube_auth.py` - YouTube 认证工具
- `reauthorize_kat_records_studio.py` - 重新授权工具
- `api_config.py` - API 配置工具
- `episode_status.py` - 期数状态检查

**需要评估的脚本**：
- `create_schedule_master.py` - 如果已被 McPOS 替代，删除
- `remix_mixtape.py` - 如果已被 McPOS 替代，删除
- 其他脚本根据实际使用情况决定

---

### 阶段 3：整理脚本目录（2-3小时）

#### 3.1 创建归档目录
```bash
mkdir -p scripts/archive/{test,fix,debug,old_world}
```

#### 3.2 归档测试脚本
```bash
# 移动测试脚本到归档目录
cd scripts
for script in test_*.py check_*.py; do
    if [ -f "$script" ]; then
        # 检查是否仍在使用
        if ! grep -r "$(basename $script .py)" . --include="*.py" --include="*.sh" | grep -v "$script" | grep -q .; then
            mv "$script" archive/test/
            echo "归档: $script"
        fi
    fi
done

git add scripts/archive/test/
git commit -m "chore: 归档测试脚本到 scripts/archive/test/"
```

#### 3.3 归档一次性修复脚本
```bash
# 移动修复脚本到归档目录
cd scripts
for script in fix_*.py; do
    if [ -f "$script" ]; then
        mv "$script" archive/fix/
        echo "归档: $script"
    fi
done

git add scripts/archive/fix/
git commit -m "chore: 归档一次性修复脚本到 scripts/archive/fix/"
```

#### 3.4 归档调试脚本
```bash
# 移动调试脚本到归档目录
cd scripts
for script in diagnose_*.py; do
    if [ -f "$script" ]; then
        mv "$script" archive/debug/
        echo "归档: $script"
    fi
done

git add scripts/archive/debug/
git commit -m "chore: 归档调试脚本到 scripts/archive/debug/"
```

#### 3.5 保留生产脚本
**保留的脚本**（生产环境使用）：
- `batch_upload_from_date.py` - 批量上传（新）
- `batch_upload_feb_2_7.py` - 批量上传（特定日期）
- `batch_produce_month.py` - 批量制作
- `upload_episodes_direct.py` - 直接上传
- `rerender_episode.py` - 重新渲染
- `scripts/uploader/upload_to_youtube.py` - 上传引擎（核心）

---

### 阶段 4：评估 src/ 目录（2-3小时）

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
如果 `src/` 中的功能已被 McPOS 替代：
1. 标记为"待删除"
2. 更新所有引用
3. 删除 `src/` 目录

如果 `src/` 中的功能仍被使用：
1. 标记为"遗留代码"
2. 计划迁移到 McPOS
3. 暂时保留

---

### 阶段 5：统一配置和日志（1-2小时）

#### 5.1 统一配置管理
```bash
# 检查所有配置模块
find . -name "*config*.py" -type f | grep -v ".venv" | grep -v "__pycache__"

# 确保所有模块使用 mcpos/config.py
grep -r "from.*config" mcpos/ --include="*.py" | head -10
```

#### 5.2 统一日志系统
```bash
# 检查所有日志调用
grep -r "print(" mcpos/core/ mcpos/assets/ --include="*.py" | head -10

# 确保所有模块使用 mcpos/core/logging.py
grep -r "from.*logging" mcpos/ --include="*.py" | head -10
```

---

### 阶段 6：边界模块审计（2-3小时）

#### 6.1 检查 subprocess 违规
```bash
# 检查 core/ 和 assets/ 中是否有 subprocess 导入
grep -r "import subprocess" mcpos/core/ mcpos/assets/ --include="*.py"

# 如果有，需要重构到 adapters/
```

#### 6.2 检查外部 SDK 违规
```bash
# 检查 core/ 和 assets/ 中是否有外部 SDK 导入
grep -r "from openai\|from anthropic\|import ffmpeg\|import youtube" mcpos/core/ mcpos/assets/ --include="*.py"

# 如果有，需要重构到 adapters/
```

#### 6.3 修复违规
对于发现的违规：
1. 创建或更新对应的 adapter
2. 将违规代码移到 adapter
3. 更新调用代码

---

### 阶段 7：验证功能（1-2小时）

#### 7.1 测试完整制播流程
```bash
# 测试单期节目制作
python3 -m mcpos.cli.main run-episode kat kat_20260208

# 验证所有阶段
python3 -m mcpos.cli.main run-stage kat kat_20260208 INIT
python3 -m mcpos.cli.main run-stage kat kat_20260208 TEXT_BASE
python3 -m mcpos.cli.main run-stage kat kat_20260208 COVER
python3 -m mcpos.cli.main run-stage kat kat_20260208 MIX
python3 -m mcpos.cli.main run-stage kat kat_20260208 TEXT_SRT
python3 -m mcpos.cli.main run-stage kat kat_20260208 RENDER
```

#### 7.2 测试批量操作
```bash
# 测试批量上传
python3 scripts/batch_upload_from_date.py --start-date 20260218 --help
```

#### 7.3 测试 Web 后端（如果使用）
```bash
# 启动 Web 后端
cd kat_rec_web
# 测试 API 端点
```

---

### 阶段 8：更新文档（1-2小时）

#### 8.1 更新 README.md
- 更新项目结构说明
- 更新使用指南
- 更新部署说明

#### 8.2 更新架构文档
- 更新模块依赖图
- 更新模块职责说明
- 更新清理后的结构

#### 8.3 创建迁移指南
- 服务器部署指南
- 模块依赖说明
- 配置说明

---

## 📊 清理清单

### 高优先级（立即执行）

- [ ] 删除 `#/` 目录（如果确认废弃）
- [ ] 删除 `desktop/` 目录（如果确认废弃）
- [ ] 删除 `scripts/local_picker/create_mixtape.py`
- [ ] 删除 `scripts/local_picker/batch_generate_covers.py`
- [ ] 归档测试脚本到 `scripts/archive/test/`
- [ ] 归档修复脚本到 `scripts/archive/fix/`
- [ ] 归档调试脚本到 `scripts/archive/debug/`

### 中优先级（本周完成）

- [ ] 评估 `src/` 目录，决定删除或迁移
- [ ] 评估 `essentia/` 目录，决定删除或归档
- [ ] 评估其他 `scripts/local_picker/` 脚本
- [ ] 统一配置管理
- [ ] 统一日志系统

### 低优先级（下周完成）

- [ ] 边界模块审计
- [ ] 修复违规代码
- [ ] 更新文档
- [ ] 创建迁移指南

---

## ⚠️ 注意事项

1. **分阶段执行**：不要一次性删除太多，每步验证
2. **保留备份**：确保可以回滚
3. **测试验证**：每次清理后测试核心功能
4. **文档更新**：及时更新文档

---

## 📈 预期成果

### 清理后统计
- **代码量减少**：预计减少 30-40%
- **模块清晰**：每个模块职责单一
- **易于维护**：清晰的依赖关系
- **可迁移**：可部署到服务器

### 模块统计
- **核心模块**：McPOS（自包含）
- **适配层**：Web 后端、工具脚本
- **数据层**：channels/, images_pool/, config/

---

**预计完成时间**：1-2周
**负责人**：开发团队
