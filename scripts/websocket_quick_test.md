# WebSocket 快速测试指南

## ⚠️ 重要提示

**curl 不能直接测试 WebSocket 连接**。WebSocket 使用特殊的协议握手，需要通过专门的客户端。

---

## 🔧 解决端口占用

如果看到 "Address already in use" 错误：

```bash
# 方法 1: 停止占用端口的进程
kill 29472  # 或使用找到的 PID

# 方法 2: 查看并停止所有 uvicorn 进程
ps aux | grep uvicorn | grep -v grep
killall uvicorn

# 方法 3: 使用不同端口
cd kat_rec_web/backend
export USE_MOCK_MODE=true
uvicorn main:app --reload --port 8001
```

---

## 🧪 测试方法

### 方法 1: 使用 Python 测试脚本（推荐）

```bash
# 1. 安装依赖（如果需要）
pip install websockets

# 2. 运行测试脚本
python3 scripts/test_websocket_client.py

# 3. 或测试特定功能
python3 scripts/test_websocket_client.py --test status    # 只测试状态端点
python3 scripts/test_websocket_client.py --test events    # 只测试事件端点
python3 scripts/test_websocket_client.py --test heartbeat # 只测试心跳
```

**预期输出**:
```
🔌 连接到 ws://localhost:8000/ws/status...
✅ 连接成功!
📨 收到消息 #1:
   类型: status_update
   队列状态: {'total': 10, 'active': 7, ...}
   成功率: 83.33%
```

### 方法 2: 使用 wscat（需要 Node.js）

```bash
# 1. 安装 wscat
npm install -g wscat

# 2. 连接并监听
wscat -c ws://localhost:8000/ws/status

# 应该每 10 秒收到状态更新
# 应该每 5 秒收到 "ping"
```

### 方法 3: 使用浏览器控制台

打开浏览器（Chrome/Firefox），打开开发者工具（F12），在控制台输入：

```javascript
// 测试状态端点
const ws = new WebSocket('ws://localhost:8000/ws/status')
ws.onopen = () => console.log('✅ 连接成功')
ws.onmessage = (e) => {
  const data = JSON.parse(e.data)
  console.log('📨 收到消息:', data)
  
  if (data.type === 'status_update') {
    console.log('队列状态:', data.data.queue_status)
    console.log('成功率:', data.data.success_rate)
    console.log('最后事件:', data.data.last_event)
  }
}
ws.onerror = (e) => console.error('❌ 错误:', e)
ws.onclose = () => console.log('👋 连接关闭')
```

### 方法 4: 运行单元测试

```bash
cd kat_rec_web/backend
pytest tests/test_websocket_status.py -v
```

---

## 📊 预期行为

### 状态端点 (`/ws/status`)

- **连接**: 立即建立
- **心跳**: 每 5 秒收到 `"ping"`
- **状态更新**: 每 10 秒收到完整状态消息
- **消息格式**:
  ```json
  {
    "type": "status_update",
    "data": {
      "queue_status": {
        "total": 10,
        "active": 7,
        "pending": 2,
        "processing": 3,
        "completed": 5,
        "failed": 1
      },
      "success_rate": 83.33,
      "last_event": {
        "timestamp": "2025-11-10T...",
        "level": "INFO",
        "message": "..."
      }
    }
  }
  ```

### 事件端点 (`/ws/events`)

- **连接**: 立即建立
- **心跳**: 每 5 秒收到 `"ping"`
- **事件**: 每 3-8 秒收到随机事件
- **消息格式**:
  ```json
  {
    "type": "event",
    "data": {
      "timestamp": "2025-11-10T...",
      "level": "INFO",
      "message": "Channel CH-001 started remixing",
      "channel_id": "CH-001",
      "stage": "remixing"
    }
  }
  ```

---

## 🔍 调试技巧

### 查看后端日志

```bash
# 启动后端时应该看到：
✅ Status broadcast task started
✅ Events broadcast task started
Heartbeat task started (interval: 5s)
Cleanup task started (timeout: 15s)
✅ WebSocket client connected. ID: conn_0, Total: 1
```

### 测试心跳

```bash
# 使用测试脚本的 heartbeat 模式
python3 scripts/test_websocket_client.py --test heartbeat

# 应该看到：
✅ 收到 ping #1 (耗时 5.0s)
✅ 收到 ping #2 (耗时 10.0s)
✅ 心跳正常！10 秒内收到 2 个 ping
```

### 测试清理机制

1. 连接 WebSocket
2. 不发送任何消息
3. 等待 15 秒以上
4. 查看后端日志，应该看到：
   ```
   WARNING Removing stale connection: conn_0
   ```

---

## ❌ 常见问题

### 问题 1: "Connection refused"

**原因**: 后端未运行

**解决**:
```bash
cd kat_rec_web/backend
export USE_MOCK_MODE=true
uvicorn main:app --reload --port 8000
```

### 问题 2: "Address already in use"

**原因**: 端口被占用

**解决**: 见上面的"解决端口占用"部分

### 问题 3: 收不到消息

**可能原因**:
1. 心跳任务未启动（检查后端日志）
2. 连接已断开（检查连接状态）
3. 消息格式错误（检查日志）

### 问题 4: curl 无法测试

**说明**: curl 不支持 WebSocket 协议

**解决**: 使用上述任一测试方法

---

## ✅ 验证清单

- [ ] 后端服务运行正常 (`/health` 返回 200)
- [ ] WebSocket 连接成功建立
- [ ] 每 5 秒收到心跳 ping
- [ ] 每 10 秒收到状态更新（`/ws/status`）
- [ ] 每 3-8 秒收到事件（`/ws/events`）
- [ ] 状态消息包含 `queue_status`, `success_rate`, `last_event`
- [ ] 批量重试 API 正常工作

---

**最后更新**: 2025-11-10

