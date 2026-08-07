#!/usr/bin/env python3
# coding: utf-8
"""Harvest L1 speech atoms from SiG Locke master VO files via silence cuts.

Usage:
  ./.venv/bin/python scripts/sg/harvest_atoms.py
  ./.venv/bin/python scripts/sg/harvest_atoms.py --voice Locke --min-sec 1.2 --max-sec 14
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_VO_ROOT = Path.home() / "Studio/Library/sg/assets/vo"
DEFAULT_ATOMS_ROOT = Path.home() / "Studio/Library/sg/atoms"

ROLE_DIRS = {
    "open": "open",
    "breath": "breath",
    "safety": "safety",
    "release": "release",
    "deepen": "deepen",
    "scripture": "scripture",
    "poetic": "poetic",
    "bless": "bless",
    "close": "close",
    "misc": "misc",
}

# Filename / position heuristics → tags + primary role
SOURCE_THEME_TAGS = [
    (r"welcome", ["open", "welcome"]),
    (r"deuteronomy|deut", ["scripture", "deuteronomy", "safety"]),
    (r"john.?14|philippians.?4.?7|surpasses", ["scripture", "john14", "philippians", "peace"]),
    (r"psalm.?91|shadow.?of.?his.?wings|wings", ["scripture", "psalm91", "safety", "wings"]),
    (r"psalm.?121|lamentations", ["scripture", "psalm121", "lamentations", "watch"]),
    (r"philippians.?4.?6|peace.?beyond|anxiety", ["scripture", "philippians", "peace", "release"]),
    (r"psalm.?4|isaiah.?41|rest.?secure", ["scripture", "psalm4", "isaiah41", "safety"]),
    (r"isaiah.?26|philippians.?4|psalm.?4", ["scripture", "isaiah26", "philippians", "psalm4", "peace"]),
    (r"john.?10|psalm.?62", ["scripture", "john10", "psalm62", "safety"]),
    (r"psalm.?16|matthew.?28|fall.?asleep", ["scripture", "psalm16", "matthew28", "presence"]),
]

DURATION_ROLE_HINTS = [
    # (min, max, role) applied when theme doesn't force role
    (0.8, 2.2, "breath"),
    (2.2, 5.5, "misc"),
    (5.5, 14.0, "scripture"),
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
    text: str | None = None
    created_at: str = ""


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def probe_duration(path: Path) -> float:
    r = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def silence_regions(
    path: Path,
    *,
    noise_db: float = -34.0,
    min_silence: float = 0.40,
) -> list[tuple[float, float]]:
    """Return list of (silence_start, silence_end)."""
    af = f"silencedetect=noise={noise_db}dB:d={min_silence}"
    r = _run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", af, "-f", "null", "-"])
    starts: list[float] = []
    ends: list[float] = []
    for line in (r.stderr or "").splitlines():
        if "silence_start:" in line:
            try:
                starts.append(float(line.split("silence_start:")[1].strip().split()[0]))
            except (IndexError, ValueError):
                pass
        if "silence_end:" in line:
            try:
                # silence_end: 5.64 | silence_duration: 3.7
                part = line.split("silence_end:")[1].strip().split()[0]
                ends.append(float(part.replace("|", "")))
            except (IndexError, ValueError):
                pass
    # pair starts/ends greedily
    regions: list[tuple[float, float]] = []
    i = j = 0
    while i < len(starts) and j < len(ends):
        if ends[j] > starts[i]:
            regions.append((starts[i], ends[j]))
            i += 1
            j += 1
        else:
            j += 1
    return regions


def speech_islands(
    duration: float,
    silences: list[tuple[float, float]],
    *,
    pad: float = 0.04,
    merge_gap: float = 1.05,
    max_merge_sec: float = 12.5,
) -> list[tuple[float, float]]:
    """Invert silences to speech [start,end) within [0, duration].

    Short pauses (breaths) are merged so scripture sentences stay intact.
    """
    if not silences:
        return [(0.0, duration)] if duration > 0.5 else []
    islands: list[tuple[float, float]] = []
    cursor = 0.0
    for s0, s1 in sorted(silences):
        if s0 > cursor + 0.12:
            a = max(0.0, cursor)
            b = min(duration, s0)
            if b - a >= 0.4:
                islands.append((a, b))
        cursor = max(cursor, s1)
    if duration > cursor + 0.12:
        islands.append((cursor, duration))

    # Merge islands separated by short gaps (keep prayer phrases whole)
    if islands:
        merged: list[tuple[float, float]] = [islands[0]]
        for a, b in islands[1:]:
            pa, pb = merged[-1]
            gap = a - pb
            if gap <= merge_gap and (b - pa) <= max_merge_sec:
                merged[-1] = (pa, b)
            else:
                merged.append((a, b))
        islands = merged

    out: list[tuple[float, float]] = []
    for a, b in islands:
        a2, b2 = a + pad, b - pad
        if b2 - a2 >= 0.45:
            out.append((a2, b2))
    return out


def theme_tags_for_source(name: str) -> list[str]:
    low = name.lower()
    tags: list[str] = []
    for pat, tgs in SOURCE_THEME_TAGS:
        if re.search(pat, low, re.I):
            tags.extend(tgs)
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def assign_role(
    duration: float,
    index: int,
    total: int,
    source_tags: list[str],
) -> tuple[str, list[str]]:
    """Assign primary role for combinator slots.

    Priority: duration shape first (breath vs phrase), then arc position,
    then theme. Long prayer masters are mostly mid-arc scripture/poetic.
    """
    tags = list(source_tags)
    pos = index / max(total - 1, 1)
    is_welcome = "welcome" in source_tags

    # 1) Micro breath / cue lines
    if duration <= 2.2:
        role = "breath"
        tags.append("breath")
    # 2) Opening arc
    elif pos < 0.07 or (is_welcome and pos < 0.25 and duration < 8):
        role = "open"
        tags.append("open")
    # 3) Closing arc
    elif pos > 0.91:
        role = "close"
        tags.extend(["close", "bless"])
    # 4) Substantial phrases → scripture when master is scriptural, else poetic
    elif duration >= 3.2:
        # Long-enough phrase: treat as scripture carrier on prayer masters
        if "scripture" in source_tags or any(
            t.startswith("psalm") or t.startswith("john") or t.startswith("isaiah")
            or t.startswith("philippians") or t.startswith("matthew")
            or t.startswith("lamentations") or t.startswith("deuteronomy")
            for t in source_tags
        ):
            role = "scripture"
            tags.append("scripture")
        else:
            role = "poetic"
            tags.append("poetic")
    # 5) Mid-arc medium lines (2.2–3.2s)
    elif 0.28 <= pos <= 0.52:
        role = "release"
        tags.append("release")
    elif 0.52 < pos <= 0.84:
        role = "deepen"
        tags.append("deepen")
    elif "safety" in source_tags or "peace" in source_tags:
        role = "safety"
        tags.append("safety")
    else:
        role = "poetic" if duration >= 2.5 else "misc"
        tags.append(role)

    # Bless bias for soft close-ish scripture about peace
    if role == "scripture" and pos > 0.8:
        tags.append("bless")

    seen: set[str] = set()
    utags = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            utags.append(t)
    return role, utags


def export_atom(
    source: Path,
    t0: float,
    t1: float,
    out_path: Path,
) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # re-encode mono 44.1k mp3 for consistency
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}",
        "-i", str(source),
        "-ac", "1", "-ar", "44100",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_path),
    ]
    r = _run(cmd)
    return r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 500


def atom_id(source: Path, t0: float, t1: float, role: str) -> str:
    h = hashlib.sha1(f"{source.name}:{t0:.3f}:{t1:.3f}".encode()).hexdigest()[:10]
    return f"{role}_{h}"


def harvest_master(
    master: Path,
    *,
    voice: str,
    atoms_root: Path,
    min_sec: float,
    max_sec: float,
    noise_db: float,
    min_silence: float,
) -> list[Atom]:
    duration = probe_duration(master)
    if duration < 1.0:
        print(f"  skip (no duration): {master.name}")
        return []
    silences = silence_regions(master, noise_db=noise_db, min_silence=min_silence)
    islands = speech_islands(duration, silences)
    # split overlong islands at midpoint recursively-ish
    refined: list[tuple[float, float]] = []
    for a, b in islands:
        length = b - a
        if length <= max_sec:
            if length >= min_sec:
                refined.append((a, b))
            continue
        # split into chunks ~max_sec with small gaps preferred via equal parts
        n = int(length // max_sec) + 1
        step = length / n
        for i in range(n):
            x0 = a + i * step
            x1 = a + (i + 1) * step if i < n - 1 else b
            if x1 - x0 >= min_sec:
                refined.append((x0, x1))

    theme = theme_tags_for_source(master.name)
    atoms: list[Atom] = []
    total = len(refined)
    for idx, (t0, t1) in enumerate(refined):
        dur = t1 - t0
        if dur < min_sec or dur > max_sec + 0.5:
            continue
        role, tags = assign_role(dur, idx, total, theme)
        tags = list(dict.fromkeys(tags + theme))
        aid = atom_id(master, t0, t1, role)
        role_dir = atoms_root / ROLE_DIRS.get(role, "misc")
        out = role_dir / f"{aid}.mp3"
        if not export_atom(master, t0, t1, out):
            print(f"  export fail {master.name} {t0:.1f}-{t1:.1f}")
            continue
        atom = Atom(
            id=aid,
            path=str(out),
            source_master=str(master),
            voice=voice,
            t_start=round(t0, 3),
            t_end=round(t1, 3),
            duration_sec=round(probe_duration(out) or dur, 3),
            role=role,
            tags=tags,
            text=None,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        # sidecar
        side = out.with_suffix(".json")
        side.write_text(json.dumps(asdict(atom), ensure_ascii=False, indent=2), encoding="utf-8")
        atoms.append(atom)
    return atoms


def main() -> int:
    ap = argparse.ArgumentParser(description="Harvest SiG speech atoms from Locke masters")
    ap.add_argument("--vo-root", type=Path, default=DEFAULT_VO_ROOT)
    ap.add_argument("--atoms-root", type=Path, default=DEFAULT_ATOMS_ROOT)
    ap.add_argument("--voice", default="Locke")
    ap.add_argument("--min-sec", type=float, default=1.15)
    ap.add_argument("--max-sec", type=float, default=13.5)
    ap.add_argument("--noise-db", type=float, default=-34.0)
    ap.add_argument("--min-silence", type=float, default=0.40)
    ap.add_argument("--clean", action="store_true", help="Delete existing role atom mp3/json before harvest")
    args = ap.parse_args()

    voice_dir = args.vo_root / args.voice
    if not voice_dir.exists():
        print(f"Voice dir not found: {voice_dir}", file=sys.stderr)
        return 1

    masters = sorted(voice_dir.glob("*.mp3"))
    if not masters:
        print(f"No masters in {voice_dir}", file=sys.stderr)
        return 1

    args.atoms_root.mkdir(parents=True, exist_ok=True)
    for d in ROLE_DIRS.values():
        (args.atoms_root / d).mkdir(parents=True, exist_ok=True)

    if args.clean:
        for d in ROLE_DIRS.values():
            for p in (args.atoms_root / d).glob("*"):
                if p.suffix in {".mp3", ".json"}:
                    p.unlink()

    print(f"Harvest voice={args.voice} masters={len(masters)}")
    print(f"atoms → {args.atoms_root}")

    all_atoms: list[Atom] = []
    for master in masters:
        print(f"\n== {master.name} ({probe_duration(master)/60:.1f} min)")
        atoms = harvest_master(
            master,
            voice=args.voice,
            atoms_root=args.atoms_root,
            min_sec=args.min_sec,
            max_sec=args.max_sec,
            noise_db=args.noise_db,
            min_silence=args.min_silence,
        )
        print(f"  atoms: {len(atoms)}")
        all_atoms.extend(atoms)

    # role counts
    from collections import Counter
    roles = Counter(a.role for a in all_atoms)
    manifest = {
        "voice": args.voice,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(voice_dir),
        "atoms_root": str(args.atoms_root),
        "count": len(all_atoms),
        "roles": dict(roles),
        "params": {
            "min_sec": args.min_sec,
            "max_sec": args.max_sec,
            "noise_db": args.noise_db,
            "min_silence": args.min_silence,
        },
        "atoms": [asdict(a) for a in all_atoms],
    }
    man_path = args.atoms_root / "manifest.json"
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDONE {len(all_atoms)} atoms → {man_path}")
    print("roles:", dict(roles))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
