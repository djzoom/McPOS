# Sprint 6 验收与压力测试指南

本文档提供一套完整的、可直接粘贴运行的测试清单，用于验证 T2R 系统在 Sprint 6 阶段的所有功能。

---

## 🔌 0. 预备（一次性设置）

### 启动后端

```bash
# 打开终端 1
cd ~/Downloads/Kat_Rec/kat_rec_web/backend

# 建议非Mock模式，以便测试真实路径/权限/原子写入
export USE_MOCK_MODE=false

# 启动后端
uvicorn main:app --reload --port 8000
```

**期望输出**: 
- ✅ Backend services initialized
- ✅ T2R routes enabled
- Uvicorn running on http://127.0.0.1:8000

### 启动前端

```bash
# 打开终端 2（保持后端在8000端口）
cd ~/Downloads/Kat_Rec/kat_rec_web/frontend

# 启动前端
pnpm dev
```

**期望输出**: 
- ▲ Next.js 15.x.x
- - Local: http://localhost:3000

---

## ✅ 1. 90秒 Smoke Test（"活着就行"）

### 快速验证脚本

```bash
bash scripts/sprint6_acceptance_test.sh
```

或手动执行：

```bash
# 1.1 健康检查（带环境自检）
curl -s http://localhost:8000/health | jq

# 1.2 系统指标（CPU/内存/WS连接数）
curl -s http://localhost:8000/metrics/system | jq

# 1.3 WS健康指标
curl -s http://localhost:8000/metrics/ws-health | jq

# 1.4 计划接口
curl -s -X POST http://localhost:8000/api/episodes/plan \
  -H 'Content-Type: application/json' \
  -d '{"episode_id":"CH-TEST-001"}' | jq

# 1.5 运行接口（后台任务 + WS广播）
curl -s -X POST http://localhost:8000/api/episodes/run \
  -H 'Content-Type: application/json' \
  -d '{"episode_id":"CH-TEST-001","stages":["remix","render","upload","verify"]}' | jq
```

### 判定标准

- ✅ `/health` 返回 `{"status":"ok"}`，并列出 LIBRARY_ROOT/OUTPUT_ROOT/DATA_ROOT 的可写状态
- ✅ `/metrics/system` 包含 `cpu_percent`, `memory_mb`, `active_ws_connections`
- ✅ `run` 返回一个 `run_id`，终端日志可看到阶段广播

---

## 📡 2. WebSocket 完整性测试

### 2.1 Python 自动测试（推荐）

```bash
# 确保 websockets 库已安装
pip install websockets

# 运行测试
python3 scripts/sprint6_websocket_test.py
```

**判定标准**:
- ✅ `pings >= 1` (心跳5s间隔)
- ✅ `last_ver` 单调递增（无重复或乱序）
- ✅ `median_gap_ms ≈ 100±50ms` (批量缓冲)

### 2.2 浏览器控制台测试（可选）

打开 http://localhost:3000/t2r，在浏览器控制台粘贴：

```javascript
const s = new WebSocket('ws://localhost:8000/ws/events');
let lastVer = -1, pings = 0, events = 0, gaps = [];
let prevTs = performance.now();

s.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m === 'ping' || m === '"ping"') { 
    pings++; 
    console.log('💓 心跳 #' + pings);
    return; 
  }
  
  if (typeof m.version === 'number' && m.version <= lastVer) {
    console.warn('❌ version 非递增', m.version, '<=', lastVer);
  }
  lastVer = m.version || lastVer;
  events++;
  
  const now = performance.now();
  gaps.push(now - prevTs);
  prevTs = now;
  
  if (events <= 5) {
    console.log('📨 事件 #' + events, m.type || m);
  }
};

s.onopen = () => console.log('✅ WebSocket 已连接');
s.onerror = (e) => console.error('❌ WebSocket 错误', e);

// 5秒后触发测试事件
setTimeout(() => {
  fetch('http://localhost:8000/api/episodes/run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      episode_id: 'CH-TEST-002',
      stages: ['remix', 'render']
    })
  }).then(r => r.json()).then(d => {
    console.log('🚀 触发Run:', d.run_id);
  });
}, 2000);

// 15秒后输出统计
setTimeout(() => {
  const sorted = gaps.sort((a,b) => a-b);
  const median = sorted[Math.floor(sorted.length/2)];
  console.log('\n📊 统计:');
  console.log('  心跳:', pings, '(期望 ≥1)');
  console.log('  事件:', events);
  console.log('  版本:', lastVer, '(单调递增)');
  console.log('  中位数间隔:', median.toFixed(1), 'ms (期望 ~100ms)');
  s.close();
}, 15000);
```

