#!/usr/bin/env python3
# coding: utf-8
"""Fine-cut harvest for Locke masters → speech atom library.

Tiered silence model:
  - micro pause  < 0.70s  → keep inside phrase (do not cut)
  - phrase break 0.70–2.4s → L1 atom boundary
  - section break > 2.4s  → section boundary (+ optional long rest later)

Usage:
  ./.venv/bin/python scripts/sg/harvest_atoms_v2.py --clean
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

LOCKE_DIR = Path.home() / "Studio/Library/sg/assets/vo/Locke"
ATOMS_ROOT = Path.home() / "Studio/Library/sg/atoms"

# Exact masters the user listed (resolved by glob/name contains)
MASTER_KEYS = [
    "Welcome_to_Sleep_in_Grace",
    "Fall_Asleep_in_God",
    "Rest_Secure",
    "Isaiah26_Philippians4_Psalm4",
    "John10_Psalm62",
    "Psalm121_Lamentations3_2025-09-02",
    "Peace_Beyond_Understanding",
    "God_Is_Still_Speaking",
    "0908_Peace_That_Surpasses",
    "0906Fall_Asleep_Knowing",
]

ROLE_DIRS = [
    "open", "breath", "safety", "release", "deepen",
    "scripture", "poetic", "bless", "close", "misc",
]

THEME_RULES = [
    (r"welcome", ["open", "welcome", "brand"]),
    (r"deuteronomy|0906", ["scripture", "deuteronomy", "safety", "presence"]),
    (r"0908|surpasses|john.?14", ["scripture", "john14", "philippians", "peace"]),
    (r"still_speaking|best_night_prayer_for_deep_sleep_god", ["scripture", "psalm121", "lamentations", "watch"]),
    (r"peace_beyond|philippians_4_6", ["scripture", "philippians", "peace", "release"]),
    (r"rest_secure|psalm_4|isaiah_41", ["scripture", "psalm4", "isaiah41", "safety"]),
    (r"isaiah26", ["scripture", "isaiah26", "philippians", "psalm4", "peace"]),
    (r"john10|psalm62", ["scripture", "john10", "psalm62", "safety"]),
    (r"psalm121_lamentations3_2025-09-02", ["scripture", "psalm121", "lamentations"]),
    (r"psalm16|matthew28|fall_asleep_in_god", ["scripture", "psalm16", "matthew28", "presence"]),
]


@dataclass
class Atom:
    id: str
    path: str
    source_master: str
    voice: str
    t_start: float
    t_end: float
    duration_sec: float
    role: str
    tags: list[str] = field(default_factory=list)
    cut_tier: str = "phrase"  # phrase | breath
    created_at: str = ""


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def probe_duration(path: Path) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def detect_silences(path: Path, noise_db: float = -33.0, min_d: float = 0.28) -> list[tuple[float, float, float]]:
    """Return (start, end, duration) silence regions."""
    af = f"silencedetect=noise={noise_db}dB:d={min_d}"
    r = run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", af, "-f", "null", "-"])
    starts, ends, durs = [], [], []
    for line in (r.stderr or "").splitlines():
        if "silence_start:" in line:
            try:
                starts.append(float(line.split("silence_start:")[1].split()[0]))
            except ValueError:
                pass
        if "silence_end:" in line:
            try:
                end = float(line.split("silence_end:")[1].split()[0].replace("|", ""))
                ends.append(end)
                if "silence_duration:" in line:
                    durs.append(float(line.split("silence_duration:")[1].strip()))
                else:
                    durs.append(0.0)
            except ValueError:
                pass
    out = []
    i = j = 0
    while i < len(starts) and j < len(ends):
        if ends[j] > starts[i]:
            d = durs[j] if j < len(durs) else ends[j] - starts[i]
            out.append((starts[i], ends[j], d))
            i += 1
            j += 1
        else:
            j += 1
    return out


def phrase_boundaries(duration: float, silences: list[tuple[float, float, float]], phrase_gap: float = 0.70) -> list[float]:
    """Cut points at mid of phrase-level silences (not micro breaths)."""
    cuts = [0.0]
    for s0, s1, d in silences:
        if d >= phrase_gap:
            cuts.append((s0 + s1) / 2.0)
    cuts.append(duration)
    # unique sorted
    cuts = sorted(set(round(c, 3) for c in cuts if 0 <= c <= duration + 0.01))
    if cuts[0] != 0.0:
        cuts = [0.0] + cuts
    if cuts[-1] < duration - 0.05:
        cuts.append(duration)
    return cuts


def segments_from_cuts(cuts: list[float], min_sec: float, max_sec: float) -> list[tuple[float, float]]:
    segs = []
    for a, b in zip(cuts, cuts[1:]):
        if b - a < min_sec:
            # try merge forward later
            if segs and (b - segs[-1][0]) <= max_sec:
                segs[-1] = (segs[-1][0], b)
            continue
        if b - a > max_sec:
            # hard split long section into ~max chunks at equal parts
            n = int((b - a) // max_sec) + 1
            step = (b - a) / n
            for i in range(n):
                x0 = a + i * step
                x1 = a + (i + 1) * step if i < n - 1 else b
                if x1 - x0 >= min_sec:
                    segs.append((x0, x1))
        else:
            segs.append((a, b))
    # merge tiny leftovers
    merged = []
    for a, b in segs:
        if merged and (b - a) < min_sec and (b - merged[-1][0]) <= max_sec:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged


def theme_tags(name: str) -> list[str]:
    low = name.lower().replace(" ", "_")
    tags = []
    for pat, ts in THEME_RULES:
        if re.search(pat, low, re.I):
            tags.extend(ts)
    # unique
    out = []
    for t in tags:
        if t not in out:
            out.append(t)
    if "scripture" not in out and not any(x in low for x in ["welcome"]):
        out.append("scripture")
    return out


def assign_role(dur: float, pos: float, tags: list[str], is_welcome: bool) -> str:
    if dur <= 2.0:
        return "breath"
    if pos < 0.08 or (is_welcome and pos < 0.22):
        return "open"
    if pos > 0.90:
        return "close"
    if dur >= 3.0:
        return "scripture" if "scripture" in tags else "poetic"
    if 0.28 <= pos <= 0.50:
        return "release"
    if 0.50 < pos <= 0.82:
        return "deepen"
    if "safety" in tags or "peace" in tags:
        return "safety"
    return "poetic" if dur >= 2.4 else "misc"


def export_clip(src: Path, t0: float, t1: float, dst: Path) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    # slight fade to avoid clicks
    fad = min(0.04, (t1 - t0) / 8)
    af = f"afade=t=in:st=0:d={fad:.3f},afade=t=out:st={max(0, t1-t0-fad):.3f}:d={fad:.3f}"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}", "-i", str(src),
        "-af", af, "-ac", "1", "-ar", "44100",
        "-c:a", "libmp3lame", "-b:a", "192k", str(dst),
    ]
    r = run(cmd)
    return r.returncode == 0 and dst.exists() and dst.stat().st_size > 400


def resolve_masters(locke: Path) -> list[Path]:
    all_mp3 = sorted(locke.glob("*.mp3"))
    chosen = []
    for key in MASTER_KEYS:
        key_l = key.lower()
        hits = [p for p in all_mp3 if key_l in p.name.lower().replace(" ", "_").replace("'", "'")]
        if not hits:
            # looser
            parts = re.split(r"[_\W]+", key_l)
            parts = [x for x in parts if len(x) > 3][:3]
            hits = [p for p in all_mp3 if all(x in p.name.lower() for x in parts)]
        if hits:
            # prefer longest name match unique
            hits = sorted(hits, key=lambda p: len(p.name), reverse=True)
            if hits[0] not in chosen:
                chosen.append(hits[0])
        else:
            print(f"WARN: no master for key={key}")
    # ensure all locke files if keys missed some listed
    if len(chosen) < len(all_mp3):
        for p in all_mp3:
            if p not in chosen:
                chosen.append(p)
    return chosen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--locke", type=Path, default=LOCKE_DIR)
    ap.add_argument("--atoms-root", type=Path, default=ATOMS_ROOT)
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--min-sec", type=float, default=1.1)
    ap.add_argument("--max-sec", type=float, default=14.0)
    ap.add_argument("--phrase-gap", type=float, default=0.70)
    args = ap.parse_args()

    masters = resolve_masters(args.locke)
    if not masters:
        print("No masters", file=sys.stderr)
        return 1

    root = args.atoms_root
    root.mkdir(parents=True, exist_ok=True)
    for d in ROLE_DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
        if args.clean:
            for p in (root / d).glob("*"):
                if p.suffix in {".mp3", ".json"}:
                    p.unlink(missing_ok=True)

    print(f"Fine-cut harvest v2 · {len(masters)} masters → {root}")
    all_atoms: list[Atom] = []

    for master in masters:
        dur = probe_duration(master)
        print(f"\n== {master.name} ({dur/60:.1f} min)")
        sil = detect_silences(master)
        cuts = phrase_boundaries(dur, sil, phrase_gap=args.phrase_gap)
        segs = segments_from_cuts(cuts, args.min_sec, args.max_sec)
        tags0 = theme_tags(master.name)
        is_welcome = "welcome" in tags0
        print(f"  silences={len(sil)} cuts={len(cuts)} segs={len(segs)} tags={tags0[:6]}")

        for idx, (t0, t1) in enumerate(segs):
            length = t1 - t0
            if length < args.min_sec:
                continue
            pos = idx / max(len(segs) - 1, 1)
            role = assign_role(length, pos, tags0, is_welcome)
            tags = list(dict.fromkeys(tags0 + [role]))
            if role == "close":
                tags.append("bless")
            hid = hashlib.sha1(f"{master.name}:{t0:.3f}:{t1:.3f}".encode()).hexdigest()[:10]
            aid = f"{role}_{hid}"
            out = root / role / f"{aid}.mp3"
            # trim 20ms edges inside
            a, b = t0 + 0.02, t1 - 0.02
            if b - a < args.min_sec:
                a, b = t0, t1
            if not export_clip(master, a, b, out):
                print(f"  fail export {t0:.1f}-{t1:.1f}")
                continue
            atom = Atom(
                id=aid,
                path=str(out),
                source_master=str(master),
                voice="Locke",
                t_start=round(a, 3),
                t_end=round(b, 3),
                duration_sec=round(probe_duration(out) or (b - a), 3),
                role=role,
                tags=tags,
                cut_tier="phrase",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            out.with_suffix(".json").write_text(json.dumps(asdict(atom), ensure_ascii=False, indent=2), encoding="utf-8")
            all_atoms.append(atom)
        print(f"  atoms+={sum(1 for a in all_atoms if a.source_master == str(master))}")

    roles = Counter(a.role for a in all_atoms)
    manifest = {
        "version": 2,
        "voice": "Locke",
        "method": "tiered_silence_phrase_cut",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(args.locke),
        "masters": [str(m) for m in masters],
        "count": len(all_atoms),
        "roles": dict(roles),
        "params": {
            "min_sec": args.min_sec,
            "max_sec": args.max_sec,
            "phrase_gap": args.phrase_gap,
        },
        "atoms": [asdict(a) for a in all_atoms],
    }
    man = root / "manifest.json"
    man.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDONE {len(all_atoms)} atoms")
    print("roles:", dict(roles))
    print("manifest:", man)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
