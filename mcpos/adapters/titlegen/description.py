from __future__ import annotations

import re
from typing import Any, Optional

from .openai_api import _openai_chat_sync
from .budget import EpisodeBudget


def _format_timecode(seconds: float) -> str:
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        total = 0

    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _build_tracklist_text(
    tracks_a: list[dict[str, Any]],
    tracks_b: list[dict[str, Any]],
    clean_timeline: list[dict[str, Any]] | None,
) -> str:
    clean_timeline = clean_timeline or []

    if clean_timeline:
        lines: list[str] = []
        for i, item in enumerate(clean_timeline):
            if "timecode" in item and isinstance(item["timecode"], str):
                tc = item["timecode"]
            else:
                start_val = (
                    item.get("start_seconds")
                    or item.get("time_seconds")
                    or item.get("start")
                    or 0
                )
                tc = _format_timecode(start_val)

            title = (
                item.get("title")
                or item.get("track_title")
                or item.get("name")
                or f"Track {i + 1}"
            )

            side_raw = str(item.get("side") or item.get("side_label") or "").strip().upper()
            if side_raw in {"A", "SIDE A"}:
                side_label = "Side A: "
            elif side_raw in {"B", "SIDE B"}:
                side_label = "Side B: "
            else:
                if i == 0:
                    side_label = "Side A: "
                elif i == len(clean_timeline) - len(tracks_b):
                    side_label = "Side B: "
                else:
                    side_label = ""

            lines.append(f"{tc}  —  {side_label}{title}")
        return "\n".join(lines)

    current_time_sec = 0
    lines = []
    for i, track in enumerate(tracks_a + tracks_b):
        tc = _format_timecode(current_time_sec)
        if i == 0:
            side_label = "Side A: "
        elif i == len(tracks_a):
            side_label = "Side B: "
        else:
            side_label = ""
        title = track.get("title", f"Track {i + 1}")
        lines.append(f"{tc}  —  {side_label}{title}")
        current_time_sec += int(track.get("duration_seconds", 180) or 180)
    return "\n".join(lines)


def _clean_youtube_description(description: str) -> str:
    if not description:
        return description

    cleaned = description

    cleaned = re.sub(r"[-=]{10,}", "", cleaned)
    cleaned = re.sub(r"_{10,}", "", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = cleaned.replace("**", "")
    cleaned = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", cleaned)

    cleaned = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", "", cleaned)

    lines = cleaned.splitlines()
    filtered = []
    for line in lines:
        if re.search(r"tracklist|timecode", line, re.IGNORECASE):
            continue
        filtered.append(line)
    cleaned = "\n".join(filtered)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _build_description_prompt(
    album_title: str,
    tracks_a: list[dict[str, Any]],
    tracks_b: list[dict[str, Any]],
    track_list_text: str,
    tracklist_text: str,
) -> str:
    total_tracks = len(tracks_a) + len(tracks_b)
    timeline_overview = ""
    if tracklist_text:
        timeline_overview = (
            "\nTimeline overview for your reference only (do NOT include this section or any timecodes in your response. "
            "The tracklist will be added automatically by the system):\n\n"
            f"{tracklist_text}\n"
        )

    return (
        "You are a music label copywriter for Kat Records.\n"
        f"Album Title: {album_title}\n"
        f"Total Tracks: {total_tracks} ({len(tracks_a)} on Side A, {len(tracks_b)} on Side B)\n"
        "Track List (titles only, no timecodes):\n"
        f"{track_list_text}\n"
        f"{timeline_overview}\n"
        "Writing rules:\n"
        "- 2 to 3 short paragraphs, English only\n"
        "- Calm, concise, and cinematic\n"
        "- Do NOT include timecodes or tracklist\n"
        "- No bullet points or numbered lists\n"
        "Return only the prose."
    ).strip()


def _fallback_description(album_title: str, total_tracks: int) -> str:
    return (
        f"{album_title} is a late-night vinyl session built for steady focus and calm. "
        f"{total_tracks} tracks drift across two sides with soft textures and unhurried motion.\n\n"
        "Let it play in the background for study, coding, reading, or quiet work."
    )


def _generate_description_sync(
    album_title: str,
    tracks_a: list[dict[str, Any]],
    tracks_b: list[dict[str, Any]],
    tracklist_text: str,
    api_key: str,
    api_base: Optional[str],
    model: Optional[str],
    budget: EpisodeBudget,
    openai_available: bool,
    openai_class,
    timeout: int,
    max_tokens: int,
    temperature: float,
) -> str:
    budget.consume("description")
    track_list_text = "\n".join(
        f"- {t.get('title', f'Track {i+1}') }" for i, t in enumerate(tracks_a + tracks_b)
    )
    prompt = _build_description_prompt(
        album_title=album_title,
        tracks_a=tracks_a,
        tracks_b=tracks_b,
        track_list_text=track_list_text,
        tracklist_text=tracklist_text,
    )

    system_prompt = "You write album liner notes for vinyl releases."
    return _openai_chat_sync(
        api_key=api_key,
        api_base=api_base,
        model=model,
        system_prompt=system_prompt,
        user_prompt=prompt,
        timeout=timeout,
        max_tokens=max_tokens,
        temperature=temperature,
        openai_available=openai_available,
        openai_class=openai_class,
    )
