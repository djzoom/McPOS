# 后端快速启动指南

## Mock 模式启动（推荐用于开发）

Mock 模式不需要安装 Redis、SQLAlchemy 等依赖，可以快速启动用于前端开发。

```bash
# 1. 设置环境变量
export USE_MOCK_MODE=true

# 2. 启动服务器
uvicorn main:app --reload --port 8000
```

**预期输出**:
```
🔧 Mock mode enabled - skipping Redis and DB initialization
⚠️  Mock API endpoints enabled
INFO:     Uvicorn running on http://127.0.0.1:8000
```

## 验证启动成功

1. **访问根端点**:
   ```bash
   curl http://localhost:8000/
   ```

2. **访问健康检查**:
   ```bash
   curl http://localhost:8000/health
   ```

3. **访问 API 文档**:
   打开浏览器访问: http://localhost:8000/docs

4. **测试 Mock API**:
   ```bash
   # 测试频道列表
   curl http://localhost:8000/api/channels
   
   # 测试歌曲列表
   curl http://localhost:8000/api/library/songs
   
   # 测试期数列表
   curl http://localhost:8000/metrics/episodes
   ```

## 常见问题

### 问题：ModuleNotFoundError

如果看到类似 `ModuleNotFoundError: No module named 'fastapi'` 的错误：

**解决**:
```bash
pip install fastapi uvicorn python-dotenv
```

### 问题：自动切换到 Mock 模式

如果看到警告信息说"无法导入真实路由"，这是正常的。系统会自动使用 Mock 模式，不影响前端开发。

## 生产模式启动

如果需要在生产模式（使用真实数据库和 Redis）下启动：

```bash
# 1. 确保所有依赖已安装
pip install -r requirements.txt

# 2. 设置环境变量（不使用 Mock 模式）
unset USE_MOCK_MODE
# 或
export USE_MOCK_MODE=false

# 3. 启动服务器
uvicorn main:app --reload --port 8000
```

---

**提示**: 对于 Sprint 2 开发，使用 Mock 模式即可。

