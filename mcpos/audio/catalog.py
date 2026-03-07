"""
mcpos/audio/catalog.py — Multi-channel library scanner

Public API:
    scan_library(library_root, channel_id, **kwargs) -> list[Track]
    scan_bpm_library(library_root, cache_csv=None) -> list[Track]
    scan_sg_library(instrumental_root, vocal_root, catalog_csv=None) -> list[Track]
    get_track_duration(path) -> float
    write_catalog_cache(tracks, cache_path) -> None
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path
from typing import Optional

from ..models import Track


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def get_track_duration(path: Path) -> float:
    """
    Use ffprobe to get audio duration in seconds.
    Returns 0.0 on any error.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return 0.0


def _stem_to_title(stem: str) -> str:
    """Convert a filename stem to a readable title."""
    return stem.replace("_", " ").replace("-", " - ").strip()


def _safe_float(value: str | None, default: float | None = None) -> float | None:
    """Parse a string as float, returning default on failure."""
    if value is None or str(value).strip() in ("", "nan", "NaN", "None"):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# BPM library scanner (KAT / RBR)
# ---------------------------------------------------------------------------

def scan_bpm_library(
    library_root: Path,
    cache_csv: Optional[Path] = None,
) -> list[Track]:
    """
    Scan a BPM-based library (KAT or RBR) and return Track objects.

    If cache_csv exists, loads duration/bpm/silence from it. Files not in
    the cache have their duration measured via ffprobe (slow first run).

    Cache CSV columns:
        path, title, bpm, bpm_confidence, duration_sec,
        intro_silence_sec, outro_silence_sec
    """
    library_root = Path(library_root).expanduser()

    # Build cache index
    cache: dict[str, dict] = {}
    if cache_csv and Path(cache_csv).expanduser().exists():
        cache_path = Path(cache_csv).expanduser()
        with cache_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                p = row.get("path", "").strip()
                if p:
                    cache[p] = row

    tracks: list[Track] = []
    for mp3 in sorted(library_root.rglob("*.mp3")):
        key = str(mp3)
        row = cache.get(key, {})

        title = row.get("title") or _stem_to_title(mp3.stem)
        duration_sec = _safe_float(row.get("duration_sec")) or get_track_duration(mp3)
        bpm = _safe_float(row.get("bpm"))
        bpm_confidence = _safe_float(row.get("bpm_confidence"))
        intro_silence = _safe_float(row.get("intro_silence_sec"), 0.0)
        outro_silence = _safe_float(row.get("outro_silence_sec"), 0.0)

        tracks.append(Track(
            path=mp3,
            title=title,
            duration_sec=duration_sec or 0.0,
            bpm=bpm,
            bpm_confidence=bpm_confidence,
            intro_silence_sec=intro_silence or 0.0,
            outro_silence_sec=outro_silence or 0.0,
        ))

    return tracks


# ---------------------------------------------------------------------------
# SG library scanner (classification CSV)
# ---------------------------------------------------------------------------

