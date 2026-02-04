#!/usr/bin/env python3
# coding: utf-8
"""
顺序上传指定日期范围的节目（等待资产齐备再上传）

用法:
  UPLOAD_SCHEDULE_TZ=America/New_York UPLOAD_SCHEDULE_HOUR=9 \\
    python3 scripts/upload_when_ready.py --start-date 20260402 --end-date 20260430 --channel kat
"""
from __future__ import annotations

import argparse
import json
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcpos.models import EpisodeSpec, AssetPaths
from mcpos.adapters.filesystem import build_asset_paths, detect_episode_state_from_filesystem
from mcpos.adapters.uploader import upload_episode_video
from mcpos.config import get_config
from mcpos.core.logging import log_info, log_error


def _date_range(start: datetime, end: datetime) -> list[str]:
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return dates


def _resolve_episode_paths(channel_id: str, date_str: str) -> tuple[EpisodeSpec, AssetPaths]:
    """
    解析期数输出目录（支持 output/ 和 output/Archived，支持 date-only 目录）
    """
    config = get_config()
    output_root = config.channels_root / channel_id / "output"
    candidates = [
        output_root / f"{channel_id}_{date_str}",
        output_root / date_str,
        output_root / "Archived" / f"{channel_id}_{date_str}",
        output_root / "Archived" / date_str,
    ]

    def _looks_like_episode_dir(path: Path) -> bool:
        if not path.exists():
            return False
        # 只要有核心文件之一，就认为是有效候选目录
        return any(
            (path / name).exists()
            for name in [
                "playlist.csv",
                "recipe.json",
                f"{path.name}_youtube.mp4",
                f"{path.name}_render_complete.flag",
            ]
        )

    episode_dir = None
    for d in candidates:
        if _looks_like_episode_dir(d):
            episode_dir = d
            break

    if episode_dir is None:
        episode_id = f"{channel_id}_{date_str}"
        spec = EpisodeSpec(channel_id=channel_id, date=date_str, episode_id=episode_id)
        paths = build_asset_paths(spec, config)
        return spec, paths

    episode_id = episode_dir.name
    spec = EpisodeSpec(channel_id=channel_id, date=date_str, episode_id=episode_id)
    paths = AssetPaths(
        episode_output_dir=episode_dir,
        playlist_csv=episode_dir / "playlist.csv",
        recipe_json=episode_dir / "recipe.json",
        final_mix_mp3=episode_dir / f"{episode_id}_final_mix.mp3",
        timeline_csv=episode_dir / f"{episode_id}_final_mix_timeline.csv",
        cover_png=episode_dir / f"{episode_id}_cover.png",
        youtube_title_txt=episode_dir / f"{episode_id}_youtube_title.txt",
        youtube_description_txt=episode_dir / f"{episode_id}_youtube_description.txt",
        youtube_tags_txt=episode_dir / f"{episode_id}_youtube_tags.txt",
        youtube_srt=episode_dir / f"{episode_id}_youtube.srt",
        youtube_mp4=episode_dir / f"{episode_id}_youtube.mp4",
        render_complete_flag=episode_dir / f"{episode_id}_render_complete.flag",
        upload_complete_flag=episode_dir / f"{episode_id}_upload_complete.flag",
        verify_complete_flag=episode_dir / f"{episode_id}_verify_complete.flag",
        tmp_dir=episode_dir / "tmp",
    )
    return spec, paths


def _check_ready(spec: EpisodeSpec, paths: AssetPaths) -> tuple[bool, list[str]]:
    state = detect_episode_state_from_filesystem(spec, paths)

    required_files = [
        paths.playlist_csv,
        paths.recipe_json,
        paths.youtube_title_txt,
        paths.youtube_description_txt,
        paths.youtube_tags_txt,
        paths.cover_png,
        paths.final_mix_mp3,
        paths.timeline_csv,
        paths.youtube_srt,
        paths.youtube_mp4,
        paths.render_complete_flag,
    ]

    missing = []
    for path in required_files:
        if not path.exists():
            missing.append(path.name)
        elif path.is_file() and path.stat().st_size == 0:
            missing.append(f"{path.name}(0b)")

    # Ensure all core stages are complete
    all_core_complete = state.is_core_complete()
    if not all_core_complete:
        missing.append("stage_incomplete")

    return len(missing) == 0, missing


def _is_already_uploaded(paths: AssetPaths, episode_id: str) -> bool:
    upload_json = paths.episode_output_dir / f"{episode_id}_youtube_upload.json"
    return paths.upload_complete_flag.exists() or upload_json.exists()


def _is_quota_error(error_msg: str | None) -> bool:
    if not error_msg:
        return False
    lowered = error_msg.lower()
    keywords = [
        "quota",
        "quotaexceeded",
        "dailylimit",
        "ratelimit",
        "daily limit",
        "rate limit",
        "403",
    ]
    return any(k in lowered for k in keywords)


