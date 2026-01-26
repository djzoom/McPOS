#!/usr/bin/env python3
"""
快速检查当前渲染队列状态

用于评估重启时机

注意：此脚本需要后端服务运行，通过 API 调用检查状态
"""
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def check_render_queue_status(api_url: str = "http://localhost:8000") -> dict:
    """通过 API 检查渲染队列状态"""
    try:
        url = f"{api_url}/api/t2r/render-queue"
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="检查渲染队列状态")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API 服务器 URL (默认: http://localhost:8000)"
    )
    args = parser.parse_args()
    
    print("=" * 70)
    print("🔍 渲染队列状态检查")
    print("=" * 70)
    print(f"API URL: {args.api_url}\n")
    
    snapshot = check_render_queue_status(args.api_url)
    
    if "error" in snapshot:
        print(f"❌ 无法连接到后端服务: {snapshot['error']}")
        print("\n💡 提示:")
        print("  - 确保后端服务正在运行")
        print("  - 检查 API URL 是否正确")
        print("  - 如果后端未运行，可以直接重启（Asset Watchdog 会在启动时自动补齐资产）")
        sys.exit(1)
    
    current = snapshot.get("current")
    queue = snapshot.get("queue", [])
    length = snapshot.get("length", 0)
    
    print(f"📊 队列状态:")
    print(f"  总任务数: {length}")
    
    if current:
        print(f"\n🔄 正在渲染:")
        print(f"  Episode ID: {current.get('episode_id')}")
        print(f"  Channel ID: {current.get('channel_id')}")
        print(f"  入队时间: {current.get('enqueued_at', 'N/A')}")
    else:
        print(f"\n✅ 当前没有正在渲染的任务")
    
    if queue:
        print(f"\n📋 等待队列 ({len(queue)} 个):")
        for i, job in enumerate(queue, 1):
            print(f"  #{i}: {job.get('episode_id')} ({job.get('channel_id')})")
    else:
        print(f"\n✅ 队列为空")
    
    print("\n" + "=" * 70)
    print("💡 重启建议:")
    
    if current:
        print("  ⚠️  当前有任务正在渲染")
        print("  ✅ 可以重启（系统会通过恢复扫描重新入队）")
        print("  📝 重启后，当前渲染会被中断，但会在恢复扫描时重新入队")
        print("  ⏱️  根据 Step 10 的崩溃安全设计，系统会自动恢复")
    elif queue:
        print("  ✅ 队列中有等待任务，但没有正在渲染的任务")
        print("  ✅ 可以安全重启（任务会在恢复扫描时重新入队）")
    else:
        print("  ✅ 队列为空，可以安全重启")
    
    print("\n🎯 重启后的预期行为:")
    print("  1. ✅ Asset Watchdog 会启动，每 5 分钟检查一次资产")
    print("  2. ✅ Asset Watchdog 会检测到缺失的 description 和 SRT")
    print("  3. ✅ Asset Watchdog 会自动补齐缺失的资产（如果 auto_regenerate=true）")
    print("  4. ✅ RenderQueue 会进行恢复扫描，重新入队需要渲染的任务")
    print("  5. ✅ UploadQueue 和 VerifyWorker 也会自动启动")
    print("  6. ✅ 所有队列 worker 会进行恢复扫描")
    
    print("\n📝 测试步骤:")
    print("  1. 重启后端服务")
    print("  2. 观察日志，查看 Asset Watchdog 是否启动")
    print("  3. 等待最多 5 分钟（或手动触发检查），查看是否自动补齐资产")
    print("  4. 检查缺失的 description 和 SRT 文件是否已重新生成")
    print("  5. 验证新生成的文件是否使用了修复后的代码（时间格式正确、tracklist 排序正确）")
    
    print("\n🔍 验证命令:")
    print("  # 查看 Asset Watchdog 状态")
    print(f"  curl {args.api_url}/api/t2r/asset-watchdog/status")
    print("\n  # 查看渲染队列状态")
    print(f"  curl {args.api_url}/api/t2r/render-queue")


if __name__ == "__main__":
    main()

