#!/usr/bin/env python3
# coding: utf-8
"""
检查 YouTube Data API v3 启用状态
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))

try:
    from youtube_auth import get_authenticated_service
except ImportError as e:
    print(f"❌ 无法导入认证模块: {e}")
    sys.exit(1)

def check_api_status():
    """检查 API 状态"""
    print("🔍 检查 YouTube Data API v3 状态...")
    print()
    
    try:
        # 尝试获取认证服务（这会触发 API 调用）
        youtube = get_authenticated_service()
        
        # 尝试调用一个简单的 API（获取频道信息）
        print("📡 测试 API 连接...")
        request = youtube.channels().list(part="snippet", mine=True)
        response = request.execute()
        
        print("✅ YouTube Data API v3 已启用并可正常使用")
        print()
        
        if response.get("items"):
            channel = response["items"][0]
            print(f"📺 频道: {channel['snippet']['title']}")
        else:
            print("⚠️  未找到频道信息（可能需要授权）")
        
        return True
        
    except Exception as e:
        error_str = str(e)
        
        if "403" in error_str or "accessNotConfigured" in error_str:
            print("❌ YouTube Data API v3 未启用")
            print()
            print("🔧 解决步骤：")
            print("   1. 访问 Google Cloud Console：")
            print("      https://console.cloud.google.com/")
            print()
            print("   2. 选择项目并转到 'APIs & Services' → 'Library'")
            print()
            print("   3. 搜索 'YouTube Data API v3'")
            print()
            print("   4. 点击 '启用'")
            print()
            print("   5. 等待 2-5 分钟让更改生效")
            print()
            print("   或直接访问：")
            print("   https://console.developers.google.com/apis/api/youtube.googleapis.com/overview")
            return False
        elif "401" in error_str or "unauthorized" in error_str.lower():
            print("⚠️  认证问题：需要重新授权")
            print()
            print("💡 运行上传命令时会自动触发授权流程")
            return False
        else:
            print(f"❌ API 检查失败: {e}")
            return False

if __name__ == "__main__":
    success = check_api_status()
    sys.exit(0 if success else 1)

