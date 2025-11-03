#!/usr/bin/env python3
# coding: utf-8
"""
根据本地歌库目录生成曲库总表，并可选择监听目录变更。

输出 CSV 包含以下字段：
file_path, file_name, title, duration_seconds, added_at, last_used_at, times_used
其中 added_at / last_used_at 使用 ISO 8601 时间字符串（本地时区）。
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

try:
    import yaml  # type: ignore
except ImportError as exc:
    raise SystemExit("缺少 PyYAML 依赖，请先安装 requirements.txt 中列出的包。") from exc

# mutagen 用于读取多种音频格式的时长信息
try:
    from mutagen import File as MutagenFile  # type: ignore
except ImportError:
    MutagenFile = None  # type: ignore[assignment]


def read_config(config_path: Path) -> Dict:
    if not config_path.exists():
        raise FileNotFoundError(f"未找到配置文件：{config_path}")
    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data


def ensure_parent(path: Path) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class TrackRecord:
    file_path: str
    file_name: str
    title: str
    duration_seconds: Optional[float]
    added_at: str
    last_used_at: str = ""
    times_used: int = 0

    @staticmethod
    def from_usage_row(row: Dict[str, str]) -> "TrackRecord":
        return TrackRecord(
            file_path=row.get("file_path", ""),
            file_name=row.get("file_name", ""),
            title=row.get("title", ""),
            duration_seconds=float(row["duration_seconds"]) if row.get("duration_seconds") else None,
            added_at=row.get("added_at", ""),
            last_used_at=row.get("last_used_at", ""),
            times_used=int(row["times_used"]) if row.get("times_used") else 0,
        )

    def to_row(self) -> Dict[str, str]:
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "title": self.title,
            "duration_seconds": f"{self.duration_seconds:.3f}" if self.duration_seconds is not None else "",
            "added_at": self.added_at,
            "last_used_at": self.last_used_at,
            "times_used": str(self.times_used),
        }


def load_usage_table(usage_path: Path) -> Dict[str, TrackRecord]:
    table: Dict[str, TrackRecord] = {}
    if not usage_path.exists():
        return table
    with usage_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            record = TrackRecord.from_usage_row(row)
            if record.file_path:
                table[record.file_path] = record
    return table


def detect_duration_seconds(file_path: Path) -> Optional[float]:
    if MutagenFile is None:
        return None
    try:
        audio = MutagenFile(file_path)
        if audio is None:
            return None
        info = getattr(audio, "info", None)
        if info is None:
            return None
        duration = getattr(info, "length", None)
        if duration:
            return float(duration)
    except Exception:
        return None
    return None


def build_track_record(path: Path, existing: Optional[TrackRecord]) -> TrackRecord:
    file_path = str(path.resolve())
    file_name = path.name
    title = path.stem.replace("_", " ").replace("-", " ").strip()
    duration = detect_duration_seconds(path)
    added_at = (
        existing.added_at
        if existing and existing.added_at
        else dt.datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat()
    )
    last_used_at = existing.last_used_at if existing else ""
    times_used = existing.times_used if existing else 0
    return TrackRecord(
        file_path=file_path,
        file_name=file_name,
        title=title,
        duration_seconds=duration,
        added_at=added_at,
        last_used_at=last_used_at,
        times_used=times_used,
    )


def iter_audio_files(root: Path, extensions: Sequence[str]) -> Iterable[Path]:
    lowered = {ext.lower() for ext in extensions}
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            suffix = Path(name).suffix.lower()
            if suffix in lowered:
                yield Path(dirpath) / name


def save_table(path: Path, rows: Sequence[TrackRecord]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "file_path",
                "file_name",
                "title",
                "duration_seconds",
                "added_at",
                "last_used_at",
                "times_used",
            ],
        )
        writer.writeheader()
        for record in rows:
            writer.writerow(record.to_row())


def generate_catalog(config_path: Path) -> List[TrackRecord]:
    config = read_config(config_path)
    root = Path(os.path.expanduser(config.get("song_library_root", "")))
    if not root.exists():
        raise FileNotFoundError(f"歌库目录不存在：{root}")
    extensions = config.get("audio_extensions") or [".mp3", ".wav", ".flac", ".m4a", ".aac"]

    usage_log_path = Path(config.get("usage_log", "data/song_usage.csv"))
    catalog_path = Path(config.get("output_catalog", "data/song_library.csv"))

    usage_table = load_usage_table(usage_log_path)
    records: List[TrackRecord] = []

    for audio_file in iter_audio_files(root, extensions):
        existing = usage_table.get(str(audio_file.resolve()))
        record = build_track_record(audio_file, existing)
        records.append(record)

    records.sort(key=lambda r: r.title.lower())

    save_table(catalog_path, records)
    save_table(usage_log_path, records)
    return records


def print_summary(records: Sequence[TrackRecord]) -> None:
    total = len(records)
    duration_known = sum(1 for r in records if r.duration_seconds is not None)
    msg = f"已生成曲库总表，共 {total} 首曲目（其中 {duration_known} 首检测到时长）。"
    print(msg)


def run_watch_mode(config_path: Path, interval: float = 1.0) -> None:
    try:
        from watchdog.events import FileSystemEventHandler  # type: ignore
        from watchdog.observers import Observer  # type: ignore
    except ImportError as exc:
        raise SystemExit("缺少 watchdog 依赖，无法使用监听模式。请安装 requirements.txt 中的包。") from exc

    config = read_config(config_path)
    root = Path(os.path.expanduser(config.get("song_library_root", "")))
    if not root.exists():
        raise FileNotFoundError(f"歌库目录不存在：{root}")

    class LibraryEventHandler(FileSystemEventHandler):
        def __init__(self) -> None:
            super().__init__()
            self._last_run: float = 0.0

        def on_any_event(self, event) -> None:  # type: ignore[override]
            # 简单节流，避免短时间重复触发
            now = time.time()
            if now - self._last_run < interval:
                return
            self._last_run = now
            try:
                records = generate_catalog(config_path)
                print_summary(records)
            except Exception as err:  # noqa: BLE001
                print(f"[监听] 更新失败：{err}", file=sys.stderr)

    print(f"开始监听：{root}")
    records = generate_catalog(config_path)
    print_summary(records)

    handler = LibraryEventHandler()
    observer = Observer()
    observer.schedule(handler, str(root), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("监听停止。")
    finally:
        observer.stop()
        observer.join()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成本地曲库总表（可选监听模式）。")
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config/library_settings.yml"),
        help="配置文件路径，默认 config/library_settings.yml",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="启用监听模式，监控歌库目录变更并自动更新总表。",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    if args.watch:
        run_watch_mode(args.config)
    else:
        records = generate_catalog(args.config)
        print_summary(records)


if __name__ == "__main__":
    main()
