#!/usr/bin/env python3
# coding: utf-8
"""SiG x TOYTUNE long-form episode, with liturgical subtitles.

v4 (direction 2026-08-03): the TOYTUNE music is fully muted — the whole hour
rests on a CHL500 instrumental mix, ducked under the VO. The video opens with
the staged intro (title -> sanctuary -> cross -> orbits, rendered by
render_christian_orbits.py intro), then the 8-minute master loops.

Timeline:
  [0 .. 30 s]          intro video; chill bed from 0; VO enters at 10 s
  [10 s .. VO end]     prayer with subtitles, bed ducking under Locke
  [VO end .. total]    the same chill mix carries the hour — music fills
                       whatever the VO does not
  [last 5 s]           everything fades together

Subtitles are built from the session plan (atom text + timings) and styled
after church print: Hoefler Text, warm ivory, letterspaced, a whisper of deep
indigo behind the glyphs, 0.7 s in / 0.9 s out fades. Burning them means the
video is re-encoded — budget roughly real-time for a 1 h master.

  ./.venv/bin/python scripts/sg/toytune_episode.py \\
      --session-dir ~/Studio/Workspace/outputs/sg/sessions/sg_toytune_ep1 \\
      --total-minutes 60
  # 40-second styled sample first:
  ./.venv/bin/python scripts/sg/toytune_episode.py --session-dir ... --sample 40
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ORBITS_DEFAULT = Path("/Users/z/Projects/TOYTUNE/output/christian_orbits_master.mp4")
INTRO_DEFAULT = Path("/Users/z/Projects/TOYTUNE/output/christian_orbits_intro.mp4")
CHILL_DEFAULT = Path.home() / "Studio/Library/chl/CHL500"

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Prayer,Hoefler Text,46,&H00E6EFF7,&H00E6EFF7,&H50211208,&H00000000,0,0,0,0,100,100,1.3,0,1,1.6,0,2,140,140,96,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def find_vo(session_dir: Path) -> Path:
    sid = session_dir.name
    for suffix in ("_vo_padded.mp3", "_vo.mp3"):
        p = session_dir / f"{sid}{suffix}"
        if p.exists():
            return p
    raise FileNotFoundError(f"no VO track in {session_dir}")


def _ass_time(t: float) -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def build_subtitles(session_dir: Path, vo_start: float, out_path: Path,
                    atempo: float = 1.0) -> int:
    plan = json.loads(
        (session_dir / f"{session_dir.name}_session.json").read_text())["plan"]
    lines = []
    for entry in plan:
        if entry.get("type") != "atom" or not entry.get("text"):
            continue
        text = " ".join(entry["text"].split())
        a = entry["start_sec"] / atempo + vo_start
        b = entry["end_sec"] / atempo + vo_start + 0.35   # let the line breathe out
        lines.append(f"Dialogue: 0,{_ass_time(a)},{_ass_time(b)},Prayer,,0,0,0,,"
                     f"{{\\fad(700,900)\\blur0.8}}{text}")
    out_path.write_text(ASS_HEADER + "\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def build_chill_mix(chill_dir: Path, need_sec: float, out_path: Path,
                    crossfade: float, seed: int | None) -> list[str]:
    tracks = sorted(chill_dir.glob("*.mp3"))
    if not tracks:
        raise FileNotFoundError(f"no mp3 in {chill_dir}")
    rng = random.Random(seed)
    rng.shuffle(tracks)
    chosen: list[tuple[Path, float]] = []
    total = 0.0
    for t in tracks:
        d = probe_duration(t)
        if d < 45:
            continue
        chosen.append((t, d))
        total += d - (crossfade if len(chosen) > 1 else 0)
        if total >= need_sec + 90:
            break
    if total < need_sec:
        raise RuntimeError(f"chill library too short: {total:.0f}s < {need_sec:.0f}s")

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for t, _ in chosen:
        cmd += ["-i", str(t)]
    if len(chosen) == 1:
        fc = "[0:a]anull[mix]"
    else:
        parts, prev = [], "[0:a]"
        for i in range(1, len(chosen)):
            nxt = f"[x{i}]" if i < len(chosen) - 1 else "[mix]"
            parts.append(f"{prev}[{i}:a]acrossfade=d={crossfade}{nxt}")
            prev = nxt
        fc = ";".join(parts)
    fc += ";[mix]loudnorm=I=-21:TP=-2:LRA=9[out]"
    cmd += ["-filter_complex", fc, "-map", "[out]", "-c:a", "aac", "-b:a", "256k",
            str(out_path)]
    print(f"chill set: {len(chosen)} tracks, {total/60:.1f} min material")
    if subprocess.run(cmd).returncode != 0:
        raise RuntimeError("chill mix build failed")
    return [t.name for t, _ in chosen]


def main() -> int:
    ap = argparse.ArgumentParser(description="TOYTUNE-background SiG long-form episode")
    ap.add_argument("--session-dir", type=Path, required=True)
    ap.add_argument("--orbits", type=Path, default=ORBITS_DEFAULT)
    ap.add_argument("--chill-dir", type=Path, default=CHILL_DEFAULT)
    ap.add_argument("--total-minutes", type=float, default=60.0)
    ap.add_argument("--vo-start", type=float, default=10.0,
                    help="Music runs this long before the first spoken word")
    ap.add_argument("--intro", type=Path, default=INTRO_DEFAULT)
    ap.add_argument("--chill-crossfade", type=float, default=8.0)
    ap.add_argument("--vo-gain-db", type=float, default=3.5)
    ap.add_argument("--vo-atempo", type=float, default=0.88,
                    help="VO 减速系数(<1 更慢;停顿随之等比拉长)")
    ap.add_argument("--bed-gain-db", type=float, default=-7.0,
                    help="音乐床整体增益(负值更安静)")
    ap.add_argument("--no-subs", action="store_true")
    ap.add_argument("--sample", type=float, default=None,
                    help="Render only the first N seconds (style check)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    session_dir = args.session_dir.expanduser()
    vo = find_vo(session_dir)
    if not args.orbits.exists():
        print(f"Missing orbits master: {args.orbits}", file=sys.stderr)
        return 1

    vo_dur = probe_duration(vo)
    if vo_dur <= 0:
        print("cannot probe VO duration", file=sys.stderr)
        return 1
    vo_dur = vo_dur / args.vo_atempo          # 减速后的真实时长
    vo_end = args.vo_start + vo_dur
    total = args.sample if args.sample else args.total_minutes * 60.0
    if not args.sample and total < vo_end + 300:
        print(f"--total-minutes too short for a {vo_dur/60:.1f} min VO",
              file=sys.stderr)
        return 1

    ass_path = session_dir / f"{session_dir.name}_prayer.ass"
    n_cues = 0
    if not args.no_subs:
        n_cues = build_subtitles(session_dir, args.vo_start, ass_path,
                                 args.vo_atempo)
        print(f"subtitles: {n_cues} cues -> {ass_path.name}")

    if args.sample:
        out = session_dir / f"{session_dir.name}_toytune_sample.mp4"
    else:
        tag = (f"{int(args.total_minutes // 60)}h"
               if args.total_minutes % 60 == 0 else f"{int(args.total_minutes)}min")
        out = args.out or session_dir / f"{session_dir.name}_toytune_{tag}.mp4"

    fade_final = 5.0

    with tempfile.TemporaryDirectory(prefix="sig_chill_") as tmp:
        tmp = Path(tmp)
        setlist: list[str] = []

        # ---- Pass A: the full audio timeline. The TOYTUNE music is muted by
        # decree; the hour rests on the chill bed alone, ducked under the VO.
        mix_path = tmp / "timeline.m4a"
        delay_ms = int(args.vo_start * 1000)
        chill_mix = tmp / "chill_mix.m4a"
        setlist = build_chill_mix(args.chill_dir, total + 60, chill_mix,
                                  args.chill_crossfade, args.seed)
        fc = (
            f"[1:a]atrim=0:{total:.3f},volume={args.bed_gain_db}dB,"
            f"afade=t=in:st=0:d=1.5[bed];"
            f"[0:a]atempo={args.vo_atempo},adelay={delay_ms}|{delay_ms},"
            f"volume={args.vo_gain_db}dB,"
            f"asplit=2[sk0][voice];[sk0]apad[sck];"
            f"[bed][sck]sidechaincompress=threshold=0.015:ratio=8:attack=220:"
            f"release=1100[bgd];"
            f"[bgd][voice]amix=inputs=2:duration=first:normalize=0,"
            f"alimiter=limit=0.95,"
            f"afade=t=out:st={total - fade_final:.3f}:d={fade_final:.3f}[aout]"
        )
        acmd = ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-i", str(vo), "-i", str(chill_mix),
                "-filter_complex", fc, "-map", "[aout]",
                "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                "-t", f"{total:.3f}", str(mix_path)]
        print("pass A: audio timeline…", flush=True)
        if subprocess.run(acmd).returncode != 0:
            return 1

        # ---- Pass B: staged intro, then the master loops; one fade closes it.
        print("pass B: video mux…", flush=True)
        intro_dur = probe_duration(args.intro)
        if intro_dur <= 0:
            print(f"Missing intro: {args.intro}", file=sys.stderr)
            return 1
        master_dur = max(1.0, probe_duration(args.orbits))
        loops = int((total - intro_dur) / master_dur) + 1
        vgraph = (
            f"[0:v][1:v]concat=n=2:v=1:a=0,trim=0:{total:.3f},"
            f"setpts=PTS-STARTPTS,"
            f"fade=t=out:st={total - fade_final:.3f}:d={fade_final:.3f}"
        )
        if not args.no_subs:
            esc = str(ass_path).replace("\\", "/").replace(":", "\\:").replace("'", r"\'")
            vgraph += f",ass='{esc}'"
        vgraph += "[vout]"
        vcmd = ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "info",
                "-stats",
                "-i", str(args.intro),
                "-stream_loop", str(loops), "-i", str(args.orbits),
                "-i", str(mix_path),
                "-filter_complex", vgraph,
                "-map", "[vout]", "-map", "2:a:0",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "copy", "-t", f"{total:.3f}", str(out)]
        rc = subprocess.run(vcmd).returncode
        if rc != 0:
            return rc

    if not args.sample:
        manifest = {
            "session": str(session_dir), "vo_minutes": round(vo_dur / 60, 2),
            "vo_start_sec": args.vo_start, "total_minutes": total / 60,
            "orbits": str(args.orbits), "intro": str(args.intro),
            "subtitle_cues": n_cues, "vo_atempo": args.vo_atempo,
            "bed_gain_db": args.bed_gain_db,
            "music": "CHL500 only (toytune muted)",
            "chill_setlist": setlist,
        }
        (session_dir / f"{out.stem}_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False))
    print("DONE", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
