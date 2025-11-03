#!/usr/bin/env python3
# coding: utf-8
"""
YouTube OAuth 设置向导

帮助用户配置 OAuth 2.0 凭证
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def print_setup_instructions():
    """打印设置说明"""
    print("=" * 70)
    print("📺 YouTube OAuth 2.0 配置向导")
    print("=" * 70)
    print()
    
    print("步骤 1: 创建 Google Cloud 项目")
    print("  - 访问: https://console.cloud.google.com/")
    print("  - 创建新项目或选择现有项目")
    print()
    
    print("步骤 2: 启用 YouTube Data API v3")
    print("  - 在 Google Cloud Console 中，转到 'APIs & Services' → 'Library'")
    print("  - 搜索 'YouTube Data API v3'")
    print("  - 点击 '启用'")
    print()
    
    print("步骤 3: 创建 OAuth 2.0 凭证")
    print("  - 转到 'APIs & Services' → 'Credentials'")
    print("  - 点击 'Create Credentials' → 'OAuth 2.0 Client ID'")
    print("  - 如果首次创建，需要先配置 OAuth 同意屏幕")
    print("  - 应用类型选择 'Desktop app'")
    print("  - 输入名称（如：Kat Records Uploader）")
    print("  - 点击 'Create'")
    print()
    
    print("步骤 4: 下载凭证文件")
    print("  - 在凭证列表中，点击刚创建的 OAuth 2.0 客户端")
    print("  - 点击 'Download JSON'")
    print("  - 保存文件到:")
    client_secrets_path = REPO_ROOT / "config" / "google" / "client_secrets.json"
    print(f"     {client_secrets_path}")
    print()
    
    print("步骤 5: 验证文件位置")
    if client_secrets_path.exists():
        print(f"  ✅ 文件已存在: {client_secrets_path}")
        print("  ✅ 可以开始使用上传功能了！")
    else:
        print(f"  ⚠️  文件不存在: {client_secrets_path}")
        print("  💡 请将下载的 JSON 文件重命名为 'client_secrets.json'")
        print("     并放置在上面的路径")
        print()
        print("  快速命令:")
        print(f"    mv ~/Downloads/client_secret_*.json {client_secrets_path}")
    
    print()
    print("=" * 70)
    print("📖 详细说明请参考: docs/YOUTUBE_UPLOAD_GUIDE.md")
    print("=" * 70)

if __name__ == "__main__":
    print_setup_instructions()

