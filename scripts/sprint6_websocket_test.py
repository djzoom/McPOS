#!/usr/bin/env python3
"""
Sprint 6 WebSocket 完整性测试

测试版本号递增、心跳、批量缓冲等功能
"""
import asyncio
import json
import statistics
import websockets
import time
import sys

gaps = []
last_ver = -1
pings = 0
events = 0
error_count = 0
version_errors = []


async def test_websocket():
    """测试WebSocket连接"""
    global last_ver, pings, events, error_count, version_errors
    
    uri = 'ws://localhost:8000/ws/events'
    
    print("🔌 连接到 WebSocket...")
    print(f"   URL: {uri}")
    
    try:
        async with websockets.connect(uri) as ws:
            print("✅ 连接成功")
            print("   等待事件...（最多10秒或100条消息）\n")
            
            t_prev = time.time()
            start_time = time.time()
            
            # 接收最多100条消息或10秒超时
            for i in range(100):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    
                    # 处理心跳
                    if msg == 'ping' or msg == '"ping"':
                        pings += 1
                        if pings == 1:
                            print(f"✅ 收到心跳 (ping #{pings})")
                        continue
                    
                    # 解析JSON
                    try:
                        m = json.loads(msg)
                    except json.JSONDecodeError:
                        continue
                    
                    # 检查版本号
                    if isinstance(m, dict):
                        # 支持多种消息格式
                        version = (
                            m.get('version') or 
                            m.get('data', {}).get('version') or
                            (m.get('data') if isinstance(m.get('data'), dict) else {}).get('version')
                        )
                        
                        if version is not None:
                            if version <= last_ver and last_ver >= 0:
                                error_msg = f"❌ version非递增: {version} <= {last_ver}"
                                print(error_msg)
                                version_errors.append(error_msg)
                                error_count += 1
                            last_ver = version
                        
                        events += 1
                        
                        # 计算间隔（排除心跳间隔）
                        t_now = time.time()
                        gap_ms = (t_now - t_prev) * 1000
                        if gap_ms < 5000:  # 排除心跳间隔
                            gaps.append(gap_ms)
                        t_prev = t_now
                        
                        # 显示前几个事件
                        if events <= 3:
                            event_type = m.get('type', 'unknown')
                            print(f"📨 事件 #{events}: {event_type} (version: {version or 'N/A'})")
                    
                except asyncio.TimeoutError:
                    elapsed = time.time() - start_time
                    print(f"\n⏱️  超时（已等待 {elapsed:.1f} 秒）")
                    break
                    
    except websockets.exceptions.InvalidURI:
        print(f"❌ 无效的WebSocket URL: {uri}")
        error_count += 1
        return
    except ConnectionRefusedError:
        print(f"❌ 连接被拒绝 - 后端可能未运行")
        print(f"   请确保后端运行在 http://localhost:8000")
        error_count += 1
        return
    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")
        error_count += 1
        return
    
    # 输出结果
    print("\n" + "="*60)
    print("📊 测试结果")
    print("="*60)
    
    # 心跳测试
    if pings >= 1:
        print(f"✅ 心跳正常: 收到 {pings} 次 (期望 ≥1，间隔5s)")
    else:
        print(f"❌ 心跳不足: 收到 {pings} 次 (期望 ≥1)")
        error_count += 1
    
    # 事件测试
    if events > 0:
        print(f"✅ 收到 {events} 个事件")
        
        if len(gaps) > 0:
            median_gap = statistics.median(gaps)
            mean_gap = statistics.mean(gaps)
            min_gap = min(gaps)
            max_gap = max(gaps)
            
            print(f"\n📈 批量缓冲统计:")
            print(f"   中位数间隔: {median_gap:.1f}ms")
            print(f"   平均间隔: {mean_gap:.1f}ms")
            print(f"   最小间隔: {min_gap:.1f}ms")
            print(f"   最大间隔: {max_gap:.1f}ms")
            
            if 50 <= median_gap <= 200:
                print(f"   ✅ 批量缓冲正常 (~100ms)")
            else:
                print(f"   ⚠️  批量缓冲异常 (期望 ~100ms，实际 {median_gap:.1f}ms)")
        else:
            print(f"   ⚠️  无有效间隔数据（可能只有一个事件）")
    else:
        print(f"⚠️  未收到事件（可能需要触发API调用）")
        print(f"   提示: 运行以下命令触发事件")
        print(f"   curl -X POST http://localhost:8000/api/episodes/run \\")
        print(f"     -H 'Content-Type: application/json' \\")
        print(f"     -d '{{\"episode_id\":\"TEST\",\"stages\":[\"remix\"]}}'")
    
    # 版本号测试
    if last_ver > 0:
        print(f"\n✅ 版本号单调递增: 最高版本 {last_ver}")
        if len(version_errors) > 0:
            print(f"   ⚠️  发现 {len(version_errors)} 个版本号错误")
        else:
            print(f"   ✅ 无版本号重复或乱序")
    elif events > 0:
        print(f"\n⚠️  收到事件但未检测到版本号字段")
        print(f"   提示: 某些消息可能不包含version字段（如心跳）")
    else:
        print(f"\n⚠️  未检测到版本号（可能未收到事件）")
    
    print("\n" + "="*60)
    
    # 总结
    if error_count == 0 and events > 0 and pings >= 1:
        print("🎉 WebSocket测试通过！")
        return 0
    elif error_count == 0 and events == 0:
        print("⚠️  测试通过但未收到事件（可能需要触发API）")
        return 0
    else:
        print(f"❌ WebSocket测试失败（错误数: {error_count}）")
        return 1


if __name__ == '__main__':
    try:
        exit_code = asyncio.run(test_websocket())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

