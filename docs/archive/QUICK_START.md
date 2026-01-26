# 🚀 Kat Rec 快速启动指南

## 一键启动所有服务

```bash
# 启动后端 + 前端（推荐：健壮启动，确保前后端同时运行）
make ensure-running
# 或
bash scripts/ensure_services_running.sh

# 标准启动（交互式，前台运行）
make start
# 或
bash scripts/start.sh
```

## 单独启动服务

```bash
# 仅启动后端
make start-backend

# 仅启动前端
make start-frontend

# 启动所有服务 + Tauri 桌面应用
make start-tauri
```

## 健壮启动（推荐）

如果遇到后端启动失败或前后端不同时运行的问题，使用健壮启动脚本：

```bash
# 自动检查并启动缺失的服务，确保前后端同时运行
make ensure-running
```

此脚本会：
- ✅ 检查后端和前端服务状态
- ✅ 自动启动缺失的服务
- ✅ 等待服务完全启动后再继续
- ✅ 提供详细的错误诊断信息
- ✅ 自动配置前端连接到正确的后端端口

## 服务地址

启动成功后，访问以下地址：

- **前端**: http://localhost:3000
- **排播总览**: http://localhost:3000/mcrb/overview
- **后端 API**: http://127.0.0.1:8010
- **API 文档**: http://127.0.0.1:8010/docs
- **健康检查**: http://127.0.0.1:8010/health

## 环境要求

- Python 3.11+ (虚拟环境: `.venv311`)
- Node.js 20+ 和 pnpm
- 端口 8010 和 3000 可用

## 日志文件

所有服务的日志保存在 `.logs/` 目录：
- `backend.log` - 后端日志
- `frontend.log` - 前端日志
- `tauri.log` - Tauri 日志（如果启动）

## 停止服务

按 `Ctrl+C` 停止所有服务，脚本会自动清理所有进程。

## 故障排除

### 后端启动失败

如果后端启动失败，常见原因和解决方法：

1. **依赖缺失**：检查虚拟环境是否激活，依赖是否安装
   ```bash
   source .venv311/bin/activate
   pip install -r kat_rec_web/backend/requirements.txt
   ```

2. **端口被占用**：检查并停止占用进程
   ```bash
   # 检查端口占用
   lsof -i :8000  # 后端（默认端口）
   lsof -i :3000  # 前端
   
   # 停止占用进程
   lsof -ti :8000 | xargs kill -9
   lsof -ti :3000 | xargs kill -9
   ```

3. **导入错误**：查看后端日志获取详细错误信息
   ```bash
   tail -n 50 .logs/backend.log
   ```

4. **使用 Mock 模式**：如果数据库/Redis 不可用，使用 Mock 模式启动
   ```bash
   export USE_MOCK_MODE=true
   make start-backend
   ```

### 前后端不同时运行

使用健壮启动脚本确保前后端同时运行：

```bash
# 自动检查并启动缺失的服务
make ensure-running
```

此脚本会：
- 检查后端健康状态（`/health` 端点）
- 检查前端响应
- 自动启动缺失的服务
- 等待服务完全启动后再继续

### 虚拟环境未激活

确保虚拟环境存在：
```bash
# 创建虚拟环境（如果不存在）
python3 -m venv .venv311
source .venv311/bin/activate
pip install -r kat_rec_web/backend/requirements.txt
```

### 前端依赖未安装

```bash
cd kat_rec_web/frontend
pnpm install
```

## 更多命令

查看 `make help` 获取所有可用命令。

