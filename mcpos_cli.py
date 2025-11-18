#!/usr/bin/env python3
"""
McPOS CLI 入口脚本

临时方案：直接运行此脚本调用 CLI，直到通过 pip install -e . 安装后可以使用 mcpos 命令。

使用方法：
    python3 mcpos_cli.py init-episode kat kat_20241201
    python3 mcpos_cli.py run-episode kat kat_20241201
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入并运行 CLI
from mcpos.cli.main import app

if __name__ == "__main__":
    app()

