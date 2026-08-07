#!/usr/bin/env python3
# coding: utf-8
"""Render one SiG episode: single slow background loop + elegant ASS subtitles.

Subtitles are speech-aligned via:
  1) session plan cumulative times + atom sidecar text (if Whisper harvest done), else
  2) local whisper.cpp word timestamps on the session VO track.

Usage:
  python3 scripts/sg/render_session_video.py \\
    --session-dir ~/Studio/Workspace/outputs/sg/sessions/sg_locke_v2_001 \\
    --speed 0.125
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

VIDEO_DIR = Path.home() / "Studio/Library/sg/assets/video"
WHISPER_CLI = "whisper-cli"
MODEL_CANDIDATES = [
    Path("/Users/z/Projects/whisper.cpp/models/ggml-large-v3-turbo.bin"),
    Path.home() / "Projects/whisper.cpp/models/ggml-large-v3-turbo.bin",
]


@dataclass
class Cue:
    start: float
    end: float
    text: str


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def probe_duration(path: Path) -> float:
    r = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def pick_one_video(video_dir: Path, seed: int | None = None) -> Path:
    files = sorted(video_dir.glob("*.mp4"))
    if not files:
        raise FileNotFoundError(f"No videos in {video_dir}")
    if seed is not None:
        random.seed(seed)
    return random.choice(files)


def ass_time(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def wrap_text(text: str, width: int = 42) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= width:
        return text
    words = text.split(" ")
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        trial = (" ".join(cur + [w])).strip()
        if len(trial) <= width:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return "\\N".join(lines[:3])  # max 3 lines


def build_ass(cues: list[Cue], out_path: Path, *, play_res_x: int = 1920, play_res_y: int = 1080) -> Path:
    """Elegant sleep-prayer ASS: soft cream type, gentle fade, bottom-safe margin."""
    header = f"""[Script Info]
Title: Sleep in Grace
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: {play_res_x}
PlayResY: {play_res_y}
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
; Primary &H00BBGGRR — soft warm ivory
Style: Prayer,Georgia,52,&H00E8F0FF,&H000000FF,&H66101010,&H80000000,0,0,0,0,100,100,0.8,0,1,0,0,2,120,120,110,1
Style: Scripture,Georgia,50,&H00D0E8FF,&H000000FF,&H66101010,&H80000000,0,1,0,0,100,100,1.0,0,1,0,0,2,140,140,110,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    for c in cues:
        if not c.text or c.end <= c.start:
            continue
        # slight display padding
        start = max(0.0, c.start)
        end = max(start + 0.35, c.end + 0.12)
        style = "Scripture" if re.search(
            r"\b(psalm|matthew|john|isaiah|philippians|romans|lord said|jesus said)\b",
            c.text,
            re.I,
        ) else "Prayer"
        body = wrap_text(c.text)
        # fade in 250ms / out 350ms + soft blur-less shadow via \fad
        line = (
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,"
            f"{{\\fad(250,350)\\blur0.4}}{body}"
        )
        events.append(line)

    out_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out_path


def cues_from_session_plan(session_json: Path) -> list[Cue]:
    """Rebuild timeline from plan + atom sidecars (needs text on atoms)."""
    data = json.loads(session_json.read_text(encoding="utf-8"))
    plan = data.get("plan") or []
    t = 0.0
    cues: list[Cue] = []
    for item in plan:
        if item.get("type") == "silence":
            t += float(item.get("sec") or 0)
            continue
        if item.get("type") != "atom":
            continue
        dur = float(item.get("duration_sec") or 0)
        text = item.get("text")
        path = item.get("path")
        if not text and path:
            side = Path(path).with_suffix(".json")
            if side.exists():
                try:
                    text = json.loads(side.read_text(encoding="utf-8")).get("text")
                except Exception:
                    text = None
        # prefer recorded pad_after_sec (pad ≥ speech); fall back to duration then legacy 0.35
        pad = float(item.get("pad_after_sec") or 0)
        if pad <= 0:
            pad = max(dur, 0.35) if dur > 0 else 0.35
        if text and dur > 0:
            # use plan start_sec when present (already accounts for atempo + pads)
            if item.get("start_sec") is not None and item.get("end_sec") is not None:
                s = float(item["start_sec"])
                e = float(item["end_sec"])
                cues.append(Cue(start=s, end=e, text=str(text).strip()))
                t = e + pad
                continue
            cues.append(Cue(start=t, end=t + dur, text=str(text).strip()))
        t += dur + pad
    return cues


def cues_from_whisper(vo_path: Path, work: Path, model: Path) -> list[Cue]:
    work.mkdir(parents=True, exist_ok=True)
    wav = work / f"{vo_path.stem}_16k.wav"
    if not wav.exists() or wav.stat().st_mtime < vo_path.stat().st_mtime:
        r = run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(vo_path), "-ar", "16000", "-ac", "1", str(wav),
        ])
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-400:])
    out_base = work / f"{vo_path.stem}_w"
    js = Path(str(out_base) + ".json")
    if not js.exists() or js.stat().st_mtime < wav.stat().st_mtime:
        cmd = [
            WHISPER_CLI, "-m", str(model), "-l", "en",
            "-sow", "-ml", "1", "-oj", "-of", str(out_base), "-t", "6",
            str(wav),
        ]
        print("  whisper VO for subtitles…")
        r = run(cmd)
        if r.returncode != 0 and not js.exists():
            raise RuntimeError(r.stderr[-800:])
    data = json.loads(js.read_text(encoding="utf-8"))
    words = []
    for seg in data.get("transcription") or []:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        off = seg.get("offsets") or {}
        a = float(off.get("from", 0)) / 1000.0
        b = float(off.get("to", 0)) / 1000.0
        if b <= a:
            b = a + 0.1
        words.append((a, b, text))

    # group to phrases
    if not words:
        return []
    cues: list[Cue] = []
    buf = [words[0]]

    def flush():
        nonlocal buf
        if not buf:
            return
        text = re.sub(r"\s+", " ", " ".join(w[2] for w in buf)).strip()
        text = re.sub(r"\s+([,.!?;:])", r"\1", text)
        if text:
            cues.append(Cue(start=buf[0][0], end=buf[-1][1], text=text))
        buf = []

    for w in words[1:]:
        gap = w[0] - buf[-1][1]
        dur = w[1] - buf[0][0]
        last = buf[-1][2].rstrip()
        if gap >= 0.55 or (last and last[-1] in ".!?") or dur >= 8.0:
            flush()
            buf = [w]
        else:
            buf.append(w)
    flush()
    return cues


