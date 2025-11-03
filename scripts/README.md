# Kat Rec 脚本工具集

## 🚀 启动脚本

### `start_backend.sh` - 启动后端服务

```bash
bash scripts/start_backend.sh
```

**功能**:
- 自动检测虚拟环境
- 设置 Mock 模式
- 检查端口占用
- 启动 uvicorn 服务

---

## 🧪 测试脚本

### `test_all.sh` - 完整测试套件

```bash
bash scripts/test_all.sh
```

**测试内容**:
- 健康检查
- 任务控制 API
- WebSocket 连接

### `test_websocket.sh` - WebSocket 测试说明

```bash
bash scripts/test_websocket.sh
```

提供 WebSocket 测试的各种方法和说明。

### `quick_test_ws.sh` - 快速测试（后端已运行）

```bash
bash scripts/quick_test_ws.sh
```

快速验证后端运行状态和 API。

### `test_websocket_client.py` - Python WebSocket 客户端

```bash
# 完整测试
python3 scripts/test_websocket_client.py

# 测试特定功能
python3 scripts/test_websocket_client.py --test status
python3 scripts/test_websocket_client.py --test events
python3 scripts/test_websocket_client.py --test heartbeat
```

**功能**:
- 测试 `/ws/status` 端点
- 测试 `/ws/events` 端点
- 测试心跳机制（5 秒间隔）

---

## 📋 使用流程

### 1. 启动后端

```bash
# 终端 1
bash scripts/start_backend.sh
```

### 2. 测试 WebSocket

```bash
# 终端 2（新终端）
python3 scripts/test_websocket_client.py
```

### 3. 验证功能

```bash
# 测试 API
bash scripts/quick_test_ws.sh

# 完整测试
bash scripts/test_all.sh
```

---

## 🔧 环境要求

### Python 依赖

```bash
pip install websockets  # WebSocket 客户端测试
```

### Node.js 工具（可选）

```bash
npm install -g wscat  # WebSocket 命令行工具
```

---

## 📝 测试示例

### 预期输出

**后端启动**:
```
✅ Status broadcast task started
✅ Events broadcast task started
INFO: Heartbeat task started (interval: 5s)
INFO: Cleanup task started (timeout: 15s)
INFO: Uvicorn running on http://0.0.0.0:8000
```

**WebSocket 测试**:
```
✅ 连接成功!
📨 收到消息 #1:
   类型: status_update
   队列状态: {'total': 10, 'active': 7, ...}
   成功率: 83.33%
```

---

## 📚 相关文档

- `websocket_quick_test.md` - WebSocket 详细测试指南
- `docs/WEBSOCKET_ENHANCEMENTS.md` - WebSocket 增强功能文档

---

**最后更新**: 2025-11-10

