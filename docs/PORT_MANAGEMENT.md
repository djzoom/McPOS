# 端口管理指南

## 问题说明

前后端端口不一致是常见问题，可能导致：
- 前端无法连接到后端 API
- WebSocket 连接失败
- CORS 错误

## 解决方案

### 1. 自动端口检测和适配

启动脚本 (`scripts/start.sh`) 现在会自动：
- ✅ 检测后端是否已在运行（通过 `/health` 端点）
- ✅ 如果端口被占用，自动查找可用端口（8000-8010）
- ✅ 自动更新前端配置以匹配实际后端端口

### 2. 端口配置优先级

前端会按以下优先级获取后端端口：

1. **环境变量** `NEXT_PUBLIC_API_URL`（最高优先级）
2. **环境变量** `NEXT_PUBLIC_BACKEND_PORT`（自动构建 URL）
3. **默认值** `http://localhost:8000`

### 3. 手动端口检查

运行端口检查脚本：

```bash
cd kat_rec_web
bash scripts/check-ports.sh
```

这会：
- 检查端口占用情况
- 自动更新前端 `.env.local` 配置
- 显示当前端口配置

### 4. 停止后端服务

如果端口被占用，可以停止现有后端：

```bash
bash scripts/stop-backend.sh
```

或手动停止：

```bash
# 查找占用端口的进程
lsof -i :8000

# 停止进程（替换 PID）
kill <PID>
```

### 5. 环境变量配置

在项目根目录或 `kat_rec_web` 目录创建 `.env` 文件：

```bash
# 后端端口
BACKEND_PORT=8000

# 前端端口
FRONTEND_PORT=3000

# 前端 API URL（可选，会自动从 BACKEND_PORT 生成）
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## 常见问题

### Q: 前端显示 "无法连接到后端服务"

**A:** 检查：
1. 后端是否在运行：`curl http://localhost:8000/health`
2. 端口是否一致：运行 `bash scripts/check-ports.sh`
3. 浏览器控制台查看实际使用的 API URL

### Q: 端口被占用怎么办？

**A:** 
1. 使用 `scripts/stop-backend.sh` 停止旧进程
2. 或让启动脚本自动查找可用端口（8000-8010）
3. 前端会自动适配新的后端端口

### Q: 如何查看当前端口配置？

**A:**
```bash
# 检查后端端口
lsof -i :8000

# 检查前端端口
lsof -i :3000

# 查看前端配置
cat kat_rec_web/frontend/.env.local
```

## 最佳实践

1. **使用统一启动脚本**：始终使用 `scripts/start.sh` 启动服务
2. **检查端口冲突**：启动前运行 `scripts/check-ports.sh`
3. **环境变量优先**：在 `.env` 文件中设置端口，而不是硬编码
4. **查看日志**：启动脚本会显示实际使用的端口

## 技术细节

### 后端端口检测

启动脚本会：
1. 检查端口是否被占用
2. 如果占用，检查是否是本项目的后端（通过 `/health` 端点）
3. 如果是，复用现有服务
4. 如果不是，查找可用端口（8000-8010）

### 前端自动配置

启动脚本会：
1. 读取实际使用的后端端口
2. 更新 `frontend/.env.local` 文件
3. 设置 `NEXT_PUBLIC_API_URL` 和 `NEXT_PUBLIC_WS_URL`

### 前端运行时检测

前端代码 (`lib/apiBase.ts`) 会：
1. 优先使用环境变量
2. 如果没有，从 `NEXT_PUBLIC_BACKEND_PORT` 构建 URL
3. 最后使用默认值（带警告）

