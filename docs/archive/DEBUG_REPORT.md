# 后端服务诊断报告

## 问题总结

**症状**: 点击 Void 格子没有任何反应
- 前端日志显示 "ScheduleHydrator transformed episodes" 但无 playlist/cover 生成
- 后端 API (`GET http://localhost:8000/api/channels`) 返回 404 或超时
- WebSocket 连接 (`/ws/events`, `/ws/status`, `/ws/schedule`) 失败，显示 "handshake timed out"
- 自动化工作流 (`planEpisode → generatePlaylist → remixMixtape`) 从未触发

## 诊断结果

### 1. 后端进程状态
- ✅ **进程存在**: PID 28018 正在运行
- ⚠️ **进程状态**: `SN` (睡眠/低优先级)，已运行 13 小时
- ❌ **HTTP 响应**: 所有端点 (`/`, `/health`, `/api/channels`) 超时或无响应

### 2. 端口监听状态
- ✅ **端口占用**: 8000 端口被进程 28018 占用
- ❌ **HTTP 连接**: 无法建立连接，请求超时

### 3. 前端配置
- ✅ **API URL**: `NEXT_PUBLIC_API_URL=http://localhost:8000`
- ✅ **WebSocket URL**: `NEXT_PUBLIC_WS_URL=ws://localhost:8000`

### 4. 后端配置
- ⚠️ **Mock 模式**: 未设置 `USE_MOCK_MODE` 环境变量（默认 false）
- ⚠️ **路由注册**: 如果不在 mock 模式，需要 Redis 和数据库

## 根本原因分析

**最可能的原因**: 后端进程在启动时卡住或挂起，导致：
1. FastAPI 应用未完全初始化
2. HTTP 服务器未正常启动监听
3. WebSocket 端点未注册

**可能的原因**:
1. **导入错误**: T2R 路由导入失败（第 305-373 行），导致应用启动失败
2. **初始化阻塞**: `lifespan` 函数中的数据库/Redis 初始化卡住
3. **端口冲突**: 虽然进程存在，但实际未监听 8000 端口

## 解决方案

### 方案 1: 重启后端服务（推荐）

```bash
# 1. 停止当前后端进程
kill 28018

# 2. 进入后端目录
cd /Users/z/Downloads/Kat_Rec/kat_rec_web/backend

# 3. 使用 Mock 模式启动（快速，无需 Redis/DB）
export USE_MOCK_MODE=true
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 或者使用真实模式（需要 Redis/DB）
# unset USE_MOCK_MODE
# uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 方案 2: 检查并修复导入错误

如果重启后仍然失败，检查 T2R 路由导入：

```bash
cd /Users/z/Downloads/Kat_Rec/kat_rec_web/backend
python3 -c "from t2r.routes import scan, srt, plan, upload, audit, desc, episodes, automation, reset, schedule, api_health; print('✅ All routes imported')"
```

### 方案 3: 使用开发脚本启动

检查是否有启动脚本：

```bash
# 检查 package.json 或 Makefile
cd /Users/z/Downloads/Kat_Rec
cat kat_rec_web/backend/package.json 2>/dev/null || echo "No package.json"
cat Makefile | grep -i backend || echo "No backend target in Makefile"
```

## 验证步骤

启动后端后，验证以下端点：

```bash
# 1. 根端点
curl http://localhost:8000/

# 2. 健康检查
curl http://localhost:8000/health

# 3. 频道列表（Mock 模式）
curl http://localhost:8000/api/channels

# 4. T2R API Health
curl http://localhost:8000/api/t2r/api-health

# 5. WebSocket 端点（通过浏览器开发者工具测试）
# ws://localhost:8000/ws/status
# ws://localhost:8000/ws/events
```

## 预期结果

启动成功后，应该看到：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
✅ Database initialized (如果非 mock 模式)
✅ Backend services initialized (如果非 mock 模式)
🔧 Mock mode enabled - skipping Redis initialization (如果是 mock 模式)
✅ T2R/MCRB routers registered
```

## 前端验证

后端启动后，刷新前端页面，应该看到：
1. ✅ `/api/channels` 请求成功（200 状态码）
2. ✅ WebSocket 连接成功（控制台显示 "✅ Events WebSocket connected"）
3. ✅ 点击 Void 格子可以创建 episode 并触发自动化工作流

## 后续建议

1. **添加健康检查**: 在启动脚本中添加自动重试逻辑
2. **改进错误处理**: 如果导入失败，应该优雅降级而不是挂起
3. **添加日志**: 确保启动过程的每个步骤都有日志输出
4. **监控进程**: 使用进程管理器（如 systemd 或 supervisor）确保服务稳定运行

