"""
mcpos/text/generator.py — YouTube metadata generation via Claude API

Generates title, description, and tags for each episode.
Uses claude-sonnet-4-6 by default; falls back to Jinja2 templates if unavailable.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import EpisodeSpec, AssetPaths, StageResult, StageName, Track
from ..core.logging import log_info, log_warning, log_error


# ---------------------------------------------------------------------------
# Per-channel prompt templates
# ---------------------------------------------------------------------------

_PROMPTS: dict[str, str] = {
    "kat": (
        "You are a copywriter for Kat Records Studio, a lo-fi music YouTube channel "
        "(150K+ subscribers, 24M+ views, @KatRecordsStudio).\n\n"
        "Episode details:\n"
        "- Date: {date}\n"
        "- Track count: {track_count}\n"
        "- Duration: {duration_min} minutes\n"
        "- Sample tracks: {sample_tracks}\n\n"
        "Write a YouTube video title, description, and tags.\n\n"
        "Rules:\n"
        "- Title: max 70 chars, evocative, cozy lo-fi vibe. "
        "Examples: \"Late Night Study Session ☕ Lo-Fi Jazz Hop • 3 Hours\", "
        "\"Rainy Afternoon Chill 🌧 Lo-Fi Beats • 3 Hours\"\n"
        "- Description: 3–4 paragraphs. Open with mood/vibe. Include tracklist. "
        "Close with subscribe CTA.\n"
        "- Tags: 15–20 relevant tags (lofi, study music, chill beats, etc.)\n\n"
        "Output ONLY valid JSON:\n"
        '{"title": "...", "description": "...", "tags": ["tag1", "tag2", ...]}'
    ),
    "rbr": (
        "You are a copywriter for Run Baby Run, a running music YouTube channel.\n\n"
        "Episode details:\n"
        "- Date: {date}\n"
        "- BPM: {bpm}\n"
        "- Duration: {duration_min} minutes\n"
        "- Sample tracks: {sample_tracks}\n\n"
        "Write a YouTube video title, description, and tags for a running music mix.\n\n"
        "Rules:\n"
        "- Title: max 70 chars, energetic, include BPM. "
        "Example: \"5K Pace Run 🏃 {bpm} BPM Running Music • {duration_min} Min\"\n"
        "- Description: Open with pace/workout context. Include BPM info. Partial tracklist. CTA.\n"
        "- Tags: 15–20 tags (running music, workout, BPM, motivation, etc.)\n\n"
        "Output ONLY valid JSON:\n"
        '{"title": "...", "description": "...", "tags": ["tag1", "tag2", ...]}'
    ),
    "sg": (
        "You are a copywriter for Sleep in Grace, a healing and ambient sleep music YouTube channel.\n\n"
        "Episode details:\n"
        "- Date: {date}\n"
        "- Track count: {track_count}\n"
        "- Duration: {duration_min} minutes\n"
        "- Sample tracks: {sample_tracks}\n\n"
        "Write a YouTube video title, description, and tags.\n\n"
        "Rules:\n"
        "- Title: max 70 chars, peaceful healing vibe. "
        "Example: \"Deep Sleep Music 🌙 Healing Ambient • 6 Hours\"\n"
        "- Description: Warm, spiritual tone. Use cases: sleep, meditation, prayer. CTA.\n"
        "- Tags: 15–20 tags (sleep music, healing, ambient, meditation, prayer music, etc.)\n\n"
        "Output ONLY valid JSON:\n"
        '{"title": "...", "description": "...", "tags": ["tag1", "tag2", ...]}'
    ),
}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _get_anthropic_key() -> Optional[str]:
    """Get Anthropic API key from env or config file."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        return key
    config_file = Path(__file__).parent.parent.parent / "config" / "anthropic_api_key.txt"
    if config_file.exists():
        key = config_file.read_text(encoding="utf-8").strip()
        if key:
            return key
    return None


def _call_claude(prompt: str, model: str = "claude-sonnet-4-6") -> Optional[str]:
    """
    Call Claude API synchronously. Returns response text, or None on failure.
    """
    api_key = _get_anthropic_key()
    if not api_key:
        log_warning("[text] ANTHROPIC_API_KEY not configured; using template fallback")
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except ImportError:
        log_warning("[text] anthropic package not installed; pip install anthropic")
        return None
    except Exception as e:
        log_error(f"[text] Claude API error: {e}")
        return None


def _parse_json_response(response: str) -> Optional[dict]:
    """Extract JSON from Claude response (handles markdown code fences)."""
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Skip opening fence and closing fence
        inner = [l for l in lines[1:] if not l.startswith("```")]
        text = "\n".join(inner).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Fallback templates
# ---------------------------------------------------------------------------

