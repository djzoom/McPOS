# 后端故障排除指南

**最后更新**: 2025-11-16

---

## 🔧 常见问题

### 问题 1: `ModuleNotFoundError: No module named 'kat_rec_web'`

**症状**:
```
ModuleNotFoundError: No module named 'kat_rec_web'
```

**原因**:
- 包未以可编辑模式安装
- 在错误的目录下运行 uvicorn

**解决方案**:

```bash
# 1. 确保在项目根目录
cd ~/Downloads/Kat_Rec

# 2. 激活虚拟环境
source .venv311/bin/activate

# 3. 以可编辑模式安装包
pip install -e .

# 4. 从项目根目录运行 uvicorn
uvicorn kat_rec_web.backend.main:app --reload
```

**验证**:
```bash
# 测试模块是否可以导入
python -c "import kat_rec_web.backend.main; print('✅ 模块导入成功')"
```

---

### 问题 2: `Address already in use` (端口 8000 被占用)

**症状**:
```
ERROR: [Errno 48] Address already in use
```

**解决方案**:

```bash
# 方法 1: 查找并停止占用端口的进程
lsof -ti:8000 | xargs kill -9

# 方法 2: 使用清理脚本
./scripts/cleanup_port_8000.sh

# 方法 3: 使用不同的端口
uvicorn kat_rec_web.backend.main:app --reload --port 8001
```

---

### 问题 3: 后端启动但进入 Mock 模式

**症状**:
- 后端启动成功
- 日志显示：`⚠️  Mock API endpoints enabled`
- 错误信息：`No module named 'services'` 或 `无法导入真实路由`
- `/api/t2r/*` 路由可能不可用或返回 Mock 数据

**原因**:
1. **相对导入问题**（已修复）：多个文件使用了相对导入：
   - `upload.py`: `from services.xxx`
   - `database.py`: `from models.xxx`
   - `library_service.py`: `from models.xxx`
   - `sync.py`, `trash.py`, `library_v2.py`, `reset.py`: 相对导入
2. **缺少模型定义**（已修复）：`TrackUsageStatus`, `ImageUsageStatus`, `TrackCreateRequest` 等类型缺失
3. **缺少依赖**：`sqlalchemy`, `psutil` 等未安装

**解决方案**:

```bash
# 1. 确保包已安装（修复相对导入问题）
pip install -e .

# 2. 安装完整后端依赖
pip install -e .[backend-full]

# 或单独安装缺失的依赖
pip install sqlalchemy psutil redis aiosqlite

# 3. 重新启动后端
uvicorn kat_rec_web.backend.main:app --reload
```

**验证**:
```bash
# 测试导入
python -c "from kat_rec_web.backend.routes import channels, library, upload, status; print('✅ OK')"

# 检查后端日志，应该看到：
# ✅ T2R routers registered
# ❌ 不应该看到 "Mock Mode Enabled" 或 "Mock API endpoints enabled"

# 测试 API 端点
curl http://localhost:8000/api/t2r/episodes
# 应该返回真实数据，而不是 Mock 数据
```

---

### 问题 4: 导入错误（清理缓存后）

**症状**:
- 运行清理脚本后
- Python 模块导入失败

**原因**:
- 清理了 `__pycache__` 但包未正确安装

**解决方案**:

```bash
# 1. 重新安装包
pip install -e .

# 2. 验证导入
python -c "import kat_rec_web; print('✅ OK')"
```

---

## 📋 启动检查清单

在启动后端前，确保：

- [ ] 在项目根目录（`~/Downloads/Kat_Rec`）
- [ ] 虚拟环境已激活（`.venv311`）
- [ ] 包已安装（`pip install -e .`）
- [ ] 端口 8000 未被占用
- [ ] 所有依赖已安装（`pip install -e .[backend-full]`）

---

## 🚀 正确的启动流程

```bash
# 1. 进入项目根目录
cd ~/Downloads/Kat_Rec

# 2. 激活虚拟环境
source .venv311/bin/activate

# 3. 确保包已安装（首次或更新后）
pip install -e .

# 4. 检查端口
lsof -i :8000 || echo "端口 8000 可用"

# 5. 启动后端
uvicorn kat_rec_web.backend.main:app --reload
```

---

## 🔍 调试技巧

### 检查模块路径

```bash
python -c "import kat_rec_web; print(kat_rec_web.__file__)"
```

### 检查已安装的包

```bash
pip show kat-rec
```

### 查看后端日志

```bash
# 实时查看日志
tail -f logs/katrec.log

# 或查看系统事件日志
tail -f logs/system_events.log
```

### 测试 API 端点

```bash
# 健康检查
curl http://localhost:8000/health

# API 文档
open http://localhost:8000/docs
```

---

## 📚 相关文档

- [端口管理指南](./PORT_MANAGEMENT.md)
- [后端启动优化](./BACKEND_STARTUP_OPTIMIZATION.md)
- [开发指南](./03_DEVELOPMENT_GUIDE.md)

---

**故障排除完成** ✅
