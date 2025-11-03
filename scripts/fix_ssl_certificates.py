#!/usr/bin/env python3
# coding: utf-8
"""
修复 macOS SSL 证书问题

解决 Python 在 macOS 上 SSL 证书验证失败的问题
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def find_python_cert_installer():
    """查找 Python 证书安装脚本"""
    import glob
    
    possible_paths = [
        "/Applications/Python 3.*/Install Certificates.command",
        "/Applications/Python 3.*/*/Install Certificates.command",
    ]
    
    for pattern in possible_paths:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    
    return None


def fix_with_certifi():
    """通过升级 certifi 修复"""
    print("🔧 方法 1: 升级 certifi 包...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "certifi"],
            check=True,
            cwd=REPO_ROOT
        )
        print("✅ certifi 已升级")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 升级失败: {e}")
        return False


def fix_with_python_installer():
    """使用 Python 自带的证书安装脚本"""
    installer = find_python_cert_installer()
    if not installer:
        print("⚠️  未找到 Python 证书安装脚本")
        return False
    
    print(f"🔧 方法 2: 运行 Python 证书安装脚本...")
    print(f"   路径: {installer}")
    try:
        # macOS 脚本需要用 bash 运行
        subprocess.run(["bash", installer], check=True)
        print("✅ 证书安装脚本已运行")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 运行失败: {e}")
        return False


def test_ssl_connection():
    """测试 SSL 连接"""
    print("\n🧪 测试 SSL 连接...")
    try:
        import ssl
        import urllib.request as req
        
        # 尝试连接一个 HTTPS 网站
        context = ssl.create_default_context()
        test_url = "https://www.python.org"
        
        with req.urlopen(test_url, timeout=5, context=context) as response:
            if response.getcode() == 200:
                print("✅ SSL 连接测试成功！")
                return True
            else:
                print(f"⚠️  连接返回状态码: {response.getcode()}")
                return False
    except Exception as e:
        print(f"❌ SSL 连接测试失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 70)
    print("🔒 SSL 证书修复工具")
    print("=" * 70)
    print()
    print("此工具将尝试修复 macOS 上的 SSL 证书验证问题。")
    print()
    
    # 先测试当前状态
    if test_ssl_connection():
        print("\n✅ 您的 SSL 证书配置正常，无需修复！")
        return 0
    
    print("\n⚠️  检测到 SSL 证书问题，开始修复...\n")
    
    # 方法 1: 升级 certifi
    if fix_with_certifi():
        if test_ssl_connection():
            print("\n✅ 修复成功！SSL 证书问题已解决。")
            return 0
    
    # 方法 2: 使用 Python 安装脚本
    if fix_with_python_installer():
        if test_ssl_connection():
            print("\n✅ 修复成功！SSL 证书问题已解决。")
            return 0
    
    # 如果都失败了
    print("\n" + "=" * 70)
    print("❌ 自动修复失败")
    print("=" * 70)
    print()
    print("请尝试手动修复：")
    print()
    print("1. 运行 Python 证书安装脚本：")
    installer = find_python_cert_installer()
    if installer:
        print(f"   bash {installer}")
    else:
        print("   /Applications/Python\\ 3.*/Install\\ Certificates.command")
    print()
    print("2. 或手动升级 certifi：")
    print(f"   {sys.executable} -m pip install --upgrade certifi")
    print()
    print("3. 或设置环境变量（不推荐，仅临时解决）：")
    print("   export SSL_CERT_FILE=$(python -m certifi)")
    print()
    
    return 1


if __name__ == "__main__":
    sys.exit(main())

