#!/usr/bin/env python3
# coding: utf-8
"""
检查 OpenAI API 就绪状态

功能：
1. 检查API密钥配置（文件/环境变量）
2. 测试API连接
3. 验证API功能（简单测试调用）
4. 显示配置状态

用法：
    python scripts/check_api_status.py
    python scripts/check_api_status.py --test  # 执行实际API测试
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))


def check_api_key_config() -> tuple[str | None, str]:
    """检查API密钥配置"""
    # 方法1：配置文件
    config_path = REPO_ROOT / "config" / "openai_api_key.txt"
    if config_path.exists():
        try:
            key = config_path.read_text().strip()
            if key:
                return key, "配置文件 (config/openai_api_key.txt)"
        except Exception as e:
            return None, f"配置文件读取失败: {e}"
    
    # 方法2：环境变量
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key, "环境变量 (OPENAI_API_KEY)"
    
    return None, "未找到配置"


def test_api_connection(api_key: str, test_call: bool = False) -> tuple[bool, str]:
    """
    测试API连接
    
    Args:
        api_key: API密钥
        test_call: 是否执行实际API调用测试
    
    Returns:
        (是否成功, 消息)
    """
    if not test_call:
        # 仅检查密钥格式
        if not api_key.startswith("sk-"):
            return False, "密钥格式不正确（应该以 'sk-' 开头）"
        if len(api_key) < 20:
            return False, "密钥长度异常（可能不完整）"
        return True, "密钥格式正确"
    
    # 执行实际API调用测试
    try:
        import json
        from urllib import request
        
        # 简单的API调用测试（列出模型，成本极低）
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": "test"}
            ],
            "max_tokens": 5
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            method="POST"
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")
        
        with request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return True, "API连接成功 ✅"
            else:
                return False, f"API返回错误状态码: {resp.status}"
                
    except request.HTTPError as e:
        if e.code == 401:
            return False, "API密钥无效（401 Unauthorized）"
        elif e.code == 429:
            return False, "API调用频率限制（429 Too Many Requests）"
        else:
            return False, f"API HTTP错误: {e.code} {e.reason}"
    except request.URLError as e:
        return False, f"网络连接失败: {e.reason}"
    except Exception as e:
        return False, f"API测试失败: {str(e)}"


def check_file_permissions() -> tuple[bool, str]:
    """检查配置文件权限"""
    config_path = REPO_ROOT / "config" / "openai_api_key.txt"
    if not config_path.exists():
        return True, "配置文件不存在（使用环境变量）"
    
    try:
        stat = config_path.stat()
        mode = stat.st_mode
        
        # 检查权限（应该是 600 或 400）
        # 600 = rw------- (所有者可读写)
        # 400 = r-------- (所有者只读)
        readable_by_others = bool(mode & 0o004) or bool(mode & 0o040)
        writable_by_others = bool(mode & 0o002) or bool(mode & 0o020)
        
        if readable_by_others or writable_by_others:
            return False, f"⚠️  文件权限不安全: {oct(mode & 0o777)} (应该是 600)"
        else:
            return True, f"✅ 文件权限安全: {oct(mode & 0o777)}"
    except Exception as e:
        return False, f"检查权限失败: {e}"


def check_git_status() -> tuple[bool, str]:
    """检查密钥文件是否在Git中"""
    config_path = REPO_ROOT / "config" / "openai_api_key.txt"
    if not config_path.exists():
        return True, "配置文件不存在"
    
    try:
        import subprocess
        # 检查是否被git追踪
        result = subprocess.run(
            ["git", "check-ignore", str(config_path)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT
        )
        
        if result.returncode == 0:
            return True, "✅ 密钥文件已在 .gitignore 中（不会被提交）"
        else:
            # 检查是否已被追踪
            tracked_result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", str(config_path)],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT
            )
            if tracked_result.returncode == 0:
                return False, "⚠️  警告：密钥文件已被Git追踪！需要从历史中移除"
            else:
                return True, "✅ 密钥文件未被Git追踪"
    except Exception:
        return True, "无法检查Git状态（Git可能未初始化）"


def main():
    parser = argparse.ArgumentParser(description="检查 OpenAI API 就绪状态")
    parser.add_argument(
        "--test",
        action="store_true",
        help="执行实际API调用测试（会产生少量费用）"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细信息"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🔍 OpenAI API 就绪状态检查")
    print("=" * 70)
    print("")
    
    # 1. 检查API密钥配置
    print("📋 1. API密钥配置检查")
    print("-" * 70)
    api_key, config_source = check_api_key_config()
    
    if api_key:
        # 只显示密钥的前8个字符和后4个字符（安全显示）
        key_display = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        print(f"✅ API密钥已配置")
        print(f"   来源: {config_source}")
        print(f"   密钥: {key_display}")
        print(f"   长度: {len(api_key)} 字符")
    else:
        print(f"❌ API密钥未配置")
        print(f"   来源: {config_source}")
        print(f"")
        print(f"💡 配置方法：")
        print(f"   1. 运行配置脚本: bash scripts/setup_api_key.sh")
        print(f"   2. 使用环境变量: export OPENAI_API_KEY='sk-...'")
        print(f"   3. 创建配置文件: echo 'sk-...' > config/openai_api_key.txt")
        print("")
        sys.exit(1)
    
    print("")
    
    # 2. 检查文件权限（如果使用配置文件）
    if "配置文件" in config_source:
        print("📋 2. 文件权限检查")
        print("-" * 70)
        is_safe, perm_msg = check_file_permissions()
        print(perm_msg)
        if not is_safe:
            print(f"💡 修复方法: chmod 600 config/openai_api_key.txt")
        print("")
    
    # 3. 检查Git状态
    if "配置文件" in config_source:
        print("📋 3. Git安全检查")
        print("-" * 70)
        is_safe, git_msg = check_git_status()
        print(git_msg)
        if not is_safe:
            print(f"💡 确保 .gitignore 包含: config/openai_api_key.txt")
        print("")
    
    # 4. API连接测试
    print("📋 4. API连接测试")
    print("-" * 70)
    
    if args.test:
        print("🔄 执行实际API调用测试...")
        success, msg = test_api_connection(api_key, test_call=True)
        print(msg)
        
        if success:
            print("")
            print("✅ API完全就绪！可以正常使用。")
        else:
            print("")
            print("❌ API测试失败")
            if "401" in msg or "无效" in msg:
                print("💡 请检查API密钥是否正确")
            elif "429" in msg or "频率" in msg:
                print("💡 API调用频率受限，请稍后重试")
            elif "网络" in msg:
                print("💡 请检查网络连接")
    else:
        success, msg = test_api_connection(api_key, test_call=False)
        print(msg)
        print("")
        print("💡 提示：使用 --test 参数执行实际API调用测试")
    
    print("")
    print("=" * 70)
    print("📊 总结")
    print("=" * 70)
    
    # 汇总状态
    all_ok = api_key is not None
    
    if args.test:
        if all_ok and success:
            print("✅ API完全就绪，可以使用！")
        else:
            print("⚠️  API配置存在问题，请根据上述提示修复")
    else:
        if all_ok:
            print("✅ API密钥已配置")
            print("💡 建议运行 --test 参数验证API连接")
        else:
            print("❌ API未配置，请先配置API密钥")
    
    print("")
    
    # 使用场景检查
    if api_key:
        print("📝 API使用场景：")
        print("   ✅ 唱片标题生成")
        print("   ✅ YouTube标题生成")
        print("   ✅ YouTube描述生成")
        print("   ✅ 排播表批量生成")
    
    return 0 if (api_key and (not args.test or success)) else 1


if __name__ == "__main__":
    sys.exit(main())