def _update_channel_schedule(channel_id: str, episode_id: str, video_id: str) -> None:
    schedule_path = REPO_ROOT / "channels" / channel_id / "schedule_master.json"
    if not schedule_path.exists():
        return
    try:
        data = schedule_path.read_text(encoding="utf-8")
        payload = json.loads(data)
    except Exception:
        return

    updated = False
    for ep in payload.get("episodes", []):
        if ep.get("episode_id") == episode_id:
            ep["youtube_video_id"] = video_id
            ep["status"] = "uploaded"
            updated = True
            break

    if updated:
        payload["updated_at"] = datetime.now().isoformat()
        schedule_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def _upload_episode(spec: EpisodeSpec, paths: AssetPaths) -> dict:
    config = get_config()
    result = await upload_episode_video(spec, paths, config)

    if result.state == "uploaded":
        return {
            "status": "success",
            "episode_id": spec.episode_id,
            "video_id": result.video_id,
            "video_url": f"https://www.youtube.com/watch?v={result.video_id}" if result.video_id else None,
        }

    error_msg = result.error or "Upload failed"
    return {
        "status": "failed",
        "episode_id": spec.episode_id,
        "error": error_msg,
    }


async def run_upload_range(
    *,
    channel_id: str,
    start_date: datetime,
    end_date: datetime,
    poll_interval: int = 300,
    continue_on_failure: bool = False,
    wait_for_ready: bool = True,
    upload_interval: int = 5,
) -> int:
    dates = _date_range(start_date, end_date)
    print("=" * 70)
    print("📤 顺序上传" + ("（等待资产齐备）" if wait_for_ready else "（不等待资产）"))
    print("=" * 70)
    print(f"频道: {channel_id}")
    print(f"日期范围: {dates[0]} -> {dates[-1]}")
    if wait_for_ready:
        print(f"等待间隔: {poll_interval}s")
    print()

    results: list[dict] = []
    quota_exhausted = False

    for idx, date_str in enumerate(dates, 1):
        spec, paths = _resolve_episode_paths(channel_id, date_str)
        episode_id = spec.episode_id

        if _is_already_uploaded(paths, episode_id):
            print(f"⏭️  已上传，跳过: {episode_id}")
            results.append({
                "status": "skipped",
                "episode_id": episode_id,
                "date": date_str,
                "error": "already_uploaded",
            })
            continue

        print("=" * 70)
        print(f"[{idx}/{len(dates)}] 处理: {episode_id}")
        print("=" * 70)

        if wait_for_ready:
            while True:
                ready, missing = _check_ready(spec, paths)
                if ready:
                    break
                log_info(f"[upload] {episode_id} not ready, missing: {missing}")
                await asyncio.sleep(poll_interval)
        else:
            ready, missing = _check_ready(spec, paths)
            if not ready:
                msg = f"not ready: {missing}"
                print(f"⏭️  未就绪，跳过: {episode_id} -> {missing}")
                results.append({
                    "status": "skipped",
                    "episode_id": episode_id,
                    "date": date_str,
                    "error": msg,
                })
                if not continue_on_failure:
                    return 1
                continue

        log_info(f"[upload] {episode_id} ready. Start upload.")
        result = await _upload_episode(spec, paths)
        result["date"] = date_str
        results.append(result)

        if result["status"] == "success":
            print(f"✅ 上传成功: {episode_id} -> {result.get('video_id')}")
            if result.get("video_id"):
                _update_channel_schedule(channel_id, episode_id, result["video_id"])
        else:
            print(f"❌ 上传失败: {episode_id} -> {result.get('error')}")
            log_error(f"[upload] Upload failed: {episode_id} -> {result.get('error')}")
            if _is_quota_error(result.get("error")):
                print("⚠️  检测到配额错误，停止上传")
                quota_exhausted = True
                break
            if not continue_on_failure:
                return 1

        # 避免触发 API 限流
        if idx < len(dates):
            await asyncio.sleep(upload_interval)

    # Summary
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")

    print()
    print("=" * 70)
    print("📊 上传结果总结")
    print("=" * 70)
    print(f"总计: {len(results)} 期")
    print(f"成功: {success_count} 期")
    print(f"失败: {failed_count} 期")
    print(f"跳过: {skipped_count} 期")
    if quota_exhausted:
        print("⚠️  因配额用尽停止上传")

    if failed_count > 0 and not quota_exhausted:
        return 1
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="顺序上传指定日期范围的节目（等待资产齐备再上传）"
    )
    parser.add_argument("--start-date", required=True, help="开始日期 (YYYYMMDD)")
    parser.add_argument("--end-date", required=True, help="结束日期 (YYYYMMDD)")
    parser.add_argument("--channel", default="kat", help="频道ID (默认: kat)")
    parser.add_argument("--poll-interval", type=int, default=300, help="等待间隔秒数 (默认: 300)")
    parser.add_argument("--continue-on-failure", action="store_true", help="失败后继续后续日期")
    args = parser.parse_args()

    try:
        start_date = datetime.strptime(args.start_date, "%Y%m%d")
        end_date = datetime.strptime(args.end_date, "%Y%m%d")
    except ValueError:
        print("❌ 日期格式错误，请使用 YYYYMMDD")
        return 1
    return await run_upload_range(
        channel_id=args.channel,
        start_date=start_date,
        end_date=end_date,
        poll_interval=args.poll_interval,
        continue_on_failure=args.continue_on_failure,
        wait_for_ready=True,
        upload_interval=5,
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
