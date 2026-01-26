#!/usr/bin/env python3
# coding: utf-8
"""
自动化流程诊断工具

检查为什么episode只停留在playlist阶段，并提供修复建议。

用法：
    python scripts/diagnose_automation.py --channel kat_lofi --episode 20251111
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
BACKEND_ROOT = REPO_ROOT / "kat_rec_web" / "backend"

for path in [SRC_ROOT, BACKEND_ROOT, REPO_ROOT]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def check_backend_running() -> tuple[bool, str]:
    """检查后端服务是否正在运行"""
    import subprocess
    try:
        result = subprocess.run(
            ["lsof", "-ti:8000"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, f"后端服务正在运行 (PID: {result.stdout.strip()})"
        return False, "后端服务未运行（端口8000未被占用）"
    except Exception as e:
        return False, f"无法检查后端状态: {e}"


def check_episode_files(channel_id: str, episode_id: str) -> Dict:
    """检查episode文件状态"""
    from kat_rec_web.backend.t2r.services.schedule_service import get_output_dir
    
    output_dir = get_output_dir(channel_id)
    episode_dir = output_dir / episode_id
    
    files_status = {
        "episode_dir_exists": episode_dir.exists(),
        "playlist_csv": (episode_dir / "playlist.csv").exists(),
        "playlist_metadata": (episode_dir / "playlist_metadata.json").exists(),
        "manifest": (episode_dir / f"{episode_id}_manifest.json").exists(),
        "full_mix": (episode_dir / f"{episode_id}_full_mix.mp3").exists(),
        "cover": (episode_dir / f"{episode_id}_cover.png").exists(),
        "youtube_video": list(episode_dir.glob(f"{episode_id}_youtube.mp4")),
        "youtube_title": (episode_dir / f"{episode_id}_youtube_title.txt").exists(),
        "youtube_description": (episode_dir / f"{episode_id}_youtube_description.txt").exists(),
    }
    
    return files_status


def check_manifest_status(channel_id: str, episode_id: str) -> Optional[Dict]:
    """检查manifest状态"""
    from kat_rec_web.backend.t2r.services.schedule_service import get_output_dir
    
    output_dir = get_output_dir(channel_id)
    episode_dir = output_dir / episode_id
    manifest_path = episode_dir / f"{episode_id}_manifest.json"
    
    if not manifest_path.exists():
        return None
    
    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": f"无法读取manifest: {e}"}


def check_schedule_status(channel_id: str, episode_id: str) -> Optional[Dict]:
    """检查schedule_master中的episode状态"""
    from kat_rec_web.backend.t2r.services.schedule_service import load_schedule_master
    
    schedule = load_schedule_master(channel_id)
    if not schedule:
        return None
    
    episodes = schedule.get("episodes", [])
    episode = next((ep for ep in episodes if ep.get("episode_id") == episode_id), None)
    
    return episode


def diagnose_episode(channel_id: str, episode_id: str) -> None:
    """诊断episode状态"""
    print(f"\n{'='*60}")
    print(f"诊断 Episode: {episode_id} (Channel: {channel_id})")
    print(f"{'='*60}\n")
    
    # 1. 检查后端服务
    print("1. 检查后端服务状态...")
    backend_running, backend_msg = check_backend_running()
    print(f"   {'✅' if backend_running else '❌'} {backend_msg}\n")
    
    # 2. 检查文件状态
    print("2. 检查文件状态...")
    files_status = check_episode_files(channel_id, episode_id)
    
    required_files = ["playlist_csv", "playlist_metadata", "manifest"]
    optional_files = ["full_mix", "cover", "youtube_video", "youtube_title", "youtube_description"]
    
    print("   必需文件:")
    for file_key in required_files:
        exists = files_status.get(file_key, False)
        if isinstance(exists, list):
            exists = len(exists) > 0
        print(f"   {'✅' if exists else '❌'} {file_key}: {exists}")
    
    print("\n   可选文件（后续阶段生成）:")
    for file_key in optional_files:
        exists = files_status.get(file_key, False)
        if isinstance(exists, list):
            exists = len(exists) > 0
        print(f"   {'✅' if exists else '❌'} {file_key}: {exists}")
    
    # 3. 检查manifest状态
    print("\n3. 检查 Manifest 状态...")
    manifest = check_manifest_status(channel_id, episode_id)
    if manifest:
        status = manifest.get("status", "unknown")
        print(f"   状态: {status}")
        
        # 检查阶段
        if "dag" in manifest:
            dag = manifest["dag"]
            print(f"   DAG 任务数: {len(dag.get('tasks', []))}")
        
        if "runs" in manifest:
            runs = manifest["runs"]
            print(f"   已完成任务: {len([r for r in runs if r.get('status') == 'ok'])}")
            print(f"   失败任务: {len([r for r in runs if r.get('status') == 'error'])}")
    else:
        print("   ❌ Manifest 文件不存在")
    
    # 4. 检查schedule状态
    print("\n4. 检查 Schedule 状态...")
    episode_data = check_schedule_status(channel_id, episode_id)
    if episode_data:
        print(f"   Episode ID: {episode_data.get('episode_id')}")
        print(f"   状态: {episode_data.get('status', 'unknown')}")
        print(f"   标题: {episode_data.get('title', 'N/A')}")
    else:
        print("   ❌ Episode 不在 schedule_master 中")
    
    # 5. 诊断结果和建议
    print("\n" + "="*60)
    print("诊断结果和建议:")
    print("="*60 + "\n")
    
    issues = []
    suggestions = []
    
    if not backend_running:
        issues.append("后端服务未运行")
        suggestions.append("启动后端服务: cd kat_rec_web/backend && uvicorn main:app --host 0.0.0.0 --port 8000")
        suggestions.append("或使用: make start-backend")
    
    if not files_status.get("playlist_csv"):
        issues.append("playlist.csv 不存在")
        suggestions.append("运行: python scripts/local_picker/create_mixtape.py --episode-id {episode_id}")
    
    if files_status.get("playlist_csv") and not files_status.get("full_mix"):
        issues.append("playlist已生成，但后续阶段未执行")
        suggestions.append("方案1: 确保后端服务运行，然后调用 POST /api/t2r/schedule/create-episode?start_generation=true")
        suggestions.append("方案2: 手动运行: python scripts/local_picker/run_episode_flow.py --channel {channel_id} {episode_id}")
        suggestions.append("方案3: 使用CLI: python scripts/local_picker/create_mixtape.py --episode-id {episode_id} (不要加 --no-remix)")
    
    if issues:
        print("发现的问题:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        
        print("\n建议的修复步骤:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"   {i}. {suggestion}")
    else:
        print("✅ 未发现明显问题")
    
    print("\n" + "="*60)
    print("快速修复命令:")
    print("="*60)
    print(f"\n# 方案1: 使用 EpisodeFlow CLI（推荐）")
    print(f"python scripts/local_picker/run_episode_flow.py --channel {channel_id} {episode_id}\n")
    
    print(f"# 方案2: 确保后端运行后，通过API触发")
    print(f"curl -X POST 'http://localhost:8000/api/t2r/schedule/create-episode?channel_id={channel_id}&date={episode_id}&start_generation=true'\n")
    
    print(f"# 方案3: 使用 create_mixtape.py（全流程）")
    print(f"python scripts/local_picker/create_mixtape.py --episode-id {episode_id} --channel {channel_id}\n")


def main():
    parser = argparse.ArgumentParser(description="诊断自动化流程问题")
    parser.add_argument("--channel", "-c", required=True, help="Channel ID")
    parser.add_argument("--episode", "-e", required=True, help="Episode ID (YYYYMMDD)")
    
    args = parser.parse_args()
    
    try:
        diagnose_episode(args.channel, args.episode)
    except Exception as e:
        print(f"\n❌ 诊断过程出错: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

