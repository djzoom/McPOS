#!/usr/bin/env python3
"""
WebSocket 客户端测试脚本

用于测试 WebSocket 连接、心跳和消息接收
"""
import asyncio
import json
import sys
from datetime import datetime

try:
    import websockets
except ImportError:
    print("❌ 需要安装 websockets 库")
    print("   运行: pip install websockets")
    sys.exit(1)


async def test_websocket_status():
    """测试 /ws/status 端点"""
    uri = "ws://localhost:8000/ws/status"
    
    print(f"🔌 连接到 {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ 连接成功!")
            print("")
            print("等待消息（10 秒后自动断开）...")
            print("")
            
            # 监听消息
            try:
                # 设置超时
                messages_received = 0
                
                while messages_received < 3:  # 接收 3 条消息后退出
                    try:
                        # 等待消息，最多 12 秒
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=12.0
                        )
                        
                        # 处理心跳消息（可能是纯字符串 "ping"）
                        if message == '"ping"' or message == 'ping':
                            print(f"💓 收到心跳 ping")
                            print(f"   时间: {datetime.now().strftime('%H:%M:%S')}")
                            print("")
                            continue
                        
                        # 尝试解析 JSON
                        try:
                            data = json.loads(message)
                        except json.JSONDecodeError:
                            # 如果不是 JSON，直接显示原始消息
                            print(f"📨 收到消息 #{messages_received + 1}:")
                            print(f"   原始内容: {message}")
                            print(f"   时间: {datetime.now().strftime('%H:%M:%S')}")
                            print("")
                            continue
                        
                        messages_received += 1
                        
                        print(f"📨 收到消息 #{messages_received}:")
                        print(f"   类型: {data.get('type', 'unknown')}")
                        
                        if data.get('type') == 'status_update':
                            status_data = data.get('data', {})
                            print(f"   队列状态: {status_data.get('queue_status', {})}")
                            print(f"   成功率: {status_data.get('success_rate', 0)}%")
                            print(f"   最后事件: {status_data.get('last_event', {}).get('message', 'N/A')}")
                        
                        print(f"   时间: {datetime.now().strftime('%H:%M:%S')}")
                        print("")
                        
                    except asyncio.TimeoutError:
                        print("⏱️  等待消息超时（可能心跳还在发送）")
                        break
                    
            except KeyboardInterrupt:
                print("\n👋 用户中断")
            
    except ConnectionRefusedError:
        print("❌ 连接被拒绝，请确保后端服务正在运行")
        print("   运行: cd kat_rec_web/backend && export USE_MOCK_MODE=true && uvicorn main:app --reload --port 8000")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 连接错误: {e}")
        sys.exit(1)
    
    print("✅ 测试完成")


async def test_websocket_events():
    """测试 /ws/events 端点"""
    uri = "ws://localhost:8000/ws/events"
    
    print(f"🔌 连接到 {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ 连接成功!")
            print("")
            print("等待事件（5 个事件后自动断开）...")
            print("")
            
            events_received = 0
            
            while events_received < 5:
                try:
                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=30.0
                    )
                    
                    # 跳过心跳消息
                    if message == '"ping"' or message == 'ping':
                        continue
                    
                    # 尝试解析 JSON
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        print(f"⚠️  收到非 JSON 消息: {message}")
                        continue
                    
                    events_received += 1
                    
                    print(f"📨 事件 #{events_received}:")
                    if data.get('type') == 'event':
                        event_data = data.get('data', {})
                        level = event_data.get('level', 'UNKNOWN')
                        message_text = event_data.get('message', '')
                        timestamp = event_data.get('timestamp', '')
                        print(f"   级别: {level}")
                        print(f"   消息: {message_text}")
                        print(f"   时间: {timestamp}")
                    print("")
                    
                except asyncio.TimeoutError:
                    print("⏱️  等待事件超时")
                    break
                    
    except ConnectionRefusedError:
        print("❌ 连接被拒绝")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 连接错误: {e}")
        sys.exit(1)
    
    print("✅ 测试完成")


async def test_heartbeat():
    """测试心跳机制"""
    uri = "ws://localhost:8000/ws/status"
    
    print(f"🔌 测试心跳机制...")
    print("   连接后将等待 10 秒，观察 ping 消息")
    print("")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ 连接成功!")
            print("   等待服务器 ping（应该每 5 秒一次）...")
            print("")
            
            ping_count = 0
            start_time = asyncio.get_event_loop().time()
            
            try:
                while (asyncio.get_event_loop().time() - start_time) < 12:
                    try:
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=6.0
                        )
                        
                        # 检查是否是 ping（可能是字符串 "ping" 或 JSON '"ping"'）
                        if message == '"ping"' or message == 'ping' or '"ping"' in str(message):
                            ping_count += 1
                            elapsed = asyncio.get_event_loop().time() - start_time
                            print(f"   ✅ 收到 ping #{ping_count} (耗时 {elapsed:.1f}s)")
                        
                    except asyncio.TimeoutError:
                        print(f"   ⚠️  6 秒内未收到消息（已收到 {ping_count} 个 ping）")
                        break
                        
            except KeyboardInterrupt:
                print("\n👋 用户中断")
            
            print("")
            if ping_count >= 2:
                print(f"✅ 心跳正常！10 秒内收到 {ping_count} 个 ping")
            elif ping_count == 1:
                print(f"⚠️  心跳可能较慢，10 秒内收到 {ping_count} 个 ping")
            else:
                print(f"❌ 未收到心跳消息")
                
    except ConnectionRefusedError:
        print("❌ 连接被拒绝")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 连接错误: {e}")
        sys.exit(1)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='WebSocket 测试客户端')
    parser.add_argument(
        '--test',
        choices=['status', 'events', 'heartbeat', 'all'],
        default='all',
        help='选择测试类型'
    )
    
    args = parser.parse_args()
    
    if args.test == 'status' or args.test == 'all':
        print("=" * 60)
        print("测试 1: /ws/status 端点")
        print("=" * 60)
        asyncio.run(test_websocket_status())
        print("")
    
    if args.test == 'events' or args.test == 'all':
        print("=" * 60)
        print("测试 2: /ws/events 端点")
        print("=" * 60)
        asyncio.run(test_websocket_events())
        print("")
    
    if args.test == 'heartbeat' or args.test == 'all':
        print("=" * 60)
        print("测试 3: 心跳机制")
        print("=" * 60)
        asyncio.run(test_heartbeat())
        print("")
    
    print("=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()

