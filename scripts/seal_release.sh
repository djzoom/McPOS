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

mkdir -p audit/golden_path_v0.9-rc0
curl -s http://127.0.0.1:8010/health | jq . > audit/golden_path_v0.9-rc0/health_check_final.json
curl -s http://127.0.0.1:8010/metrics/system | jq . > audit/golden_path_v0.9-rc0/metrics_system_final.json

# 更新验证报告时间戳
if [ -f audit/golden_path_v0.9-rc0/verification_report.md ]; then
  sed -i.bak "s/生成时间: .*/生成时间: $(date -u +'%Y-%m-%d %H:%M:%S UTC')/" audit/golden_path_v0.9-rc0/verification_report.md
  rm -f audit/golden_path_v0.9-rc0/verification_report.md.bak
fi

echo "✅ 验证数据已更新"
echo ""

# 提交更改
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. 提交更改"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

git add -A
git commit -m "chore: prepare v0.9-rc0 release

- Fix import paths (absolute imports for websocket)
- Add __init__.py guards for stable package structure
- Fix ws_probe.py to support --endpoint argument
- Add golden path verification artifacts
- Update frontend .env.local for 8010 port
- Add verification scripts and checklists

Closes: Sprint 6 golden path verification"

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

