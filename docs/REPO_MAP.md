# REPO_MAP - Kat_Rec / kat_rec_web

本文件梳理关键代码目录、文件与用途，供第三方审计快速定位。

## 顶层结构

```
kat_rec_web/
  backend/        # FastAPI 后端
  frontend/       # Next.js 前端
  data/           # 数据输出（不入库）
  output/         # 生成产物（不入库）
  docs/           # 文档
  scripts/        # 自动化脚本
```

## 后端（backend）

- `backend/main.py`: FastAPI 入口，注册路由、lifespan、/health。
- `backend/routes/websocket.py`: WebSocket 端点、心跳、批量缓冲、版本号。
- `backend/routes/control.py`: 任务控制 API（mock/扩展）。
- `backend/t2r/router.py`: T2R 路由聚合。
- `backend/t2r/routes/scan.py`: `POST /api/t2r/scan`，锁定/索引构建与事件广播。
- `backend/t2r/routes/srt.py`: `POST /api/t2r/srt/*`，SRT 检查与修复。
- `backend/t2r/routes/plan.py`: `POST /api/episodes/plan|run`，Recipe 生成与 Runbook 后台执行、journal。
- `backend/t2r/routes/metrics.py`: `/metrics/system` 与 `/metrics/ws-health`。
- `backend/core/websocket_manager.py`: 连接管理、5s 心跳、15s 清理、100ms 批量。
- `backend/t2r/services/schedule_service.py`: 排播读取/写入、原子写入。
- `backend/t2r/services/runbook_journal.py`: 运行日志、恢复入口。
- `backend/t2r/services/retry_manager.py`: 重试策略加载与指数退避执行。
- `backend/t2r/utils/atomic_write.py`: 原子写入工具。
- `backend/t2r/utils/atomic_group.py`: 事务组写入工具。
- `backend/t2r/events/schema.py` (新增): WS 事件模式集中定义（{type, ts, level, version, data}）。

## 前端（frontend）

- `frontend/app/(t2r)/t2r/page.tsx`: Reality Board 入口。
- `frontend/components/t2r/*`: 八大板块组件（Channel Overview, Schedule Doctor 等）。
- `frontend/components/MissionControl/*`: Mission Control 指标区块。
- `frontend/components/SystemFeed.tsx`: 右下事件流。
- `frontend/services/api.ts` / `frontend/services/t2rApi.ts`: REST API 封装。
- `frontend/services/wsClient.ts`: WebSocket 客户端（指数退避、心跳、去重）。
- `frontend/hooks/useT2RWebSocket.ts`: 订阅 /ws/* 并分发到各 store。
- `frontend/stores/*`: Zustand stores（t2rScheduleStore, runbookStore 等）。
- `frontend/src/types/openapi.d.ts` (生成目标): OpenAPI TS 类型。
- `frontend/src/types/events.ts` (新增): WS 事件联合类型镜像。
- `frontend/src/stores/_shapeCheck.ts` (新增): Zustand 切片 shape 类型检查。

## 脚本（scripts）

- `scripts/verify_t2r.sh`: Sprint 验证脚本。
- `scripts/sprint6_acceptance_test.sh` (新增): Sprint 6 验收与压力测试一键脚本。
- `scripts/sprint6_websocket_test.py` (新增): WS 完整性检测。
- `scripts/entropy_report.sh` (新增): 体积/依赖熵报告。
- `scripts/verify_sprint6.sh` (新增): 健康与指标+计划/运行的快速验证。

## 文档（docs）

- `docs/T2R_PRODUCTION_READY.md`: 生产就绪说明。
- `docs/T2R_SPRINT5_COMPLETE.md`: Sprint 5 完成总结。
- `docs/T2R_SPRINT6_COMPLETE.md`: Sprint 6 完成总结。
- `docs/SPRINT6_TESTING_GUIDE.md`: 测试指南（粘贴即跑）。
- `docs/T2R_API_SCHEMA.md` (新增): REST+WS 合同归档（镜像当前实现）。
- `docs/ENTROPY_REPORT.md` (新增): 体积与依赖报告汇总。
- `docs/AUDIT_README.md` (新增): 第三方审计入口说明。
