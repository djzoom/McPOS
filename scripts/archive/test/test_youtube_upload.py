#!/usr/bin/env python3
# coding: utf-8
"""
YouTube Upload 测试脚本

用于快速测试上传流程的各个组件
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "uploader"))
sys.path.insert(0, str(REPO_ROOT / "src"))

def test_imports():
    """测试依赖导入"""
    print("=" * 70)
    print("🔍 测试 1: 依赖导入")
    print("=" * 70)
    
    # 先检查 Google API 依赖
    try:
        import google.auth
        import google_auth_oauthlib
        import googleapiclient
        print("✅ Google API 依赖已安装")
    except ImportError as e:
        print(f"❌ Google API 依赖缺失: {e}")
        print("💡 请运行: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        return False
    
    # 再测试模块导入
    try:
        from upload_to_youtube import (
            load_config,
            get_credentials,
            authorize,
            get_authenticated_service,
            check_already_uploaded,
            read_metadata_files
        )
        print("✅ 所有模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_loading():
    """测试配置加载"""
    print("\n" + "=" * 70)
    print("🔍 测试 2: 配置加载")
    print("=" * 70)
    
    try:
        from upload_to_youtube import load_config
        config = load_config()
        
        print(f"✅ 配置加载成功")
        print(f"   - client_secrets_file: {config['client_secrets_file']}")
        print(f"   - token_file: {config['token_file']}")
        print(f"   - privacy_status: {config['privacy_status']}")
        print(f"   - category_id: {config['category_id']}")
        print(f"   - tags: {config['tags']}")
        
        # 检查文件是否存在
        if config['client_secrets_file'].exists():
            print(f"   ✅ client_secrets.json 存在")
        else:
            print(f"   ⚠️  client_secrets.json 不存在: {config['client_secrets_file']}")
            print(f"   💡 需要先下载 OAuth 凭证文件")
        
        return True
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_auth_status():
    """测试认证状态"""
    print("\n" + "=" * 70)
    print("🔍 测试 3: OAuth 认证状态")
    print("=" * 70)
    
    try:
        from upload_to_youtube import load_config, get_credentials
        config = load_config()
        
        creds = get_credentials(config)
        if creds and creds.valid:
            print("✅ Token 有效，已授权")
            print(f"   - Token 文件: {config['token_file']}")
            return True
        else:
            print("⚠️  Token 无效或不存在")
            print(f"   💡 需要运行授权流程")
            print(f"   💡 在首次上传时会自动触发授权")
            return False
    except Exception as e:
        print(f"❌ 认证检查失败: {e}")
        return False

def test_file_detection(episode_id: str = "20251102"):
    """测试文件检测"""
    print("\n" + "=" * 70)
    print(f"🔍 测试 4: 文件检测 (Episode: {episode_id})")
    print("=" * 70)
    
    try:
        from upload_to_youtube import read_metadata_files
        
        # 尝试找到视频文件
        output_dir = REPO_ROOT / "output"
        video_files = list(output_dir.glob(f"{episode_id}_youtube.mp4"))
        
        # 也检查最终文件夹
        for folder in output_dir.glob(f"{episode_id[:8]}-*"):
            video_files.extend(list(folder.glob(f"{episode_id}_youtube.mp4")))
        
        if not video_files:
            print(f"⚠️  未找到视频文件: {episode_id}_youtube.mp4")
            print(f"   💡 需要先运行 Stage 9 (视频渲染)")
            return False
        
        video_file = video_files[0]
        print(f"✅ 找到视频文件: {video_file}")
        
        # 测试元数据读取
        metadata = read_metadata_files(episode_id, video_file)
        
        print(f"\n📋 检测到的元数据:")
        print(f"   - 标题: {metadata['title'] or '未找到'}")
        print(f"   - 描述: {metadata['description'] and metadata['description'][:50] + '...' or '未找到'}")
        print(f"   - 字幕: {metadata['subtitle_path'] or '未找到'}")
        print(f"   - 缩略图: {metadata['thumbnail_path'] or '未找到'}")
        
        if metadata['title'] and metadata['description']:
            print("✅ 元数据完整，可以上传")
            return True
        else:
            print("⚠️  元数据不完整，但可以使用默认值")
            return True  # 仍然可以上传
            
    except Exception as e:
        print(f"❌ 文件检测失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_schedule_check(episode_id: str = "20251102"):
    """测试排播表检查"""
    print("\n" + "=" * 70)
    print(f"🔍 测试 5: 排播表检查 (Episode: {episode_id})")
    print("=" * 70)
    
    try:
        from upload_to_youtube import check_already_uploaded
        
        video_id = check_already_uploaded(episode_id)
        if video_id:
            print(f"✅ 期数已上传")
            print(f"   - YouTube Video ID: {video_id}")
            print(f"   💡 使用 --force 可以强制重新上传")
            return True
        else:
            print(f"✅ 期数未上传，可以执行上传")
            return True
            
    except Exception as e:
        print(f"⚠️  排播表检查失败（可能状态管理器未初始化）: {e}")
        print(f"   💡 这不会阻止上传，只是无法检查是否已上传")
        return True  # 不是致命错误

def main():
    """主测试流程"""
    print("\n" + "=" * 70)
    print("🧪 YouTube Upload 组件测试")
    print("=" * 70)
    
    results = {
        "依赖导入": test_imports(),
        "配置加载": test_config_loading(),
        "认证状态": test_auth_status(),
        "文件检测": test_file_detection(),
        "排播表检查": test_schedule_check(),
    }
    
    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n✅ 所有测试通过！可以执行上传")
        print("\n💡 上传命令:")
        print(f"   python scripts/kat_cli.py upload --episode 20251102")
        print(f"   或")
        print(f"   python scripts/uploader/upload_to_youtube.py --episode 20251102 --video output/...")
    else:
        print("\n⚠️  部分测试失败，请检查上述问题")
        if not results["认证状态"]:
            print("\n💡 首次使用需要 OAuth 授权：")
            print("   1. 确保 config/google/client_secrets.json 存在")
            print("   2. 运行上传命令时会自动触发授权流程")
            print("   3. 或运行: python scripts/local_picker/youtube_auth.py --setup")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

