#!/usr/bin/env python3
# coding: utf-8
"""
Restore recently-used images back to images_pool/available.

Definition of "recent":
- Uses st_ctime (metadata change time) as a proxy for "moved into used".
  On macOS/APFS this updates on rename/move, which matches our use-case.

Safety:
- Supports --dry-run.
- Writes a restore log to reports/ for auditability.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path


def _list_pngs(dir_path: Path) -> list[Path]:
    if not dir_path.exists():
        return []
    return [p for p in dir_path.glob("*.png") if p.is_file()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=30, help="How many images to restore.")
    ap.add_argument(
        "--used-dir",
        default="images_pool/used",
        help="Directory containing used images.",
    )
    ap.add_argument(
        "--available-dir",
        default="images_pool/available",
        help="Directory containing available images.",
    )
    ap.add_argument("--dry-run", action="store_true", help="List actions without moving files.")
    args = ap.parse_args()

    used_dir = Path(args.used_dir)
    avail_dir = Path(args.available_dir)
    avail_dir.mkdir(parents=True, exist_ok=True)

    used_files = _list_pngs(used_dir)
    if not used_files:
        raise SystemExit(f"No PNG files found in {used_dir}")

    used_files.sort(key=lambda p: p.stat().st_ctime, reverse=True)
    selected = used_files[: max(0, args.count)]

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    log_path = report_dir / f"restored_images_{ts}.txt"

    moved = 0
    skipped = 0
    conflicts = 0

    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"used_dir={used_dir}\n")
        f.write(f"available_dir={avail_dir}\n")
        f.write(f"count={args.count}\n")
        f.write(f"dry_run={args.dry_run}\n")
        f.write("files:\n")

        for p in selected:
            target = avail_dir / p.name
            ctime = p.stat().st_ctime
            f.write(f"{ctime:.0f}\t{p.name}\n")
            if target.exists():
                conflicts += 1
                continue
            if args.dry_run:
                skipped += 1
                continue
            try:
                p.rename(target)
                moved += 1
            except OSError:
                # Cross-device fallback (rare). We avoid importing shutil unless needed.
                try:
                    import shutil  # noqa: PLC0415

                    shutil.move(str(p), str(target))
                    moved += 1
                except Exception:
                    skipped += 1

    used_after = len(_list_pngs(used_dir))
    avail_after = len(_list_pngs(avail_dir))

    print(f"log: {log_path}")
    print(f"moved: {moved}")
    print(f"skipped: {skipped}")
    print(f"conflicts: {conflicts}")
    print(f"used_after: {used_after}")
    print(f"available_after: {avail_after}")


if __name__ == "__main__":
    main()