def scan_sg_library(
    instrumental_root: Path,
    vocal_root: Optional[Path] = None,
    catalog_csv: Optional[Path] = None,
) -> list[Track]:
    """
    Scan the Sleep in Grace library.

    Priority:
    1. If catalog_csv exists, load Track metadata from it (fast, rich).
    2. Otherwise, scan instrumental_root + vocal_root from filesystem (slow).

    catalog_csv columns (from CHL classification script):
        file, source_path, duration_sec, audio_onset_sec, class,
        Song_Intro_sec, first_vocal_sec, first_vocal_window,
        speech_segments_total, dest_path
    """
    instrumental_root = Path(instrumental_root).expanduser()

    # ---- Path 1: Load from classification CSV ----
    if catalog_csv:
        csv_path = Path(catalog_csv).expanduser()
        if csv_path.exists():
            tracks: list[Track] = []
            with csv_path.open(encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Resolve path: prefer dest_path, fallback to source_path / file
                    dest = row.get("dest_path", "").strip()
                    src = row.get("source_path", "").strip()
                    filename = row.get("file", "").strip()

                    candidate_paths = [
                        Path(dest) if dest else None,
                        Path(src) if src else None,
                    ]
                    # Also try resolving under instrumental_root / vocal_root
                    if filename:
                        candidate_paths += [
                            instrumental_root / filename,
                            (Path(vocal_root).expanduser() / filename) if vocal_root else None,
                        ]

                    track_path: Optional[Path] = None
                    for cp in candidate_paths:
                        if cp and cp.exists():
                            track_path = cp
                            break

                    if track_path is None:
                        continue  # skip missing files

                    title = _stem_to_title(Path(filename).stem if filename else track_path.stem)
                    duration_sec = _safe_float(row.get("duration_sec")) or get_track_duration(track_path)
                    vocal_class = row.get("class", "").strip() or None
                    song_intro_sec = _safe_float(row.get("Song_Intro_sec"))
                    first_vocal_sec = _safe_float(row.get("first_vocal_sec"))

                    tracks.append(Track(
                        path=track_path,
                        title=title,
                        duration_sec=duration_sec or 0.0,
                        vocal_class=vocal_class,
                        song_intro_sec=song_intro_sec,
                        first_vocal_sec=first_vocal_sec,
                    ))

            return tracks

    # ---- Path 2: Filesystem scan ----
    tracks = []

    # Instrumental
    if instrumental_root.exists():
        for mp3 in sorted(instrumental_root.rglob("*.mp3")):
            tracks.append(Track(
                path=mp3,
                title=_stem_to_title(mp3.stem),
                duration_sec=get_track_duration(mp3),
                vocal_class="instrumental",
            ))

    # Vocal
    if vocal_root:
        vr = Path(vocal_root).expanduser()
        if vr.exists():
            for mp3 in sorted(vr.rglob("*.mp3")):
                tracks.append(Track(
                    path=mp3,
                    title=_stem_to_title(mp3.stem),
                    duration_sec=get_track_duration(mp3),
                    vocal_class="vocal",
                ))

    return tracks


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def scan_library(
    library_root: Path,
    channel_id: str,
    **kwargs,
) -> list[Track]:
    """
    Scan a channel's song library and return Track objects.

    Dispatches to the appropriate scanner based on channel_id:
    - "kat" / "rbr": scan_bpm_library(library_root, cache_csv=...)
    - "sg" / "chl": scan_sg_library(library_root, vocal_root=..., catalog_csv=...)

    Extra kwargs are forwarded to the specific scanner.
    """
    if channel_id in ("kat", "rbr"):
        return scan_bpm_library(library_root, **kwargs)
    elif channel_id in ("sg", "chl"):
        return scan_sg_library(library_root, **kwargs)
    else:
        raise ValueError(f"Unknown channel_id '{channel_id}'. Expected 'kat', 'rbr', 'sg', or 'chl'.")


# ---------------------------------------------------------------------------
# Cache writer
# ---------------------------------------------------------------------------

def write_catalog_cache(tracks: list[Track], cache_path: Path) -> None:
    """
    Write a list of Track objects to a CSV cache file.

    Columns: path, title, bpm, bpm_confidence, duration_sec,
             intro_silence_sec, outro_silence_sec, vocal_class,
             song_intro_sec, first_vocal_sec
    """
    cache_path = Path(cache_path).expanduser()
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "path", "title", "bpm", "bpm_confidence", "duration_sec",
        "intro_silence_sec", "outro_silence_sec",
        "vocal_class", "song_intro_sec", "first_vocal_sec",
    ]

    with cache_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for t in tracks:
            writer.writerow({
                "path": str(t.path),
                "title": t.title,
                "bpm": t.bpm if t.bpm is not None else "",
                "bpm_confidence": t.bpm_confidence if t.bpm_confidence is not None else "",
                "duration_sec": f"{t.duration_sec:.3f}",
                "intro_silence_sec": f"{t.intro_silence_sec:.3f}",
                "outro_silence_sec": f"{t.outro_silence_sec:.3f}",
                "vocal_class": t.vocal_class or "",
                "song_intro_sec": f"{t.song_intro_sec:.3f}" if t.song_intro_sec is not None else "",
                "first_vocal_sec": f"{t.first_vocal_sec:.3f}" if t.first_vocal_sec is not None else "",
            })