**判定标准**:
- ✅ 控制台 `pings` 在10秒内应 ≥1（心跳5s）
- ✅ `lastVer` 单调递增
- ✅ `gaps` 的中位数大致在 100ms 左右（批量刷新）

---

## ♻️ 3. 重试与恢复测试

### 3.1 检查重试策略

```bash
cat ~/Downloads/Kat_Rec/kat_rec_web/backend/t2r/config/retry_policy.json | jq
```

**期望**: 包含 `max_retries`, `backoff_multiplier`, `stages` 等字段

### 3.2 触发Run并检查Journal

```bash
# 触发一轮Run（内置10%随机失败率）
curl -s -X POST http://localhost:8000/api/episodes/run \
  -H 'Content-Type: application/json' \
  -d '{"episode_id":"CH-TEST-003","stages":["remix","render","upload","verify"]}' | jq

# 等待2秒让journal写入
sleep 2

# 查看journal
tail -n 50 ~/Downloads/Kat_Rec/data/run_journal.json | jq '.'
```

**判定标准**:
- ✅ journal 中能看到阶段状态 `running`/`completed`/`failed`
- ✅ 若失败，则应记录 `retry_point` 并广播 `runbook_error`

### 3.3 恢复能力测试

```bash
# 再次调用run（同episode_id）
curl -s -X POST http://localhost:8000/api/episodes/run \
  -H 'Content-Type: application/json' \
  -d '{"episode_id":"CH-TEST-003","stages":["remix","render","upload","verify"]}' | jq

# 查看后端日志，应看到 "Resuming from ..."
```

**判定标准**: 日志提示 `resuming from ...`（若上一轮失败），并从断点继续

### 3.4 运行单元测试

```bash
cd ~/Downloads/Kat_Rec/kat_rec_web/backend
pytest -v tests/test_resume_run.py
```

**期望**: 至少 1 passed（或显示通过的断言数）

---

## 🧾 4. 原子写入测试

```bash
# 检查是否有.tmp残留文件（原子写入失败标志）
find ~/Downloads/Kat_Rec/data -name "*.tmp" 2>/dev/null | wc -l

# 检查recipe文件（应包含hash）
ls -l ~/Downloads/Kat_Rec/data | grep "CH-TEST" | grep -E "-[a-f0-9]{8}\.json"

# 验证JSON完整性
find ~/Downloads/Kat_Rec/data -name "CH-TEST-*.json" -exec jq empty {} \; 2>&1
```

**判定标准**: 
- ✅ 数据文件"要么就写全、要么就没有"，不会半截文件
- ✅ Recipe文件名包含hash（幂等性）

---

## 📈 5. Metrics回归测试

```bash
# 1. 记录初始连接数
INIT=$(curl -s http://localhost:8000/metrics/system | jq -r '.active_ws_connections')
echo "初始WS连接数: $INIT"

# 2. 打开 http://localhost:3000/t2r 页面

# 3. 等待5秒
sleep 5

# 4. 再次检查
LATER=$(curl -s http://localhost:8000/metrics/system | jq -r '.active_ws_connections')
echo "当前WS连接数: $LATER"

# 5. 关闭页面后再次检查（应下降）
# ... 手动关闭页面 ...
sleep 3
FINAL=$(curl -s http://localhost:8000/metrics/system | jq -r '.active_ws_connections')
echo "关闭后WS连接数: $FINAL"
```

**判定标准**: 连接数与真实页面/脚本连接一致

---

## 🧪 6. 一键验收脚本

