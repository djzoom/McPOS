#!/bin/bash
# McPOS CLI 包装脚本 - 自动激活虚拟环境并运行命令

cd "$(dirname "$0")"

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "❌ 错误: 虚拟环境不存在 (venv/)"
    echo "   请先创建虚拟环境: python3 -m venv venv"
    exit 1
fi

# 激活虚拟环境并运行命令
source venv/bin/activate

# 执行传入的所有参数
exec python3 -m mcpos.cli.main "$@"

