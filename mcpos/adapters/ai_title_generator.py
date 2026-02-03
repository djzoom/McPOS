# coding: utf-8
"""
AI Title Generator (Refactored)

- Deterministic cost (no retry loops)
- Album title uses content words from cover image filename
- YouTube subtitle from fixed pool (no model call)
- YouTube title assembled deterministically with quotes
- Optional single-shot AI description
"""
from __future__ import annotations

from typing import Any, Optional

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False
    OpenAI = None  # type: ignore

from .titlegen.budget import EpisodeBudget
from .titlegen.service import (
    generate_album_title as _generate_album_title_service,
    generate_youtube_title_and_description as _generate_youtube_title_and_description_service,
)

DEFAULT_MODEL = "gpt-4o-mini"

TITLE_GENERATION_CONFIG = {
    "album_title": {
        "max_tokens": 32,
        "temperature": 0.9,
        "timeout": 30,
    },
    "description": {
        "max_tokens": 700,
        "temperature": 0.8,
        "timeout": 45,
    },
}

MAX_ALBUM_TITLE_BYTES = 60
MAX_YT_TITLE_CHARS = 100
MAX_YT_TITLE_BYTES = 120

DEFAULT_HASHTAGS = [
    "#KatRecords",
    "#vibecoding",
    "#vinylsession",
    "#jazzambient",
    "#nightmusic",
    "#cityrain",
    "#chillinstrumental",
    "#sounddiary",
    "#creativefocus",
    "#analogdreams",
    "#sleepmusic",
    "#studybeats",
    "#lofisoul",
    "#nightdrive",
    "#cozyvibes",
]


async def generate_album_title(
    track_titles: list[str],
    image_filename: str,
    theme_color_rgb: tuple[int, int, int],
    episode_date: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    model: str | None = None,
    channel_id: str = "kat",
    budget: EpisodeBudget | None = None,
    seed_salt: str | None = None,
) -> str:
    return await _generate_album_title_service(
        track_titles=track_titles,
        image_filename=image_filename,
        theme_color_rgb=theme_color_rgb,
        episode_date=episode_date,
        api_key=api_key,
        api_base=api_base,
        model=model or DEFAULT_MODEL,
        channel_id=channel_id,
        budget=budget,
        seed_salt=seed_salt,
        openai_available=OPENAI_AVAILABLE,
        openai_class=OpenAI,
        title_cfg=TITLE_GENERATION_CONFIG["album_title"],
        max_album_title_bytes=MAX_ALBUM_TITLE_BYTES,
    )


async def generate_youtube_title_and_description(
    album_title: str,
    playlist_data: dict[str, Any],
    api_key: str | None = None,
    api_base: str | None = None,
    model: str | None = None,
    channel_id: str = "kat",
    budget: EpisodeBudget | None = None,
) -> tuple[str, str]:
    return await _generate_youtube_title_and_description_service(
        album_title=album_title,
        playlist_data=playlist_data,
        api_key=api_key,
        api_base=api_base,
        model=model or DEFAULT_MODEL,
        channel_id=channel_id,
        budget=budget,
        openai_available=OPENAI_AVAILABLE,
        openai_class=OpenAI,
        max_title_chars=MAX_YT_TITLE_CHARS,
        max_title_bytes=MAX_YT_TITLE_BYTES,
        description_cfg=TITLE_GENERATION_CONFIG["description"],
        default_hashtags=DEFAULT_HASHTAGS,
    )
