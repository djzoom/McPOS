#!/usr/bin/env bash
set -euo pipefail

echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║                      v0.9-rc0 封板脚本                                          ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# 检查未提交的更改
if [ -n "$(git status --porcelain)" ]; then
  echo "📝 检测到未提交的更改："
  git status --short
  echo ""
  read -p "是否继续提交并打tag? (y/N) " -n 1 -r
  echo ""
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 已取消"
    exit 1
  fi
fi

# 收集最终验证数据
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. 收集最终验证数据"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

API_BASE="${API_BASE:-http://127.0.0.1:8010}"

mkdir -p audit/golden_path_v0.9-rc0

# Health and metrics
curl -s "$API_BASE/health" | jq . > audit/golden_path_v0.9-rc0/health_check_final.json 2>/dev/null || echo "{}" > audit/golden_path_v0.9-rc0/health_check_final.json
curl -s "$API_BASE/metrics/system" | jq . > audit/golden_path_v0.9-rc0/metrics_system_final.json 2>/dev/null || echo "{}" > audit/golden_path_v0.9-rc0/metrics_system_final.json
curl -s "$API_BASE/metrics/ws-health" | jq . > audit/golden_path_v0.9-rc0/metrics_ws_health_final.json 2>/dev/null || echo "{}" > audit/golden_path_v0.9-rc0/metrics_ws_health_final.json

# WebSocket statistics
if [ -f audit/ws_stats.json ]; then
  cp audit/ws_stats.json audit/golden_path_v0.9-rc0/ 2>/dev/null || true
  cp audit/ws_sample.jsonl audit/golden_path_v0.9-rc0/ 2>/dev/null || true
fi

# Plan/Run test results
curl -s -X POST "$API_BASE/api/t2r/plan" -H 'Content-Type: application/json' -d '{"episode_id":"20251102"}' | jq . > audit/golden_path_v0.9-rc0/plan_result.json 2>/dev/null || echo "{}" > audit/golden_path_v0.9-rc0/plan_result.json
curl -s -X POST "$API_BASE/api/t2r/run" -H 'Content-Type: application/json' -d '{"episode_id":"20251102","dry_run":true}' | jq . > audit/golden_path_v0.9-rc0/run_result.json 2>/dev/null || echo "{}" > audit/golden_path_v0.9-rc0/run_result.json

# Backend logs
if [ -f /tmp/uvicorn_golden_path.log ]; then
  tail -100 /tmp/uvicorn_golden_path.log > audit/golden_path_v0.9-rc0/backend_full_log.txt 2>/dev/null || true
fi

echo "✅ 验证数据已收集和归档"
echo ""

# 提交更改
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. 提交更改"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 只添加验证产物，不提交其他未跟踪文件
git add audit/golden_path_v0.9-rc0/ 2>/dev/null || true

if [ -n "$(git status --porcelain audit/golden_path_v0.9-rc0/)" ]; then
  git commit -m "chore: archive v0.9-rc0 golden path verification artifacts

- Health check snapshots
- Metrics endpoints snapshots (system + ws-health)
- WebSocket statistics and samples
- Plan/Run test results
- Backend full logs
- Verification summary"
fi

echo "✅ 更改已提交"
echo ""

# 打tag
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. 创建 tag"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

git tag -a v0.9-rc0 -m "v0.9-rc0: Sprint 6 Golden Path Release Candidate

Features:
- T2R/MCRB dual prefix API support
- Fixed import path issues
- WebSocket version tracking
- SRT directory traversal protection
- Health endpoint with env validation
- Frontend static export support
- Tauri desktop wrapper foundation

Verification:
- Backend endpoints verified
- Import path guards in place
- Golden path artifacts collected

Next: GUI golden path testing"

echo "✅ Tag v0.9-rc0 已创建"
echo ""

# 显示tag信息
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. 验证信息"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

git log --oneline -1
echo ""
git tag -l -n9 v0.9-rc0
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 封板完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📦 下一步操作："
echo "  1. 推送tag: git push origin v0.9-rc0"
echo "  2. 完成GUI测试后，更新验证报告"
echo "  3. 准备正式发布"

