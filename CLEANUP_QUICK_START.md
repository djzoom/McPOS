# Kat Rec 项目清理快速开始指南

## 🚀 立即执行（5分钟）

### 1. 创建备份
```bash
git checkout -b backup/before-cleanup-$(date +%Y%m%d)
git push origin backup/before-cleanup-$(date +%Y%m%d)
git checkout -b cleanup/modularization
```

### 2. 运行分析
```bash
python3 scripts/analyze_project_structure.py
python3 scripts/create_cleanup_plan.py
```

### 3. 查看清理计划
```bash
cat docs/cleanup_plan.json | python3 -m json.tool | head -50
```

---

## 📋 清理清单（按优先级）

### 高优先级（立即执行）

#### ✅ 删除废弃目录
```bash
# 确认后删除
rm -rf "#/" desktop/
git add "#/" desktop/
git commit -m "chore: 删除废弃目录 #/ 和 desktop/"
```

#### ✅ 删除旧世界脚本
```bash
rm scripts/local_picker/create_mixtape.py
rm scripts/local_picker/batch_generate_covers.py
git add scripts/local_picker/
git commit -m "chore: 删除已被 McPOS 替代的旧世界脚本"
```

#### ✅ 归档测试/修复/调试脚本
```bash
bash scripts/execute_cleanup.sh
git add scripts/archive/
git commit -m "chore: 归档测试/修复/调试脚本"
```

### 中优先级（本周完成）

#### ⚠️ 评估 src/ 目录
```bash
# 检查依赖关系
grep -r "from src\." . --include="*.py" | grep -v "src/" | head -20

# 如果功能已被 McPOS 替代，删除
# 如果仍在使用，标记为"遗留代码"
```

#### ⚠️ 评估 essentia/ 目录
```bash
# 检查是否仍被使用
grep -r "essentia" mcpos/ scripts/ kat_rec_web/ --include="*.py" | head -10

# 如果不再使用，删除或归档
```

### 低优先级（下周完成）

#### 📝 统一配置和日志
- 确保所有模块使用 `mcpos/config.py`
- 确保所有模块使用 `mcpos/core/logging.py`

#### 🔍 边界模块审计
```bash
# 检查违规
grep -r "import subprocess" mcpos/core/ mcpos/assets/ --include="*.py"
grep -r "from openai\|from anthropic" mcpos/core/ mcpos/assets/ --include="*.py"
```

---

## ✅ 验证步骤

### 1. 测试核心功能
```bash
# 测试完整制播流程
python3 -m mcpos.cli.main run-episode kat kat_20260208
```

### 2. 测试批量操作
```bash
# 测试批量上传
python3 scripts/batch_upload_from_date.py --start-date 20260218 --help
```

### 3. 检查依赖关系
```bash
# 检查 McPOS 是否违反 Dev_Bible
grep -r "from src\|from scripts\|from kat_rec_web" mcpos/ --include="*.py"
```

---

## 📚 详细文档

- **完整方案**：`docs/SYSTEM_CLEANUP_AND_MODULARIZATION_COMPLETE_PLAN.md`
- **执行指南**：`docs/CLEANUP_EXECUTION_GUIDE.md`
- **清理计划**：`docs/PROJECT_CLEANUP_AND_MODULARIZATION_PLAN.md`

---

## ⚠️ 注意事项

1. **分阶段执行**：不要一次性删除太多
2. **保留备份**：确保可以回滚
3. **测试验证**：每次清理后测试核心功能
4. **文档更新**：及时更新文档

---

**预计完成时间**：1-2周
**开始执行**：立即开始