```bash
# 使用自动化测试脚本
bash scripts/sprint6_acceptance_test.sh
```

**判定标准**: 各段均返回 OK，且 metrics 有合理数值

---

## 🧱 7. 前端去重与重连测试（手动）

### 7.1 去重测试

1. 打开 http://localhost:3000/t2r
2. 打开开发者工具 → Console
3. 观察右下 SystemFeed
4. **检查**: 同一 `version` 的事件不应重复显示

### 7.2 重连测试

1. 确保页面已连接并收到事件
2. **断网**: 关闭WiFi/网络连接
3. **等待**: 10-20秒
4. **恢复网络**: 重新连接
5. **观察**: 
   - Feed 应能继续推进
   - 控制台应显示重连日志
   - 重连间隔应为指数退避: 2s → 4s → 8s → 16s → 32s → 60s

---

## 🐳 8. Docker化验收（可选）

```bash
cd ~/Downloads/Kat_Rec/kat_rec_web

# 启动Docker Compose
docker compose up --build

# 等待服务启动（约30-60秒）
# 然后重复第1/2/5步的curl与WS测试

# 验证容器内服务
docker compose exec backend curl http://localhost:8000/health
```

**判定标准**: 容器内 `/health` 与 `/metrics/*` 正常；run 能广播事件

---

## 🎯 通过/不通过的"红线"标准

### 必须通过 ✅

- [ ] `/health` 报 OK 且列出可写目录
- [ ] `/metrics/system` 与 `/metrics/ws-health` 可用
- [ ] WS：version 单调递增、5s 心跳、~100ms 批量
- [ ] `plan` 产出带 hash 的 recipe；`run` 立即返回 `run_id`
- [ ] journal 记录完整阶段，失败能恢复
- [ ] 无临时文件残留（原子写入正常）

### 建议观察 ⚠️

- [ ] WS 连接数与前端页面一致
- [ ] 多并发 run（开3-4个）吞吐稳定、无内存飙升
- [ ] 前端重连机制正常（指数退避）

---

## 🧰 故障排查

### 403/503 错误

**可能原因**: 环境变量或目录权限问题

```bash
# 检查/health的paths字段
curl -s http://localhost:8000/health | jq '.environment.paths'

# 检查目录权限
ls -ld ~/Downloads/Kat_Rec/{library,output,config,data}
```

### WS 没消息

**排查步骤**:
1. 检查后端日志是否有 `broadcast_t2r_event`
2. 检查端口是否被占用: `lsof -i :8000`
3. 检查前端是否连接: 浏览器控制台查看WebSocket连接

### Version 重复/乱序

**可能原因**: 
- 多个WS客户端同时连接
- 刷新后旧连接未关闭

**解决**: 
- 确保只打开一个页面
- 刷新页面后等待旧连接关闭

### 恢复不生效

**排查步骤**:
1. 检查 `data/run_journal.json` 是否写入了 `retry_point`
2. 确认 `resume_from_run_id()` 函数被调用
3. 查看后端日志是否有 "Resuming from ..." 消息

---

## 📊 测试报告模板

完成测试后，填写以下报告：

```
Sprint 6 验收测试报告
日期: YYYY-MM-DD
测试人: [Your Name]

✅ 通过项:
- [ ] Smoke Test
- [ ] WebSocket完整性
- [ ] 重试与恢复
- [ ] 原子写入
- [ ] Metrics回归
- [ ] 前端去重与重连
- [ ] Docker化（如测试）

❌ 失败项:
- [列出失败的测试项]

⚠️  警告项:
- [列出警告项]

总体结论: [通过/部分通过/不通过]
```

---

## 🔗 相关文档

- [Sprint 6 完成总结](../docs/T2R_SPRINT6_COMPLETE.md)
- [T2R 生产就绪文档](../docs/T2R_PRODUCTION_READY.md)
- [README](../kat_rec_web/README.md)

---

**一句话总结**: 先 health & metrics，后 WS 三件套（心跳/版本/批量），再看 run 的恢复与原子写入。以上每一步都有"可量化"的通过条件，跑完你就能给 Sprint 6 画 ✅ 了。

