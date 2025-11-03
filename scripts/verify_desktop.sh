#!/usr/bin/env bash
set -euo pipefail

echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║                  桌面应用验证脚本                                              ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# 检查Tauri CLI
if ! command -v tauri &> /dev/null && [ ! -f desktop/tauri/node_modules/.bin/tauri ]; then
  echo "⚠️  Tauri CLI未安装"
  echo "安装命令：cd desktop/tauri && pnpm install"
  exit 1
fi

echo "✅ Tauri CLI已就绪"
echo ""

# 检查前端静态导出
if [ ! -d "kat_rec_web/frontend/out" ]; then
  echo "⚠️  前端未静态导出，需要先运行："
  echo "   cd kat_rec_web/frontend"
  echo "   NEXT_OUTPUT_MODE=export pnpm build"
  echo ""
  read -p "是否现在导出? (y/N) " -n 1 -r
  echo ""
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    cd kat_rec_web/frontend
    NEXT_OUTPUT_MODE=export pnpm build
    cd ../..
  else
    exit 1
  fi
fi

echo "✅ 前端静态导出存在"
echo ""

# 检查Tauri配置
if [ ! -f "desktop/tauri/src-tauri/tauri.conf.json" ]; then
  echo "❌ Tauri配置不存在"
  exit 1
fi

echo "✅ Tauri配置存在"
echo ""

# 验证Tauri配置中的distDir指向正确位置
dist_dir=$(jq -r '.build.distDir' desktop/tauri/src-tauri/tauri.conf.json 2>/dev/null || echo "")
if [ -n "$dist_dir" ]; then
  echo "📁 静态文件目录: $dist_dir"
  if [ -d "$dist_dir" ] || [ -d "kat_rec_web/frontend/$dist_dir" ]; then
    echo "✅ 目录存在"
  else
    echo "⚠️  目录不存在，需要先构建前端"
  fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "准备启动桌面应用"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "运行命令: make app:dev"
echo ""
echo "验证点："
echo "1. 应用窗口应自动打开"
echo "2. 检查控制台日志：后端进程启动"
echo "3. 等待 /health 端点就绪（≤20秒）"
echo "4. 应用应自动导航到 /t2r 页面"
echo "5. 验证 window.__API_BASE__ 和 window.__WS_BASE__ 已注入"

