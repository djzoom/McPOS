#!/bin/bash
# 启动后端服务脚本

set -e

echo "🚀 启动 Kat Rec 后端服务"
echo ""

# 检查是否在正确的目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/kat_rec_web/backend"

if [ ! -d "$BACKEND_DIR" ]; then
    echo "❌ 找不到后端目录: $BACKEND_DIR"
    exit 1
fi

# 切换到后端目录
cd "$BACKEND_DIR"

# 检查虚拟环境
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  未检测到虚拟环境"
    if [ -f "$PROJECT_ROOT/.venv311/bin/activate" ]; then
        echo "   激活虚拟环境..."
        source "$PROJECT_ROOT/.venv311/bin/activate"
    else
        echo "   请先激活虚拟环境或安装依赖"
    fi
fi

# 设置环境变量
export USE_MOCK_MODE=true
export LOG_LEVEL=${LOG_LEVEL:-INFO}

# 检查端口是否被占用
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  端口 8000 已被占用"
    echo "   正在尝试停止占用进程..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# 启动服务
echo "✅ 启动后端服务（Mock 模式）"
echo "   端口: 8000"
echo "   日志级别: $LOG_LEVEL"
echo ""

uvicorn main:app --reload --port 8000 --host 0.0.0.0