def _fallback_title(spec: EpisodeSpec) -> str:
    dur = spec.target_duration_min or spec.duration_minutes or 180
    hours = dur // 60
    mins = dur % 60
    dur_str = f"{hours}h {mins}min" if mins else f"{hours}h"
    labels = {
        "kat": f"Lo-Fi Chill Beats • {dur_str}",
        "rbr": f"Running Music {spec.target_bpm or ''}BPM • {dur_str}".strip(),
        "sg": f"Healing Ambient Sleep Music • {dur_str}",
    }
    label = labels.get(spec.channel_id, f"Music Mix • {dur_str}")
    return f"{label} | {spec.date or spec.episode_id}"[:70]


def _fallback_description(spec: EpisodeSpec, tracks: list[Track]) -> str:
    lines = [f"Episode: {spec.episode_id}", ""]
    if tracks:
        lines.append("Tracklist:")
        for i, t in enumerate(tracks[:30], 1):
            lines.append(f"{i:02d}. {t.title}")
    lines += ["", "Subscribe for daily music. 🎵"]
    return "\n".join(lines)


def _fallback_tags(spec: EpisodeSpec) -> list[str]:
    defaults: dict[str, list[str]] = {
        "kat": ["lofi", "lo-fi", "study music", "chill beats", "jazz hop", "focus music",
                "lofi hip hop", "background music", "work music", "coffee shop music",
                "relax music", "lofi chill", "kat records"],
        "rbr": ["running music", "workout music", "gym music", "motivation", "cardio",
                "jogging music", "running playlist", "exercise music", "pace music",
                f"{spec.target_bpm}bpm" if spec.target_bpm else "bpm music"],
        "sg": ["sleep music", "healing music", "ambient music", "meditation music",
               "relaxing music", "prayer music", "calm music", "deep sleep",
               "sleep sounds", "healing frequencies", "peaceful music"],
    }
    return defaults.get(spec.channel_id, ["music", "ambient", "relaxing"])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_episode_text(
    spec: EpisodeSpec,
    paths: AssetPaths,
    tracks: list[Track],
) -> StageResult:
    """
    Generate title, description, and tags for a YouTube episode.

    Writes:
      paths.youtube_title_txt
      paths.youtube_description_txt
      paths.youtube_tags_txt

    Uses Claude API if configured; otherwise uses template fallback.
    """
    started_at = datetime.now()

    # Idempotency: skip if all three files exist
    if (paths.youtube_title_txt.exists()
            and paths.youtube_description_txt.exists()
            and paths.youtube_tags_txt.exists()):
        log_info(f"[text] Text assets already exist for {spec.episode_id}")
        return StageResult(
            stage=StageName.TEXT_BASE, success=True,
            duration_seconds=0.0,
            key_asset_paths=[
                paths.youtube_title_txt,
                paths.youtube_description_txt,
                paths.youtube_tags_txt,
            ],
            started_at=started_at, finished_at=datetime.now(),
        )

    # Build prompt
    sample_tracks = ", ".join(t.title for t in tracks[:5]) if tracks else "Various tracks"
    dur_min = spec.target_duration_min or spec.duration_minutes or 180
    prompt_template = _PROMPTS.get(spec.channel_id, _PROMPTS["kat"])
    prompt = prompt_template.format(
        date=spec.date or spec.episode_id,
        track_count=len(tracks),
        duration_min=dur_min,
        sample_tracks=sample_tracks,
        bpm=spec.target_bpm or "N/A",
    )

    # Attempt Claude API
    title = description = None
    tags: list[str] = []

    response = _call_claude(prompt)
    if response:
        data = _parse_json_response(response)
        if data:
            title = str(data.get("title", "")).strip() or None
            description = str(data.get("description", "")).strip() or None
            tags = [str(t).strip() for t in data.get("tags", []) if t]
            log_info(f"[text] Claude generated text for {spec.episode_id}")
        else:
            log_warning(f"[text] Failed to parse Claude JSON for {spec.episode_id}")

    # Apply fallbacks
    if not title:
        title = _fallback_title(spec)
    if not description:
        description = _fallback_description(spec, tracks)
    if not tags:
        tags = _fallback_tags(spec)

    # Write files
    try:
        paths.youtube_title_txt.parent.mkdir(parents=True, exist_ok=True)
        paths.youtube_title_txt.write_text(title, encoding="utf-8")
        paths.youtube_description_txt.write_text(description, encoding="utf-8")
        paths.youtube_tags_txt.write_text("\n".join(tags), encoding="utf-8")

        finished_at = datetime.now()
        log_info(f"[text] Wrote text assets for {spec.episode_id}: '{title[:50]}'")
        return StageResult(
            stage=StageName.TEXT_BASE, success=True,
            duration_seconds=(finished_at - started_at).total_seconds(),
            key_asset_paths=[
                paths.youtube_title_txt,
                paths.youtube_description_txt,
                paths.youtube_tags_txt,
            ],
            started_at=started_at, finished_at=finished_at,
        )
    except Exception as e:
        log_error(f"[text] Failed to write text assets: {e}")
        return StageResult(
            stage=StageName.TEXT_BASE, success=False,
            duration_seconds=0.0, key_asset_paths=[],
            error_message=str(e),
            started_at=started_at, finished_at=datetime.now(),
        )
