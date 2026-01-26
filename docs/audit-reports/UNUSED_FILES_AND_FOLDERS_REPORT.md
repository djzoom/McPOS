# 无用文件和文件夹检查报告

**生成时间**: 2025-11-16  
**检查范围**: 整个项目目录

---

## 📊 检查结果摘要

### 1. 缓存和构建产物（可安全删除）

#### Python 缓存
- **`__pycache__/` 目录**: 多个位置，Python 字节码缓存
- **`.pyc` 和 `.pyo` 文件**: 编译后的 Python 文件
- **建议**: 可以删除，Python 会自动重新生成

#### Next.js 构建缓存
- **`kat_rec_web/frontend/.next/`**: **1.5GB** - Next.js 构建缓存
- **`.next/cache/`**: Webpack 缓存
- **建议**: 可以删除，`pnpm build` 会重新生成

#### 覆盖率报告
- **`kat_rec_web/backend/htmlcov/`**: HTML 覆盖率报告
- **`coverage.xml`**: XML 覆盖率报告
- **建议**: 可以删除，运行测试会重新生成

#### Rust 构建产物
- **`desktop/tauri/src-tauri/target/`**: Rust 编译产物
- **建议**: 可以删除，`pnpm tauri build` 会重新生成

---

### 2. 备份和临时文件（可删除）

#### 备份文件
- **`.bak` 文件**: 
  - `kat_rec_web/frontend/.env.local.bak`
- **`.old` 文件**:
  - `kat_rec_web/frontend/.next/cache/webpack/*.old` (多个)
- **建议**: 可以删除

#### 临时文件
- **`.tmp` 文件**: 如果有的话
- **`.DS_Store`**: macOS 系统文件（应该在 .gitignore 中）
- **`.swp`, `.swo`**: Vim 临时文件

---

### 3. 日志文件（可归档或删除）

#### 旧日志文件
- **`logs/system_events.log.1` 到 `.log.10`**: 轮转的旧日志
- **`logs/katrec.log`**: 当前日志（保留）
- **建议**: 旧日志可以归档或删除

---

### 4. 空目录（可删除）

#### 空测试目录
- `kat_rec_web/frontend/stores/__tests__/`
- `kat_rec_web/frontend/utils/__tests__/`
- `kat_rec_web/frontend/components/common/__tests__/`
- `kat_rec_web/frontend/components/mcrb/__tests__/`
- `kat_rec_web/frontend/__tests__/integration/`
- `kat_rec_web/frontend/app/legacy/` (如果为空)

#### 空构建目录
- `.cursor/plans/`
- `kat_rec_web/frontend/styles/` (如果为空)
- `kat_rec_web/frontend/public/` (如果为空)
- `output/` (如果为空)
- `library/` (如果为空)

---

### 5. Legacy 和 Archive 目录（需要评估）

#### Legacy 目录
- **`kat_rec_web/frontend/app/legacy/`**: 前端 legacy 页面
- **`kat_rec_web/frontend/legacy/`**: 前端 legacy 工具
- **`kat_rec_web/backend/t2r/legacy/`**: 后端 legacy 服务
- **建议**: 根据治理文档，legacy 目录保留用于向后兼容

#### Archive 目录
- **`scripts/archive/`**: 脚本归档
- **`scripts/local_picker/archive/`**: 本地选择器归档
- **`docs/archive/`**: 文档归档（94 个文件）
- **建议**: 保留，用于历史参考

---

### 6. 重复的虚拟环境（需要评估）

#### 虚拟环境目录
- **`.venv/`**: 323MB
- **`.venv311/`**: 337MB
- **`venv/`**: 如果存在
- **`#/`**: 可能是错误的虚拟环境
- **`kat_rec_web/backend/.venv/`**: 如果存在
- **建议**: 只保留一个活跃的虚拟环境，删除其他的

---

### 7. 大文件目录（需要评估）

#### Node.js 依赖
- **`kat_rec_web/frontend/node_modules/`**: **765MB**
- **建议**: 保留，但可以定期清理未使用的依赖

#### 虚拟环境
- **`.venv311/`**: **337MB**
- **`.venv/`**: **323MB**
- **建议**: 只保留一个

---

### 8. 可能无用的脚本（需要评估）

#### 测试脚本
- `scripts/test_upload_now.sh`
- `scripts/test_upload_quick.sh`
- `scripts/test_websocket.sh`
- `scripts/test_websocket_client.py`
- **建议**: 如果不再使用，可以移动到 `scripts/archive/`

#### 验证脚本
- `scripts/verify_sprint2.sh`
- `scripts/verify_sprint3.sh`
- `scripts/verify_sprint6.sh`
- **建议**: 如果 sprint 已完成，可以归档

---

## 🗑️ 建议的清理操作

### 立即可以删除（安全）

```bash
# 1. Python 缓存
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete

# 2. Next.js 构建缓存
rm -rf kat_rec_web/frontend/.next

# 3. 覆盖率报告
rm -rf kat_rec_web/backend/htmlcov
rm -f coverage.xml kat_rec_web/backend/coverage.xml

# 4. 备份文件
find . -type f -name "*.bak" -delete
find . -type f -name "*.old" -delete
find . -type f -name "*~" -delete

# 5. 旧日志文件
rm -f logs/system_events.log.[1-9] logs/system_events.log.10

# 6. macOS 系统文件
find . -name ".DS_Store" -delete
```

### 需要评估后删除

```bash
# 1. 空目录（先检查是否为空）
find . -type d -empty -not -path "*/node_modules/*" -not -path "*/.git/*"

# 2. 重复的虚拟环境（保留 .venv311，删除其他的）
# 如果 .venv311 是活跃的，删除 .venv 和 venv
rm -rf .venv venv "#"

# 3. Rust 构建产物（如果需要清理空间）
rm -rf desktop/tauri/src-tauri/target
```

---

## 📈 清理后预期节省空间

- **Next.js 缓存**: ~1.5GB
- **Python 缓存**: ~几 MB
- **覆盖率报告**: ~几 MB
- **旧日志**: ~几 MB
- **备份文件**: ~几 MB
- **重复虚拟环境**: ~323MB (如果删除 .venv)

**总计**: 约 **1.8GB+**

---

## ⚠️ 注意事项

1. **虚拟环境**: 删除前确认哪个是活跃的
2. **Legacy 目录**: 根据治理文档，legacy 目录应保留
3. **Archive 目录**: 保留用于历史参考
4. **Node_modules**: 不要删除，但可以运行 `pnpm prune` 清理未使用的依赖
5. **构建产物**: 删除后需要重新构建

---

## ✅ 清理脚本

已创建清理脚本 `scripts/cleanup_unused_files.sh`:

### 使用方法

```bash
# 干运行（预览将要删除的文件）
./scripts/cleanup_unused_files.sh --dry-run

# 实际执行清理
./scripts/cleanup_unused_files.sh
```

### 脚本功能

1. ✅ 清理 Python 缓存（__pycache__, *.pyc, *.pyo）
2. ✅ 清理 Next.js 构建缓存（.next/）
3. ✅ 清理覆盖率报告（htmlcov/, coverage.xml）
4. ✅ 清理备份文件（*.bak, *.old, *~）
5. ✅ 清理 macOS 系统文件（.DS_Store）
6. ✅ 清理旧日志文件（system_events.log.1-10）
7. ℹ️  报告空目录（不自动删除，需要手动评估）

---

**报告完成** ✅

