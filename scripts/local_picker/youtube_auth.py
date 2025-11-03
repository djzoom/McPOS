#!/usr/bin/env python3
# coding: utf-8
"""
YouTube OAuth 2.0 认证模块

功能：
1. OAuth 2.0 认证流程（本地回调）
2. Token 持久化与自动刷新
3. 认证状态检查
"""
from __future__ import annotations

import json
import sys
import webbrowser
from pathlib import Path
from typing import Optional

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    print("⚠️  Google API 库未安装，请运行: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    sys.exit(1)

# OAuth 2.0 配置
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLIENT_SECRETS_FILE = REPO_ROOT / "config" / "google" / "client_secrets.json"
TOKEN_FILE = REPO_ROOT / "config" / "google" / "youtube_token.json"


class YouTubeAuthError(Exception):
    """YouTube认证错误"""
    pass


def get_credentials() -> Optional[Credentials]:
    """
    获取有效的认证凭据
    
    如果token存在且有效，直接返回
    如果token过期，自动刷新
    如果token不存在，返回None（需要用户授权）
    """
    if not GOOGLE_API_AVAILABLE:
        raise YouTubeAuthError("Google API 库未安装")
    
    # 检查凭证文件
    if not CLIENT_SECRETS_FILE.exists():
        return None
    
    creds = None
    
    # 加载已保存的token
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception as e:
            print(f"⚠️  加载token失败: {e}")
            # token文件可能损坏，删除它
            TOKEN_FILE.unlink()
    
    # 如果token无效或过期，尝试刷新
    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                print("🔄 Token已过期，正在刷新...")
                creds.refresh(Request())
                save_credentials(creds)
                print("✅ Token已刷新")
            except Exception as e:
                print(f"⚠️  Token刷新失败: {e}")
                print("💡 需要重新授权，请运行: python scripts/local_picker/youtube_upload.py --setup")
                creds = None
        else:
            creds = None
    
    return creds


def save_credentials(creds: Credentials) -> None:
    """保存认证凭据到文件"""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # 保存token（包含敏感信息）
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes,
    }
    if creds.expiry:
        token_data['expiry'] = creds.expiry.isoformat()
    
    # 设置文件权限为600（仅所有者可读写）
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2), encoding='utf-8')
    TOKEN_FILE.chmod(0o600)
    
    print(f"✅ Token已保存到: {TOKEN_FILE}")


def authorize() -> Credentials:
    """
    执行首次OAuth授权流程
    
    流程：
    1. 检查client_secrets.json是否存在
    2. 启动OAuth流程
    3. 打开浏览器引导用户授权
    4. 保存token
    """
    if not GOOGLE_API_AVAILABLE:
        raise YouTubeAuthError("Google API 库未安装")
    
    if not CLIENT_SECRETS_FILE.exists():
        raise YouTubeAuthError(
            f"❌ OAuth凭证文件不存在: {CLIENT_SECRETS_FILE}\n"
            f"请按照以下步骤配置：\n"
            f"1. 访问 https://console.cloud.google.com/\n"
            f"2. 创建项目并启用 YouTube Data API v3\n"
            f"3. 创建OAuth 2.0客户端ID（桌面应用）\n"
            f"4. 下载凭证文件并保存为: {CLIENT_SECRETS_FILE}"
        )
    
    print("🔐 开始OAuth授权流程...")
    print(f"📁 使用凭证文件: {CLIENT_SECRETS_FILE}")
    
    # 启动OAuth流程
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        SCOPES
    )
    
    # 本地服务器回调（用于桌面应用）
    print("🌐 正在打开浏览器进行授权...")
    creds = flow.run_local_server(port=0, open_browser=True)
    
    # 保存token
    save_credentials(creds)
    
    print("✅ 授权完成！")
    return creds


def get_authenticated_service():
    """
    获取已认证的YouTube API服务对象
    
    如果token不存在或无效，会自动尝试刷新或提示授权
    """
    creds = get_credentials()
    
    if not creds or not creds.valid:
        # 如果没有有效token，尝试授权
        print("⚠️  未找到有效token，开始授权流程...")
        creds = authorize()
    
    try:
        service = build('youtube', 'v3', credentials=creds)
        return service
    except Exception as e:
        raise YouTubeAuthError(f"创建YouTube API服务失败: {e}")


def check_auth_status() -> bool:
    """检查认证状态"""
    creds = get_credentials()
    return creds is not None and creds.valid


def setup_auth() -> None:
    """设置向导：引导用户完成OAuth配置"""
    print("=" * 70)
    print("📺 YouTube上传功能 - OAuth配置向导")
    print("=" * 70)
    print()
    
    # 检查凭证文件
    if CLIENT_SECRETS_FILE.exists():
        print(f"✅ 已找到OAuth凭证文件: {CLIENT_SECRETS_FILE}")
    else:
        print(f"❌ 未找到OAuth凭证文件: {CLIENT_SECRETS_FILE}")
        print()
        print("📋 配置步骤：")
        print("1. 访问 Google Cloud Console: https://console.cloud.google.com/")
        print("2. 创建新项目（或选择现有项目）")
        print("3. 启用 YouTube Data API v3:")
        print("   - 在API库中搜索 'YouTube Data API v3'")
        print("   - 点击 '启用'")
        print("4. 创建OAuth 2.0凭证：")
        print("   - 转到 '凭据' 页面")
        print("   - 点击 '创建凭据' → 'OAuth 2.0 客户端ID'")
        print("   - 应用类型选择 '桌面应用'")
        print("   - 下载JSON文件")
        print(f"   - 保存为: {CLIENT_SECRETS_FILE}")
        print()
        return
    
    # 检查token
    if TOKEN_FILE.exists():
        print(f"✅ 已找到Token文件: {TOKEN_FILE}")
        creds = get_credentials()
        if creds and creds.valid:
            print("✅ Token有效，无需重新授权")
            return
        else:
            print("⚠️  Token无效或已过期，需要重新授权")
    else:
        print("⚠️  未找到Token文件，需要首次授权")
    
    print()
    print("🔐 开始授权流程...")
    try:
        authorize()
        print()
        print("✅ 配置完成！现在可以使用YouTube上传功能了")
    except Exception as e:
        print(f"❌ 授权失败: {e}")
        print()
        print("💡 提示：")
        print("   - 确保已正确配置client_secrets.json")
        print("   - 确保已启用YouTube Data API v3")
        print("   - 确保网络连接正常")


if __name__ == "__main__":
    # 运行设置向导
    setup_auth()

