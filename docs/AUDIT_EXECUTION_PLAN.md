# 审计执行计划

**目标**: 为第三方审计员提供清晰的执行步骤

---

## 🎯 审计目标

验证 T2R 系统的以下能力：
1. 健康检查与系统指标
2. REST API 端点功能
3. WebSocket 实时通信
4. 后台任务执行与恢复
5. 原子写入与幂等性

---

## ⏱️ 预计时间

- **快速验证**: 5-10 分钟
- **完整测试**: 30-60 分钟
- **深度审查**: 2-4 小时

---

## 📋 执行步骤

### 阶段 1: 环境准备 (5分钟)

```bash
# 1. 检查依赖
which python3 curl jq node pnpm

# 2. 克隆/进入仓库
cd /path/to/Kat_Rec

# 3. 安装后端依赖
cd kat_rec_web/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. 安装前端依赖（可选，用于前端测试）
cd ../frontend
pnpm install  # 或 npm install
```

### 阶段 2: 启动服务 (2分钟)

**终端 1 - 后端**:
```bash
cd kat_rec_web/backend
source .venv/bin/activate
export USE_MOCK_MODE=false
uvicorn main:app --reload --port 8000
```

**终端 2 - 前端（可选）**:
```bash
cd kat_rec_web/frontend
pnpm dev
```

### 阶段 3: 快速验证 (5分钟)

```bash
# 运行一键验证脚本
bash scripts/verify_sprint6.sh
```

**期望**: 所有端点返回有效 JSON，无 500 错误

### 阶段 4: 完整测试 (20-30分钟)

```bash
# 运行完整验收测试
bash scripts/sprint6_acceptance_test.sh
```

**期望**: 所有自动化测试通过

### 阶段 5: WebSocket 专项测试 (5分钟)

```bash
# 安装 websockets 库
pip install websockets

# 运行 WS 测试
python3 scripts/sprint6_websocket_test.py
```

**期望**: 
- 心跳 ≥1 次
- 版本号单调递增
- 批量缓冲 ~100ms

### 阶段 6: 熵报告生成 (2分钟)

```bash
# 生成熵报告
bash scripts/entropy_report.sh

# 查看报告
cat docs/ENTROPY_REPORT.md
cat docs/FRONTEND_SIZE.txt
```

### 阶段 7: 代码审查 (可选，1-2小时)

```bash
# 查看代码地图
cat docs/REPO_MAP.md

# 查看 API 契约
cat docs/T2R_API_SCHEMA.md

# 运行类型检查
cd kat_rec_web/frontend
pnpm type-check

# 运行后端测试
cd ../backend
pytest tests/ -v
```

---

## 📊 通过标准

### 必须通过（红线）

- [ ] `/health` 返回 `{"status":"ok"}`
- [ ] `/metrics/system` 返回有效数据
- [ ] `/metrics/ws-health` 返回连接统计
- [ ] WS 版本号单调递增
- [ ] WS 心跳 ≥1次（5s间隔）
- [ ] Plan 生成带 hash 的 recipe
- [ ] Run 立即返回 run_id
- [ ] 无临时文件残留

### 建议通过

- [ ] 完整验收测试通过
- [ ] WebSocket 批量缓冲正常
- [ ] Journal 恢复功能正常

---

## 🔍 检查清单

### 代码结构

- [ ] 后端 T2R 模块完整（20个文件）
- [ ] 前端组件结构清晰
- [ ] 配置文件统一

### 文档

- [ ] `REPO_MAP.md` 存在且完整
- [ ] `T2R_API_SCHEMA.md` 反映当前实现
- [ ] `AUDIT_README.md` 清晰易懂

### 脚本

- [ ] 所有测试脚本可执行
- [ ] 验证脚本返回预期结果
- [ ] 熵报告可生成

### 运行时

- [ ] 后端正常启动
- [ ] API 端点响应正常
- [ ] WebSocket 连接成功
- [ ] 后台任务执行正常

---

## 📝 审计报告模板

```
# T2R 系统审计报告

**审计日期**: YYYY-MM-DD
**审计员**: [Name]
**审计版本**: Sprint 6

## 环境
- Python: 3.x.x
- Node.js: 20.x.x
- 后端模式: mock/production

## 测试结果

### 快速验证
- [ ] /health: PASS/FAIL
- [ ] /metrics/system: PASS/FAIL
- [ ] /metrics/ws-health: PASS/FAIL

### 完整测试
- [ ] Smoke Test: PASS/FAIL
- [ ] WebSocket: PASS/FAIL
- [ ] 重试与恢复: PASS/FAIL
- [ ] 原子写入: PASS/FAIL

### 代码审查
- [ ] 代码结构: PASS/FAIL
- [ ] 文档完整性: PASS/FAIL
- [ ] 配置管理: PASS/FAIL

## 发现的问题
1. [列出问题]

## 建议
1. [列出建议]

## 总体评估
- 通过/部分通过/不通过
```

---

## 🔗 相关资源

- [AUDIT_README.md](AUDIT_README.md) - 快速入口
- [SPRINT6_TESTING_GUIDE.md](SPRINT6_TESTING_GUIDE.md) - 详细测试指南
- [CODE_REVIEW_REPORT.md](CODE_REVIEW_REPORT.md) - 代码审查报告
- [FINAL_AUDIT_CHECKLIST.md](FINAL_AUDIT_CHECKLIST.md) - 最终检查清单

---

**审计准备状态**: ✅ **就绪**

