#!/usr/bin/env python3
# coding: utf-8
"""
API配置向导

一次性配置所有API密钥，持久化存储
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))

from api_config import get_api_config, API_PROVIDERS


def validate_key_format(provider: str, key: str) -> tuple[bool, str]:
    """验证密钥格式"""
    provider_info = API_PROVIDERS[provider]
    
    if not key or not key.strip():
        return False, "密钥不能为空"
    
    key = key.strip()
    
    # 检查前缀（如果有）
    if provider_info["key_prefix"]:
        if not key.startswith(provider_info["key_prefix"]):
            return False, f"密钥格式错误：应该以 '{provider_info['key_prefix']}' 开头"
    
    # 检查最小长度
    if len(key) < 10:
        return False, "密钥长度异常（可能不完整）"
    
    return True, "密钥格式正确"


def configure_api_interactive():
    """交互式配置API"""
    config = get_api_config()
    
    print()
    print("=" * 70)
    print("🔑 API配置向导")
    print("=" * 70)
    print()
    print("此向导将帮助您一次性配置所有API密钥。")
    print("配置后将自动保存，无需重复输入。")
    print()
    print("支持的API提供商：")
    for provider_id, provider_info in API_PROVIDERS.items():
        current = "（当前默认）" if provider_id == config.get_provider() else ""
        print(f"  • {provider_info['name']} ({provider_id}){current}")
    print()
    
    # 选择默认API提供商
    print("=" * 70)
    print("步骤1：选择默认API提供商")
    print("=" * 70)
    print()
    
    providers_list = list(API_PROVIDERS.keys())
    for i, provider_id in enumerate(providers_list, 1):
        provider_info = API_PROVIDERS[provider_id]
        current = " ← 当前默认" if provider_id == config.get_provider() else ""
        print(f"  {i}. {provider_info['name']} ({provider_id}){current}")
    print()
    
    while True:
        choice = input(f"请选择默认API提供商 [1-{len(providers_list)}] (当前: {config.get_provider()}): ").strip()
        
        if not choice:
            # 保持当前默认
            break
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(providers_list):
                config.set_provider(providers_list[idx])
                print(f"✅ 已设置默认API提供商为: {API_PROVIDERS[providers_list[idx]]['name']}")
                break
            else:
                print(f"❌ 请输入 1-{len(providers_list)} 之间的数字")
        except ValueError:
            print("❌ 请输入有效的数字")
    
    print()
    
    # 配置各个API密钥
    print("=" * 70)
    print("步骤2：配置API密钥")
    print("=" * 70)
    print()
    print("您可以为每个API提供商配置密钥，至少需要配置一个。")
    print("未配置的API将无法使用。")
    print()
    
    configured_count = 0
    
    for provider_id, provider_info in API_PROVIDERS.items():
        print(f"\n📋 {provider_info['name']} ({provider_id})")
        print("-" * 70)
        
        # 检查是否已有密钥
        existing_key, source = config.get_api_key(provider_id)
        if existing_key:
            print(f"✅ 已配置密钥 ({source})")
            replace = input("是否重新配置？(y/N): ").strip().lower()
            if replace != 'y':
                configured_count += 1
                continue
        
        print()
        print(f"如何获取 {provider_info['name']} API密钥：")
        if provider_id == "openai":
            print("  1. 访问: https://platform.openai.com/api-keys")
            print("  2. 登录OpenAI账户")
            print("  3. 创建新密钥（格式：sk-...）")
        elif provider_id == "gemini":
            print("  1. 访问: https://makersuite.google.com/app/apikey")
            print("  2. 登录Google账户")
            print("  3. 创建新API密钥")
        print()
        
        while True:
            try:
                print()
                print("🔐 安全提示：")
                print("  • 输入时密钥不会显示在屏幕上（不回显）")
                print("  • 密钥将保存在本地配置文件：config/api_config.json")
                print("  • 文件权限自动设置为600（仅您可读）")
                print("  • 配置文件已在.gitignore中，不会被提交到Git")
                print()
                key = getpass.getpass(f"请输入 {provider_info['name']} API密钥 (留空跳过): ").strip()
                
                if not key:
                    print("⏭️  已跳过")
                    break
                
                # 验证格式
                is_valid, msg = validate_key_format(provider_id, key)
                if not is_valid:
                    print(f"❌ {msg}")
                    retry = input("是否重新输入？(y/N): ").strip().lower()
                    if retry != 'y':
                        break
                    continue
                
                # 保存密钥
                config.set_api_key(provider_id, key, save=True)
                print(f"✅ {provider_info['name']} API密钥已保存")
                configured_count += 1
                break
                
            except KeyboardInterrupt:
                print("\n\n❌ 已取消")
                sys.exit(1)
            except Exception as e:
                print(f"❌ 配置失败: {e}")
                retry = input("是否重新输入？(y/N): ").strip().lower()
                if retry != 'y':
                    break
    
    print()
    print("=" * 70)
    print("✅ 配置完成")
    print("=" * 70)
    print()
    
    if configured_count == 0:
        print("⚠️  警告：未配置任何API密钥！")
        print("   您需要至少配置一个API密钥才能使用系统。")
        sys.exit(1)
    
    print(f"📊 配置统计：")
    print(f"  已配置: {configured_count}/{len(API_PROVIDERS)} 个API")
    print(f"  默认提供商: {API_PROVIDERS[config.get_provider()]['name']}")
    print()
    print(f"💾 配置已保存到: {config.config_path}")
    print(f"   权限: 600（仅所有者可读）")
    print(f"   状态: 已在.gitignore中，不会被提交到Git")
    print()
    print("✅ 安全措施：")
    print("  • 文件权限：600（仅您可读可写）")
    print("  • Git保护：不会被意外提交")
    print("  • 本地存储：仅存储在您的电脑")
    print()
    print("💡 下次运行时，系统会自动使用已配置的API密钥。")
    print("   无需重复输入！重启后仍然有效！")
    print()
    print("📋 关于API密钥有效期：")
    print("  • OpenAI/Gemini密钥通常永久有效")
    print("  • 如果泄露，请在对应平台删除并重新生成")
    print("  • 可通过 终端菜单 → 3 → 1 检查API状态")


if __name__ == "__main__":
    try:
        configure_api_interactive()
    except KeyboardInterrupt:
        print("\n\n❌ 已取消")
        sys.exit(1)

