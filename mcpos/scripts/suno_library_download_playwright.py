#!/usr/bin/env python3
"""
Download all tracks from Suno Library using Playwright + Chrome.

Usage:
  python -m mcpos.scripts.suno_library_download_playwright \
    --download-dir /absolute/path/to/downloads \
    --user-data-dir /absolute/path/to/chrome_profile \
    --login-first
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mcpos.adapters.suno_downloader_playwright_adapter import (
    SunoLibraryDownloadConfig,
    SunoPlaywrightDownloader,
)
from mcpos.core.logging import log_info, log_warning, log_error


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download all tracks from Suno Library using Playwright."
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=Path("~/Downloads/suno_library").expanduser(),
        help="Download directory (default: ~/Downloads/suno_library).",
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
        "--login-first",
        action="store_true",
        help="Open login page first and wait for user confirmation.",
    )
    parser.add_argument(
        "--login-url",
        default="https://suno.com",
        help="Login page URL (default: https://suno.com).",
    )
    parser.add_argument(
        "--library-url",
        default="https://suno.com/library",
        help="Library page URL (default: https://suno.com/library).",
    )
    parser.add_argument(
        "--format",
        dest="format_preference",
        choices=["any", "mp3", "wav"],
        default="any",
        help="Preferred download format (default: any).",
    )
    parser.add_argument(
        "--max",
        type=int,
        help="Limit number of tracks to download.",
    )
    parser.add_argument(
        "--manual-on-fail",
        action="store_true",
        help="If auto-click fails, pause for manual download.",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Keep Chrome open after downloads until Enter is pressed.",
    )
    parser.add_argument(
        "--channel",
        default="chrome",
        help="Playwright browser channel (default: chrome).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = SunoLibraryDownloadConfig(
        download_dir=args.download_dir.expanduser().resolve(),
        library_url=args.library_url,
        login_url=args.login_url,
        user_data_dir=args.user_data_dir,
        headless=args.headless,
        channel=args.channel,
        format_preference=args.format_preference,
    )

    downloader = SunoPlaywrightDownloader(config)
    results = []
    try:
        if args.login_first:
            downloader.open_url(config.login_url)
            input("Log in to Suno in Chrome, then press Enter to continue...")

        urls = downloader.collect_library_song_urls(max_tracks=args.max)
        if not urls:
            log_error("No song links found in library.")
            return 1

        total = len(urls)
        for idx, url in enumerate(urls, start=1):
            log_info(f"[{idx}/{total}] Downloading: {url}")
            result = downloader.download_song_url(url)
            if not result.success and args.manual_on_fail:
                log_warning(f"Auto download failed: {url} ({result.error})")

                def manual_action():
                    input("Click Download in Chrome, then press Enter...")

                result = downloader.download_song_url(url, manual_action=manual_action)
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
