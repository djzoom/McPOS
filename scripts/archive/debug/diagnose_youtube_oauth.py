#!/usr/bin/env python3
# coding: utf-8
"""
YouTube OAuth 诊断工具

检查 YouTube OAuth 配置状态，诊断问题并提供修复建议。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

try:
    from utils_logging import setup_logging, logger
    setup_logging()
except ImportError:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)

# 颜色输出
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
NC = "\033[0m"  # No Color


def check_client_secrets() -> tuple[bool, str]:
    """检查 client_secrets.json 文件"""
    client_secrets_path = REPO_ROOT / "config" / "google" / "client_secrets.json"
    
    if not client_secrets_path.exists():
        return False, f"❌ 文件不存在: {client_secrets_path}"
    
    try:
        with open(client_secrets_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if "installed" not in data:
            return False, "❌ 文件格式错误：缺少 'installed' 字段"
        
        installed = data["installed"]
        required_fields = ["client_id", "client_secret", "auth_uri", "token_uri"]
        missing = [f for f in required_fields if f not in installed]
        
        if missing:
            return False, f"❌ 缺少必需字段: {', '.join(missing)}"
        
        client_id = installed.get("client_id", "")
        if not client_id or len(client_id) < 10:
            return False, "❌ client_id 无效或为空"
        
        return True, f"✅ client_secrets.json 配置正确 (Client ID: {client_id[:20]}...)"
    
    except json.JSONDecodeError as e:
        return False, f"❌ JSON 解析错误: {e}"
    except Exception as e:
        return False, f"❌ 读取文件失败: {e}"


def check_token_file() -> tuple[bool, str, dict | None]:
    """检查 youtube_token.json 文件"""
    token_path = REPO_ROOT / "config" / "google" / "youtube_token.json"
    
    if not token_path.exists():
        return False, f"❌ Token 文件不存在: {token_path}", None
    
    try:
        with open(token_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        required_fields = ["token", "refresh_token", "client_id", "client_secret"]
        missing = [f for f in required_fields if f not in data]
        
        if missing:
            return False, f"❌ Token 文件缺少必需字段: {', '.join(missing)}", None
        
        # 检查 token 是否过期
        expiry_str = data.get("expiry")
        if expiry_str:
            try:
                expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                
                if expiry < now:
                    days_expired = (now - expiry).days
                    return (
                        False,
                        f"⚠️  Token 已过期 {days_expired} 天 (过期时间: {expiry_str})",
                        data
                    )
                else:
                    hours_remaining = (expiry - now).total_seconds() / 3600
                    return (
                        True,
                        f"✅ Token 有效 (剩余 {hours_remaining:.1f} 小时)",
                        data
                    )
            except (ValueError, TypeError) as e:
                return False, f"⚠️  无法解析过期时间: {e}", data
        
        return True, "✅ Token 文件存在（未设置过期时间）", data
    
    except json.JSONDecodeError as e:
        return False, f"❌ Token 文件 JSON 解析错误: {e}", None
    except Exception as e:
        return False, f"❌ 读取 Token 文件失败: {e}", None


def check_google_api_libraries() -> tuple[bool, str]:
    """检查 Google API 库是否已安装"""
    required_modules = [
        "googleapiclient",
        "google_auth_oauthlib",
        "google.auth",
    ]
    
    missing = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        return False, f"❌ 缺少依赖库: {', '.join(missing)}\n   安装命令: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
    
    return True, "✅ Google API 库已安装"


def test_api_connection() -> tuple[bool, str]:
    """测试 API 连接"""
    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "uploader"))
        sys.path.insert(0, str(REPO_ROOT / "src"))
        
        from upload_to_youtube import get_authenticated_service, load_config
        
        config = load_config()
        youtube = get_authenticated_service(config)
        
        # 尝试调用 API
        request = youtube.channels().list(part="snippet", mine=True)
        response = request.execute()
        
        if response.get("items"):
            channel = response["items"][0]
            return True, f"✅ API 连接正常\n   频道: {channel['snippet']['title']}"
        else:
            return True, "✅ API 连接正常（但未找到频道信息）"
    
    except Exception as e:
        error_str = str(e)
        
        if "403" in error_str or "accessNotConfigured" in error_str:
            return False, (
                "❌ YouTube Data API v3 未启用\n"
                "   解决步骤:\n"
                "   1. 访问 https://console.cloud.google.com/\n"
                "   2. 选择项目 → 'APIs & Services' → 'Library'\n"
                "   3. 搜索 'YouTube Data API v3' 并启用\n"
                "   4. 等待 2-5 分钟让更改生效"
            )
        elif "401" in error_str or "unauthorized" in error_str.lower():
            return False, (
                "❌ 认证失败：需要重新授权\n"
                "   运行: python scripts/refresh_youtube_token.py"
            )
        elif "refresh" in error_str.lower():
            return False, (
                "❌ Token 刷新失败：需要重新授权\n"
                "   运行: python scripts/refresh_youtube_token.py"
            )
        else:
            return False, f"❌ API 连接失败: {error_str}"


def print_fix_instructions():
    """打印修复说明"""
    logger.info("")
    logger.info(f"{BLUE}{'=' * 70}{NC}")
    logger.info(f"{BLUE}📋 YouTube OAuth 配置修复指南{NC}")
    logger.info(f"{BLUE}{'=' * 70}{NC}")
    logger.info("")
    logger.info("步骤 1: 检查 Google Cloud 项目")
    logger.info("  - 访问: https://console.cloud.google.com/")
    logger.info("  - 确认项目 ID 与 client_secrets.json 中的 project_id 匹配")
    logger.info("")
    logger.info("步骤 2: 启用 YouTube Data API v3")
    logger.info("  - 转到 'APIs & Services' → 'Library'")
    logger.info("  - 搜索 'YouTube Data API v3'")
    logger.info("  - 点击 '启用'")
    logger.info("")
    logger.info("步骤 3: 检查 OAuth 同意屏幕")
    logger.info("  - 转到 'APIs & Services' → 'OAuth consent screen'")
    logger.info("  - 确保应用已发布或您已添加测试用户")
    logger.info("")
    logger.info("步骤 4: 重新授权（如果需要）")
    logger.info("  - 运行: python scripts/refresh_youtube_token.py")
    logger.info("  - 或运行: python scripts/check_youtube_api.py")
    logger.info("")


def main():
    """主函数"""
    logger.info(f"{BLUE}🔍 YouTube OAuth 配置诊断{NC}")
    logger.info("=" * 70)
    logger.info("")
    
    all_ok = True
    results = []
    
    # 检查 1: client_secrets.json
    logger.info("检查 1/4: client_secrets.json")
    ok, msg = check_client_secrets()
    results.append(("client_secrets", ok, msg))
    if ok:
        logger.info(f"   {GREEN}{msg}{NC}")
    else:
        logger.info(f"   {RED}{msg}{NC}")
        all_ok = False
    logger.info("")
    
    # 检查 2: youtube_token.json
    logger.info("检查 2/4: youtube_token.json")
    ok, msg, token_data = check_token_file()
    results.append(("token_file", ok, msg))
    if ok:
        logger.info(f"   {GREEN}{msg}{NC}")
    else:
        logger.info(f"   {YELLOW}{msg}{NC}")
        if "过期" in msg:
            all_ok = False
    logger.info("")
    
    # 检查 3: Google API 库
    logger.info("检查 3/4: Google API 库")
    ok, msg = check_google_api_libraries()
    results.append(("api_libraries", ok, msg))
    if ok:
        logger.info(f"   {GREEN}{msg}{NC}")
    else:
        logger.info(f"   {RED}{msg}{NC}")
        all_ok = False
    logger.info("")
    
    # 检查 4: API 连接（如果 Token 过期但其他检查通过，尝试自动刷新）
    if all([r[1] for r in results[:3]]):
        logger.info("检查 4/4: API 连接测试")
        # 如果 Token 过期，先尝试自动刷新
        token_check = results[1]  # token_file 检查结果
        if not token_check[1] and "过期" in token_check[2]:
            logger.info(f"   {YELLOW}检测到 Token 过期，尝试自动刷新...{NC}")
            try:
                sys.path.insert(0, str(REPO_ROOT / "scripts" / "uploader"))
                sys.path.insert(0, str(REPO_ROOT / "src"))
                from upload_to_youtube import get_credentials, load_config
                config = load_config()
                creds = get_credentials(config)
                if creds and creds.valid:
                    logger.info(f"   {GREEN}✅ Token 自动刷新成功{NC}")
                else:
                    logger.info(f"   {YELLOW}⚠️  自动刷新失败，需要手动授权{NC}")
            except Exception as e:
                logger.info(f"   {YELLOW}⚠️  自动刷新失败: {e}{NC}")
        
        ok, msg = test_api_connection()
        results.append(("api_connection", ok, msg))
        if ok:
            logger.info(f"   {GREEN}{msg}{NC}")
        else:
            logger.info(f"   {RED}{msg}{NC}")
            all_ok = False
        logger.info("")
    else:
        logger.info("检查 4/4: API 连接测试")
        logger.info(f"   {YELLOW}⏭️  跳过（前置检查未通过）{NC}")
        logger.info("")
        results.append(("api_connection", False, "跳过"))
    
    # 总结
    logger.info("=" * 70)
    if all_ok:
        logger.info(f"{GREEN}✅ 所有检查通过！YouTube OAuth 配置正常{NC}")
        sys.exit(0)
    else:
        logger.info(f"{YELLOW}⚠️  发现问题，请根据上述提示修复{NC}")
        print_fix_instructions()
        sys.exit(1)


if __name__ == "__main__":
    main()

