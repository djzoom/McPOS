#!/usr/bin/env python3
"""
Suno batch download tool (Chrome automation).

Usage:
  python -m mcpos.scripts.suno_batch_download --urls-file /path/to/urls.txt
  python -m mcpos.scripts.suno_batch_download --url https://suno.com/song/xxxx
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mcpos.adapters.suno_downloader_adapter import (
    ChromeSunoDownloader,
    DownloadResult,
    SunoDownloadConfig,
)
from mcpos.core.logging import log_info, log_warning, log_error


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch download Suno tracks via Chrome."
    )
    parser.add_argument(
        "--url",
        dest="urls",
        action="append",
        default=[],
        help="Suno track URL (repeatable).",
    )
    parser.add_argument(
        "--urls-file",
        type=Path,
        help="Text/CSV file with Suno URLs (one per line, or comma/space separated).",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=Path("~/Downloads/suno_batch").expanduser(),
        help="Download directory (default: ~/Downloads/suno_batch).",
    )
    parser.add_argument(
        "--chrome-path",
        type=Path,
        help="Chrome executable path (optional).",
    )
    parser.add_argument(
        "--user-data-dir",
        type=Path,
        help="Chrome user data dir (optional, for persistent login).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome headless (downloads may not work on all setups).",
    )
    parser.add_argument(
        "--format",
        dest="format_preference",
        choices=["any", "mp3", "wav"],
        default="any",
        help="Preferred download format (default: any).",
    )
    parser.add_argument(
        "--manual-on-fail",
        action="store_true",
        help="If auto-click fails, pause for manual download.",
    )
    parser.add_argument(
        "--login-first",
        action="store_true",
        help="Open Suno login page first and wait for user confirmation.",
    )
    parser.add_argument(
        "--login-url",
        default="https://suno.com",
        help="Login page URL (default: https://suno.com).",
    )
    parser.add_argument(
        "--max",
        type=int,
        help="Limit number of URLs to process.",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Keep Chrome open after downloads until Enter is pressed.",
    )
    return parser.parse_args()


def _extract_urls_from_text(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s,]+", text)
    cleaned = []
    for url in urls:
        cleaned.append(url.strip().strip(")\"'[]"))
    return cleaned


def _load_urls(args: argparse.Namespace) -> list[str]:
    urls: list[str] = list(args.urls or [])
    if args.urls_file:
        if not args.urls_file.exists():
            log_error(f"URLs file not found: {args.urls_file}")
            return []
        content = args.urls_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            urls.extend(_extract_urls_from_text(line))

    # De-duplicate while preserving order
    seen = set()
    ordered = []
    for url in urls:
        if url not in seen:
            ordered.append(url)
            seen.add(url)

    if args.max is not None:
        ordered = ordered[: args.max]
    return ordered


def _manual_download(
    downloader: ChromeSunoDownloader,
    url: str,
) -> DownloadResult:
    log_warning(f"Manual download requested for: {url}")
    downloader.open_url(url)
    existing = downloader.snapshot_download_dir()
    input("Click the download button in Chrome, then press Enter to continue...")
    downloaded = downloader.wait_for_new_download(existing)
    if downloaded:
        return DownloadResult(url=url, success=True, file_path=downloaded)
    return DownloadResult(url=url, success=False, error="manual download timeout")


def main() -> int:
    args = _parse_args()
    urls = _load_urls(args)
    if not urls:
        log_error("No URLs provided. Use --url or --urls-file.")
        return 1

    config = SunoDownloadConfig(
        download_dir=args.download_dir.expanduser().resolve(),
        chrome_path=args.chrome_path,
        user_data_dir=args.user_data_dir,
        headless=args.headless,
        format_preference=args.format_preference,
    )

    downloader = ChromeSunoDownloader(config)
    results: list[DownloadResult] = []
    try:
        if args.login_first:
            downloader.open_url(args.login_url)
            input("Log in to Suno in Chrome, then press Enter to continue...")

        total = len(urls)
        for idx, url in enumerate(urls, start=1):
            log_info(f"[{idx}/{total}] Downloading: {url}")
            result = downloader.download_url(url)
            if not result.success and args.manual_on_fail:
                result = _manual_download(downloader, url)
            results.append(result)
    finally:
        if args.keep_open:
            input("Downloads finished. Press Enter to close Chrome...")
        downloader.close()

    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count
    log_info(f"Finished. Success: {success_count}, Failed: {fail_count}")
    for result in results:
        if not result.success:
            log_warning(f"Failed: {result.url} ({result.error})")
    return 0 if fail_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
