#!/bin/bash
# Kat Rec 项目状态快速检查脚本
# 修复了原始命令中的 shell 语法错误

set -euo pipefail

echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║                      Kat Rec 项目状态快速检查                                  ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# 1) 分支与最近提交
echo "📋 当前分支与最近提交:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
git branch --show-current
git log --oneline -5 --decorate
echo ""

# 2) 文档与审计产物
echo "📚 文档与审计产物:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "最新文档:"
ls -lt docs 2>/dev/null | head -5 || echo "  (docs 目录不存在)"
echo ""
echo "最新审计文件:"
ls -lt audit 2>/dev/null | head -5 || echo "  (audit 目录不存在)"
echo ""

# 3) 关键文件检查（Sprint 5/6 标志物）
echo "🔍 关键文件检查:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
files=(
  "kat_rec_web/backend/t2r/services/env_check.py"
  "kat_rec_web/backend/t2r/services/runbook_journal.py"
  "kat_rec_web/backend/t2r/services/retry_manager.py"
  "kat_rec_web/backend/t2r/routes/metrics.py"
  "kat_rec_web/backend/t2r/utils/atomic_write.py"
  "kat_rec_web/backend/t2r/utils/atomic_group.py"
  "kat_rec_web/docker-compose.yml"
  "docs/T2R_SPRINT5_COMPLETE.md"
  "docs/T2R_SPRINT6_COMPLETE.md"
  "docs/AUDIT_SPRINT6.md"
  "audit/ws_probe.py"
  "desktop/tauri/src-tauri/src/main.rs"
  "scripts/check_dry.sh"
)

for f in "${files[@]}"; do
  if [ -f "$f" ]; then
    echo "✅ $f"
  else
    echo "❌ $f (缺失)"
  fi
done
echo ""

# 4) 后端进程检查
echo "🔧 后端进程状态:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if pgrep -fl uvicorn >/dev/null 2>&1; then
  echo "✅ uvicorn 进程运行中:"
  pgrep -fl uvicorn | head -3
else
  echo "⚠️  uvicorn 未运行（如果未启动后端，这是正常的）"
fi
echo ""

# 5) 端点健康检查
echo "🌐 API 端点健康检查:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 尝试多个端口
for port in 8000 8010; do
  echo "检查端口 $port:"
  
  # /health
  if response=$(curl -s -f --connect-timeout 2 "http://127.0.0.1:$port/health" 2>/dev/null); then
    echo "  ✅ /health -> $port"
    echo "$response" | jq -r '.status // .' 2>/dev/null || echo "    $response"
  else
    echo "  ❌ /health -> $port (不可达)"
  fi
  
  # /api/t2r/scan (POST)
  scan_response=$(curl -s -X POST \
    --connect-timeout 2 \
    -H 'Content-Type: application/json' \
    -d '{}' \
    "http://127.0.0.1:$port/api/t2r/scan" 2>/dev/null || echo "")
  
  if [ -n "$scan_response" ] && echo "$scan_response" | jq -e . >/dev/null 2>&1; then
    echo "  ✅ /api/t2r/scan -> $port"
    echo "$scan_response" | jq '{status,summary,errors}' 2>/dev/null || echo "    $scan_response"
  else
    echo "  ⚠️  /api/t2r/scan -> $port (404 或未实现)"
  fi
  
  echo ""
done

echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║                              检查完成                                          ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"

