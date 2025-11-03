# Third-Party Audit Guide

本文档为第三方审计员提供快速验证 T2R 系统的方法。

---

## 🎯 审计目标

验证以下功能是否正常：
1. 健康检查与系统指标
2. REST API 端点响应
3. WebSocket 事件流（版本号、心跳、批量缓冲）
4. 后台任务执行与恢复
5. 原子写入与幂等性

---

## 📋 前置要求

- Python 3.11+
- Node.js 20+ (可选，用于前端)
- curl, jq
- websockets Python 库 (用于 WS 测试)

---

## 🚀 快速验证（5分钟）

### 1. 启动后端

```bash
cd kat_rec_web/backend
export USE_MOCK_MODE=false
uvicorn main:app --reload --port 8000
```

**期望输出**: 
```
✅ Backend services initialized
✅ T2R routes enabled
Uvicorn running on http://127.0.0.1:8000
```

### 2. 运行一键验证脚本

```bash
cd /Users/z/Downloads/Kat_Rec
bash scripts/verify_sprint6.sh
```

**期望**: 所有端点返回有效 JSON，无 500 错误

### 3. 运行完整验收测试

```bash
bash scripts/sprint6_acceptance_test.sh
```

**期望**: 所有测试通过，显示 "🎉 Sprint 6 验收测试通过！"

---

## 📊 分步验证

### A. 健康检查

```bash
curl -s http://localhost:8000/health | jq
```

**通过标准**:
- `status: "ok"`
- `environment.paths_valid: true`

### B. 系统指标

```bash
curl -s http://localhost:8000/metrics/system | jq
```

**通过标准**:
- `cpu_percent: 0-100`
- `memory_mb > 0`
- `active_ws_connections >= 0`

### C. WebSocket 测试

```bash
python3 scripts/sprint6_websocket_test.py
```

**通过标准**:
- 心跳 ≥1 次
- 版本号单调递增
- 批量缓冲中位数 ~100ms

### D. 计划与执行

```bash
# 计划
curl -s -X POST http://localhost:8000/api/episodes/plan \
  -H 'Content-Type: application/json' \
  -d '{"episode_id":"AUDIT-TEST"}' | jq

# 运行
curl -s -X POST http://localhost:8000/api/episodes/run \
  -H 'Content-Type: application/json' \
  -d '{"episode_id":"AUDIT-TEST","stages":["remix"],"dry_run":true}' | jq
```

**通过标准**:
- Plan 返回 `recipe_json_path`
- Run 立即返回 `run_id` (不阻塞)

---

## 📁 关键文件检查

### 配置文件

```bash
# 重试策略
cat kat_rec_web/backend/t2r/config/retry_policy.json | jq

# 环境检查
cat kat_rec_web/backend/t2r/services/env_check.py | head -50
```

### 输出文件

```bash
# Recipe 文件（幂等命名）
ls -l data/CH-TEST-*.json

# Journal 文件
cat data/run_journal.json | jq '.runs | length'
```

### 无临时文件残留

```bash
find data -name "*.tmp" | wc -l
# 期望: 0
```

---

## 📈 熵报告

```bash
bash scripts/entropy_report.sh
cat docs/ENTROPY_REPORT.md
```

查看：
- 前端 node_modules 大小
- 最大依赖包
- Python 依赖冻结列表
- 文件数量统计

---

## 🔍 架构验证

### 代码结构

查看 `docs/REPO_MAP.md` 了解关键文件位置。

### API 契约

查看 `docs/T2R_API_SCHEMA.md` 了解完整的 REST + WS 契约。

### 类型一致性

```bash
# 前端类型检查
cd kat_rec_web/frontend
pnpm type-check

# 后端类型检查（如果配置了mypy）
cd kat_rec_web/backend
mypy . --ignore-missing-imports || echo "mypy not configured"
```

---

## 🧪 自动化测试

```bash
# 后端单元测试
cd kat_rec_web/backend
pytest tests/ -v

# 恢复功能测试
pytest tests/test_resume_run.py -v
```

---

## 📝 审计检查清单

- [ ] 健康检查返回 OK
- [ ] Metrics 端点可用
- [ ] WebSocket 连接成功
- [ ] 版本号单调递增
- [ ] 心跳间隔正常（~5s）
- [ ] 批量缓冲正常（~100ms）
- [ ] Plan 生成带 hash 的 recipe
- [ ] Run 立即返回（后台执行）
- [ ] Journal 记录完整
- [ ] 无临时文件残留
- [ ] 重试策略配置存在
- [ ] 原子写入正常

---

## 🚨 常见问题

### 后端无法启动

**检查**:
- Python 版本 ≥ 3.11
- 依赖已安装: `pip install -r requirements.txt`
- 端口 8000 未被占用

### WebSocket 测试失败

**检查**:
- `pip install websockets`
- 后端已启动
- 防火墙未阻止连接

### Plan/Run 返回错误

**检查**:
- 环境变量正确（USE_MOCK_MODE=false）
- 目录权限正常（LIBRARY_ROOT, OUTPUT_ROOT 可写）
- 查看后端日志获取详细错误

---

## 📚 相关文档

- [REPO_MAP.md](REPO_MAP.md) - 代码结构地图
- [T2R_API_SCHEMA.md](T2R_API_SCHEMA.md) - API 契约
- [SPRINT6_TESTING_GUIDE.md](SPRINT6_TESTING_GUIDE.md) - 详细测试指南
- [ENTROPY_REPORT.md](ENTROPY_REPORT.md) - 熵报告

---

**审计完成后，请在 `docs/SPRINT6_TEST_STATUS.md` 更新测试结果。**

