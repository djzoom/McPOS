# Sprint 3 WebSocket Schema

**版本**: v1.0  
**更新日期**: 2025-11-10

---

## 📡 WebSocket 端点

### 1. 状态更新通道

**URL**: `ws://localhost:8000/ws/status`  
**协议**: WebSocket  
**用途**: 实时推送频道状态更新

#### 连接示例

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/status')

ws.onmessage = (event) => {
  const message = JSON.parse(event.data)
  console.log(message)
}
```

#### 消息格式

**状态更新消息**:
```json
{
  "type": "status_update",
  "data": {
    "channels": [
      {
        "channel_id": "CH-001",
        "status": "processing",
        "progress": 45,
        "updated_at": "2025-11-10T10:30:00Z"
      },
      {
        "channel_id": "CH-002",
        "status": "uploading",
        "progress": 78,
        "updated_at": "2025-11-10T10:30:05Z"
      }
    ],
    "timestamp": "2025-11-10T10:30:10Z"
  }
}
```

**心跳响应**:
```json
{
  "type": "pong",
  "timestamp": "2025-11-10T10:30:00Z"
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 消息类型：`status_update` 或 `pong` |
| `data.channels` | array | 频道状态数组 |
| `data.channels[].channel_id` | string | 频道 ID（格式：CH-XXX） |
| `data.channels[].status` | string | 状态：`pending`, `processing`, `uploading`, `completed`, `failed` |
| `data.channels[].progress` | number | 进度百分比（0-100），可选 |
| `data.channels[].updated_at` | string | ISO 8601 时间戳 |
| `data.timestamp` | string | 消息时间戳 |

#### 推送频率

- 每 **10 秒**推送一次完整状态更新
- 包含所有活跃频道的状态

---

### 2. 事件流通道

**URL**: `ws://localhost:8000/ws/events`  
**协议**: WebSocket  
**用途**: 实时推送系统事件

#### 连接示例

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/events')

ws.onmessage = (event) => {
  const message = JSON.parse(event.data)
  console.log(message)
}
```

#### 消息格式

**事件消息**:
```json
{
  "type": "event",
  "data": {
    "timestamp": "2025-11-10T10:30:00Z",
    "level": "INFO",
    "message": "Channel CH-001 started remixing",
    "channel_id": "CH-001",
    "stage": "remixing"
  }
}
```

**心跳响应**:
```json
{
  "type": "pong",
  "timestamp": "2025-11-10T10:30:00Z"
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 消息类型：`event` 或 `pong` |
| `data.timestamp` | string | ISO 8601 时间戳 |
| `data.level` | string | 事件级别：`INFO`, `WARNING`, `ERROR`, `SUCCESS` |
| `data.message` | string | 事件消息 |
| `data.channel_id` | string | 相关频道 ID，可选 |
| `data.stage` | string | 相关阶段：`remixing`, `rendering`, `uploading`, `validation`，可选 |

#### 事件级别

- **INFO**: 一般信息（蓝色）
- **SUCCESS**: 成功操作（绿色）
- **WARNING**: 警告信息（黄色）
- **ERROR**: 错误信息（红色）

#### 推送频率

- 每 **3-8 秒**推送一个随机事件（随机间隔）

---

## 🔄 客户端协议

### 心跳机制

客户端应每 30 秒发送一次 ping：

```json
{
  "type": "ping"
}
```

服务器会响应：

```json
{
  "type": "pong",
  "timestamp": "2025-11-10T10:30:00Z"
}
```

### 重连策略

建议的重连策略：

1. **首次断开**: 立即重连
2. **连续失败**: 指数退避（3s, 6s, 12s, 24s...）
3. **最大重试**: 10 次
4. **成功后**: 重置重试计数

### 错误处理

#### 连接错误

```javascript
ws.onerror = (error) => {
  console.error('WebSocket error:', error)
  // 触发重连
}
```

#### 关闭处理

```javascript
ws.onclose = (event) => {
  console.log('WebSocket closed:', event.code, event.reason)
  // 触发重连
}
```

---

## 📊 消息示例

### 状态更新示例

```json
{
  "type": "status_update",
  "data": {
    "channels": [
      {
        "channel_id": "CH-001",
        "status": "processing",
        "progress": 45,
        "updated_at": "2025-11-10T10:30:00Z"
      },
      {
        "channel_id": "CH-002",
        "status": "completed",
        "progress": 100,
        "updated_at": "2025-11-10T10:29:55Z"
      }
    ],
    "timestamp": "2025-11-10T10:30:10Z"
  }
}
```

### 事件流示例

#### INFO 事件

```json
{
  "type": "event",
  "data": {
    "timestamp": "2025-11-10T10:30:00Z",
    "level": "INFO",
    "message": "Channel CH-001 started remixing",
    "channel_id": "CH-001",
    "stage": "remixing"
  }
}
```

#### ERROR 事件

```json
{
  "type": "event",
  "data": {
    "timestamp": "2025-11-10T10:30:05Z",
    "level": "ERROR",
    "message": "Upload failed on Channel CH-003",
    "channel_id": "CH-003",
    "stage": "uploading"
  }
}
```

#### SUCCESS 事件

```json
{
  "type": "event",
  "data": {
    "timestamp": "2025-11-10T10:30:10Z",
    "level": "SUCCESS",
    "message": "Channel CH-002 successfully uploaded",
    "channel_id": "CH-002",
    "stage": "uploading"
  }
}
```

---

## 🔐 安全考虑

### 当前实现（开发阶段）

- ✅ CORS 已配置（允许 localhost）
- ✅ WebSocket 连接无认证（开发环境）
- ⚠️ 生产环境需要添加：
  - Token 认证
  - 连接限制
  - 消息验证

### 生产环境建议

1. **认证**
   ```javascript
   // 连接时携带 token
   const ws = new WebSocket(`ws://api.example.com/ws/status?token=${token}`)
   ```

2. **消息验证**
   - 验证消息格式
   - 验证时间戳
   - 防止注入攻击

3. **连接限制**
   - 每用户最多 5 个连接
   - 连接超时（30 分钟）
   - IP 限制

---

## 📝 变更日志

### v1.0 (2025-11-10)

- ✅ 初始版本
- ✅ 状态更新通道
- ✅ 事件流通道
- ✅ 心跳机制

---

**文档维护者**: Sprint 3 开发团队  
**最后更新**: 2025-11-10

