#!/usr/bin/env python3
# coding: utf-8
"""Sleep in Grace — 批量上传器。

三性质硬要求:
  幂等   — upload_complete.flag 或 video_id 存在即跳过,重跑安全;
  门禁   — 成片/时长/SRT/封面/元数据长度任一不合格即拦该期,不中断整批;
  回执双写 — 成片旁 sidecar JSON + 主表回填(写前自动 .bak_<yyyymmdd>)。

工作流:sync-check → --dry-run(验证一切,零上传)→ 真跑(private+publishAt
排播、串行、逐期落回执)→ sg_verify_uploads.py 验证 → git 提交主表。

    python scripts/sg/sg_batch_upload.py --dry-run --limit 1
    python scripts/sg/sg_batch_upload.py --limit 1
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quota                                    # noqa: E402
import upload_meta as meta                      # noqa: E402
from sg_upload import (CAPTION_TRACKS, build_service, set_thumbnail, upload_caption,   # noqa: E402
                       upload_link_lock, upload_media)

ROOT = Path(__file__).resolve().parents[2]
MASTER_PATH = ROOT / "config" / "sg_schedule_master.json"
THUMBS_DIR = Path.home() / "Studio/Workspace/temp/sg/thumbs"
DURATION_TOLERANCE = 90.0                        # 秒


from sg_media import probe_duration  # noqa: E402,F401


def make_thumb(cover: Path, ep_id: str) -> Path | None:
    """封面源图 → ≤2MB JPG 缩略图(YouTube 硬上限)。"""
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    thumb = THUMBS_DIR / f"{ep_id}_cover_thumb.jpg"
    if thumb.exists() and thumb.stat().st_mtime >= cover.stat().st_mtime:
        return thumb
    for q in (4, 7, 12):
        r = subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error",
                            "-i", str(cover), "-vf", "scale=1280:720",
                            "-q:v", str(q), str(thumb)])
        if r.returncode == 0 and thumb.stat().st_size <= 2 * 1024 * 1024:
            return thumb
    return None


def preflight(ep: dict) -> list[str]:
    """门禁:返回拦截原因列表(空 = 放行)。"""
    gate: list[str] = []
    video = Path(ep["output_file"])
    if not video.exists():
        gate.append(f"成片缺失 {video.name}")
    else:
        dur = probe_duration(video)
        want = ep.get("minutes", 60) * 60
        if abs(dur - want) > DURATION_TOLERANCE:
            gate.append(f"成片时长 {dur:.0f}s ≠ {want:.0f}s(±{DURATION_TOLERANCE:.0f})")
    srt = Path(ep["srt_file"])
    if not srt.exists():
        gate.append(f"字幕缺失 {srt.name}(upload_meta.py --build-srt 可生成)")
    cover = Path(ep["cover_file"])
    if not cover.exists():
        gate.append(f"封面缺失 {cover.name}")
    elif make_thumb(cover, ep["episode_id"]) is None:
        gate.append("封面无法压到 ≤2MB")
    try:
        sdir = video.parent
        meta.build_body(ep["episode_number"], sdir, ep["publish_at"],
                        ep.get("minutes", 60))
    except (ValueError, FileNotFoundError, KeyError) as exc:
        gate.append(f"元数据不合格: {exc}")
    try:
        if ep.get("title") != meta.build_title(ep["episode_number"],
                                               ep.get("minutes", 60)):
            gate.append("主表 title 与真源不一致(先跑 upload_meta.py --sync-check)")
    except ValueError as exc:
        gate.append(f"标题不合格: {exc}")
    pub = ep.get("publish_at", "")
    if not pub or pub <= datetime.now(timezone.utc).isoformat():
        gate.append(f"publish_at 非未来时间: {pub}(教训:未来排播,绝不即时公开)")
    return gate


def save_master(master: dict) -> None:
    stamp = datetime.now().strftime("%Y%m%d")
    bak = MASTER_PATH.with_suffix(f".json.bak_{stamp}")
    if not bak.exists():
        bak.write_text(MASTER_PATH.read_text())
    MASTER_PATH.write_text(json.dumps(master, ensure_ascii=False, indent=2))


def cmd(a: argparse.Namespace) -> int:
    master = json.loads(MASTER_PATH.read_text())
    eps = master["episodes"]
    if a.limit:
        eps = eps[: a.limit]

    yt = None
    if not a.dry_run:
        yt = build_service()

    done = blocked = uploaded = 0
    for ep in eps:
        num, ep_id = ep["episode_number"], ep["episode_id"]
        video = Path(ep["output_file"])
        flag = video.parent / f"{ep_id}_upload_complete.flag"

        # 幂等门
        if flag.exists() or ep.get("video_id") or ep.get("status") in ("uploaded", "verified"):
            print(f"  ⏭  #{num} {ep_id} 已上传({ep.get('video_id')})— 跳过")
            done += 1
            continue

        # 门禁前置
        gate = preflight(ep)
        if gate:
            print(f"  ⛔ #{num} {ep_id} 门禁拦截·不上传 — {'; '.join(gate)}")
            blocked += 1
            continue

        # 配额预算
        if not quota.can_afford():
            print(f"  🛑 配额不足(余 {quota.remaining()}u < {quota.EPISODE_COST}u)"
                  f"——停批,明日再跑")
            break

        body = meta.build_body(num, video.parent, ep["publish_at"],
                               ep.get("minutes", 60))
        thumb = make_thumb(Path(ep["cover_file"]), ep_id)
        if a.dry_run:
            print(f"  ✅ #{num} {ep_id} DRY-RUN 全门通过 "
                  f"({video.stat().st_size / 1048576:.0f}MB, "
                  f"publishAt={ep['publish_at']}, 预算后余 "
                  f"{quota.remaining() - quota.EPISODE_COST}u)")
            uploaded += 1
            continue

        # 真跑:串行上传
        print(f"  ⬆️  #{num} {ep_id} 上传中…")
        vid = upload_media(yt, video, body)
        quota.record("videos.insert", ep_id)
        # 英文 + 简繁中文三条轨。中文轨此前从未上传过(语言硬编码 en),
        # 缺哪条就跳过哪条,不因为字幕不全而中断整期上传。
        base = Path(ep["srt_file"])
        for suffix, lang, label in CAPTION_TRACKS:
            track = base.with_suffix(f"{suffix}.srt") if suffix else base
            if not track.exists():
                print(f"      ⏭ 缺 {lang} 字幕,跳过")
                continue
            upload_caption(yt, vid, track, language=lang, name=label)
            quota.record("captions.insert", f"{ep_id} {lang}")
        set_thumbnail(yt, vid, thumb)
        quota.record("thumbnails.set", ep_id)

        # 回执双写:sidecar + 主表回填
        sidecar = video.parent / f"{ep_id}_youtube_upload.json"
        receipt = {
            "episode_id": ep_id, "channel_id": "sg", "video_id": vid,
            "video_url": f"https://youtu.be/{vid}",
            "publish_at": ep["publish_at"], "status": "uploaded",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        sidecar.write_text(json.dumps(receipt, indent=2))
        ep["video_id"] = vid
        ep["status"] = "uploaded"
        ep["receipt"] = str(sidecar)
        save_master(master)
        print(f"  ✅ #{num} → https://youtu.be/{vid}(private, "
              f"publishAt={ep['publish_at']})")
        uploaded += 1

    print(f"\n汇总: 上传 {uploaded} · 跳过 {done} · 门禁拦截 {blocked} · "
          f"配额余 {quota.remaining()}u")
    if not a.dry_run and uploaded:
        print("下一步: python scripts/sg/sg_verify_uploads.py && git add config/ && git commit")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="SG 批量上传器")
    ap.add_argument("--dry-run", action="store_true", help="验证一切,零上传")
    ap.add_argument("--limit", type=int, help="只处理前 N 期")
    a = ap.parse_args()
    if a.dry_run:
        return cmd(a)
    with upload_link_lock(f"sg_batch_upload pid={Path('/proc/self').name if False else ''}"
                          f"{datetime.now():%H%M%S}"):
        return cmd(a)


if __name__ == "__main__":
    raise SystemExit(main())