def resolve_model() -> Path:
    for p in MODEL_CANDIDATES:
        if p.exists() and p.stat().st_size > 50_000_000:
            return p
    raise FileNotFoundError("whisper model not found")


def render_video(
    *,
    audio: Path,
    video: Path,
    ass: Path,
    out: Path,
    speed: float = 0.125,
    width: int = 1920,
    height: int = 1080,
    fps: int = 24,
    crf: int = 22,
    preset: str = "veryfast",
) -> Path:
    pts = 1.0 / speed
    audio_dur = probe_duration(audio)
    # Escape ass path for ffmpeg filter (colons, etc.)
    ass_esc = str(ass).replace("\\", "/").replace(":", "\\:").replace("'", r"\'")
    vf = (
        f"setpts={pts:.6f}*PTS,"
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x0a0a12,"
        f"fps={fps},"
        f"ass='{ass_esc}'"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-stream_loop", "-1", "-i", str(video),
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
    print(f"  bg: {video.name}  speed={speed}x")
    print(f"  ass: {ass.name}  cues burned via libass")
    r = run(cmd)
    if r.returncode != 0:
        # fallback: subtitles filter
        vf2 = vf.replace(f"ass='{ass_esc}'", f"subtitles='{ass_esc}'")
        cmd[cmd.index("-vf") + 1] = vf2
        r = run(cmd)
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-1200:] if r.stderr else "ffmpeg failed")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session-dir", type=Path, required=True)
    ap.add_argument("--video-dir", type=Path, default=VIDEO_DIR)
    ap.add_argument("--video", type=Path, default=None, help="force one background file")
    ap.add_argument("--speed", type=float, default=0.125)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--subtitle-mode", choices=["auto", "plan", "whisper"], default="auto")
    ap.add_argument("--work", type=Path, default=Path("/tmp/sg_sub_work"))
    ap.add_argument("--preset", default="veryfast")
    ap.add_argument("--crf", type=int, default=22)
    args = ap.parse_args()

    sdir = args.session_dir
    mixes = list(sdir.glob("*_final_mix.mp3"))
    vos = list(sdir.glob("*_vo.mp3"))
    # prefer non-padded vo for cleaner speech-only whisper
    vo = None
    for p in vos:
        if "padded" not in p.name:
            vo = p
            break
    if not vo and vos:
        vo = vos[0]
    if not mixes:
        print("No final_mix in session", file=sys.stderr)
        return 1
    audio = mixes[0]
    session_json = next(iter(sdir.glob("*_session.json")), None)

    video = args.video or pick_one_video(args.video_dir, seed=args.seed)
    print(f"session: {sdir.name}")
    print(f"audio: {audio.name} ({probe_duration(audio)/60:.1f} min)")
    print(f"video: {video.name} (single background)")

    cues: list[Cue] = []
    mode = args.subtitle_mode
    if mode in ("auto", "plan") and session_json:
        cues = cues_from_session_plan(session_json)
        # plan without text is useless
        if sum(1 for c in cues if c.text) < 3 and mode == "auto":
            cues = []
    if not cues and mode in ("auto", "whisper"):
        if not vo:
            print("No VO track for whisper subtitles", file=sys.stderr)
            return 1
        model = resolve_model()
        print(f"subtitle align: whisper ({model.name}) on {vo.name}")
        cues = cues_from_whisper(vo, args.work / sdir.name, model)
    if not cues:
        print("No subtitle cues produced", file=sys.stderr)
        return 1
    print(f"subtitle cues: {len(cues)}")

    ass_path = sdir / f"{sdir.name}_subtitles.ass"
    build_ass(cues, ass_path)
    # also plain srt for portability
    srt_path = sdir / f"{sdir.name}_subtitles.srt"
    with srt_path.open("w", encoding="utf-8") as f:
        for i, c in enumerate(cues, 1):
            def srt_t(x: float) -> str:
                h = int(x // 3600); m = int((x % 3600) // 60); s = x % 60
                return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")
            f.write(f"{i}\n{srt_t(c.start)} --> {srt_t(c.end)}\n{c.text}\n\n")

    out = sdir / f"{sdir.name}_youtube.mp4"
    render_video(
        audio=audio, video=video, ass=ass_path, out=out,
        speed=args.speed, crf=args.crf, preset=args.preset,
    )
    meta = {
        "session": str(sdir),
        "audio": str(audio),
        "video": str(video),
        "ass": str(ass_path),
        "srt": str(srt_path),
        "out": str(out),
        "speed": args.speed,
        "cue_count": len(cues),
        "subtitle_mode": mode,
    }
    (sdir / f"{sdir.name}_youtube.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("DONE", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
