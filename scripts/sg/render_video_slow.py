#!/usr/bin/env python3
# coding: utf-8
"""Render SiG YouTube video: slow-motion loop from assets/video + audio mix.

Video source: ~/Studio/Library/sg/assets/video (53 short Christian night loops)
Default speed: 0.125x (8× slower) — near-static sacred motion for sleep.

Usage:
  python3 scripts/sg/render_video_slow.py \\
    --audio ~/Studio/Workspace/outputs/sg/sessions/sg_locke_v2_001/sg_locke_v2_001_final_mix.mp3 \\
    --speed 0.125

  # or wire whole session dir
  python3 scripts/sg/render_video_slow.py --session-dir .../sg_locke_v2_001 --speed 0.1
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

VIDEO_DIR = Path.home() / "Studio/Library/sg/assets/video"


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


from sg_media import probe_duration, probe_duration_or_die  # noqa: E402,F401


def pick_video(video_dir: Path, seed: int | None = None) -> Path:
    files = sorted(video_dir.glob("*.mp4"))
    if not files:
        raise FileNotFoundError(f"No mp4 in {video_dir}")
    if seed is not None:
        random.seed(seed)
    return random.choice(files)


def render(
    audio: Path,
    video: Path,
    out: Path,
    *,
    speed: float = 0.125,
    width: int = 1920,
    height: int = 1080,
    fps: int = 24,
    crf: int = 22,
    preset: str = "veryfast",
) -> Path:
    """Loop video, slow by setpts, scale/pad to WxH, mux with audio (-shortest)."""
    if speed <= 0 or speed > 1.0:
        raise ValueError("speed should be in (0, 1], e.g. 0.125 for slowest practical")
    # setpts multiplier: 0.125x playback → timestamps stretch by 1/0.125 = 8
    pts = 1.0 / speed
    audio_dur = probe_duration(audio)
    if audio_dur <= 0:
        raise RuntimeError(f"bad audio duration: {audio}")

    out.parent.mkdir(parents=True, exist_ok=True)
    # stream_loop on input; setpts slows motion; fps caps output rate
    vf = (
        f"setpts={pts:.6f}*PTS,"
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"fps={fps}"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-stream_loop", "-1",
        "-i", str(video),
        "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf", vf,
        "-t", f"{audio_dur:.3f}",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(out),
    ]
    print(f"video: {video.name}")
    print(f"speed: {speed}x  (setpts={pts:.2f})  duration={audio_dur/60:.1f} min")
    print(f"out: {out}")
    r = run(cmd)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-1200:] if r.stderr else "ffmpeg failed")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Slow-loop Christian night video + audio")
    ap.add_argument("--audio", type=Path, default=None)
    ap.add_argument("--session-dir", type=Path, default=None, help="session folder containing *_final_mix.mp3")
    ap.add_argument("--video-dir", type=Path, default=VIDEO_DIR)
    ap.add_argument("--video", type=Path, default=None, help="specific loop file")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--speed", type=float, default=0.125, help="playback speed 0–1; 0.125 = 8× slower (default slowest)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--crf", type=int, default=22)
    ap.add_argument("--preset", default="veryfast")
    args = ap.parse_args()

    if args.session_dir:
        mixes = list(args.session_dir.glob("*_final_mix.mp3"))
        if not mixes:
            print(f"No *_final_mix.mp3 in {args.session_dir}", file=sys.stderr)
            return 1
        audio = mixes[0]
        out = args.out or (args.session_dir / f"{args.session_dir.name}_youtube.mp4")
    elif args.audio:
        audio = args.audio
        out = args.out or audio.with_name(audio.stem.replace("_final_mix", "") + "_youtube.mp4")
    else:
        print("Need --audio or --session-dir", file=sys.stderr)
        return 1

    video = args.video or pick_video(args.video_dir, seed=args.seed)
    if not video.exists():
        print(f"Missing video: {video}", file=sys.stderr)
        return 1

    try:
        path = render(
            audio, video, out,
            speed=args.speed,
            width=args.width,
            height=args.height,
            crf=args.crf,
            preset=args.preset,
        )
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    meta = {
        "audio": str(audio),
        "video": str(video),
        "out": str(path),
        "speed": args.speed,
        "setpts": 1.0 / args.speed,
        "duration_sec": probe_duration(path),
        "resolution": f"{args.width}x{args.height}",
    }
    meta_path = path.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("DONE", path)
    print("meta", meta_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
