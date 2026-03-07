"""VO script generation with channel profiles and legacy asset reuse."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .models import VOChannelProfile, VOConfig, VOScriptBundle, VOSegmentKind
from .ssml import excerpt_text, paragraphs_to_ssml, strip_ssml
from ..core.logging import log_info
from ..models import EpisodeSpec, AssetPaths, Track


def _read_primary_existing_text(asset_dir: Optional[Path]) -> Optional[str]:
    if not asset_dir or not asset_dir.exists():
        return None
    txt_files = sorted(asset_dir.glob("*.txt"))
    if not txt_files:
        return None
    return txt_files[0].read_text(encoding="utf-8").strip()


def _build_context(spec: EpisodeSpec, base_text: dict[str, Any], tracks: list[Track]) -> dict[str, Any]:
    title = (base_text.get("title") or spec.episode_id or "this session").strip()
    description = (base_text.get("description") or "").strip()
    description_excerpt = excerpt_text(description, max_words=60) if description else ""
    total_duration_min = spec.target_duration_min or spec.duration_minutes or int(sum(t.duration_sec for t in tracks) // 60) or 180
    return {
        "title": title,
        "description": description,
        "description_excerpt": description_excerpt or "Let the music become a quiet place to rest.",
        "track_count": len(tracks),
        "duration_hours": round(total_duration_min / 60.0, 1),
        "episode_id": spec.episode_id,
    }


def _generate_segment_text(profile: VOChannelProfile, context: dict[str, Any], kind: VOSegmentKind) -> str:
    if kind == VOSegmentKind.INTRO:
        return profile.intro_template.format(**context)
    if kind == VOSegmentKind.OUTRO:
        return profile.outro_template.format(**context)
    return profile.full_template.format(**context)


def _derive_texts_from_existing_text(existing_text: str, vo_config: VOConfig) -> dict[VOSegmentKind, str]:
    plain_text = strip_ssml(existing_text)
    intro_words = max(50, int(vo_config.legacy_intro_max_sec * 2.5))
    outro_words = max(35, int(vo_config.legacy_outro_max_sec * 2.5))
    return {
        VOSegmentKind.FULL: existing_text.strip(),
        VOSegmentKind.INTRO: excerpt_text(plain_text, max_words=intro_words),
        VOSegmentKind.OUTRO: excerpt_text(plain_text, from_end=True, max_words=outro_words),
    }


def _sectioned_txt(intro_text: Optional[str], outro_text: Optional[str], full_text: Optional[str]) -> str:
    sections: list[str] = []
    if intro_text:
        sections.append("[intro]\n" + intro_text.strip())
    if outro_text:
        sections.append("[outro]\n" + outro_text.strip())
    if full_text:
        sections.append("[full]\n" + full_text.strip())
    return "\n\n".join(sections).strip() + "\n"


def _sectioned_ssml(intro_ssml: Optional[str], outro_ssml: Optional[str], full_ssml: Optional[str]) -> str:
    sections: list[str] = []
    if intro_ssml:
        sections.append("[intro]\n" + intro_ssml.strip())
    if outro_ssml:
        sections.append("[outro]\n" + outro_ssml.strip())
    if full_ssml:
        sections.append("[full]\n" + full_ssml.strip())
    return "\n\n".join(sections).strip() + "\n"


def resolve_or_generate_vo_script(
    spec: EpisodeSpec,
    paths: AssetPaths,
    base_text: dict[str, Any],
    vo_config: VOConfig,
    channel_profile: VOChannelProfile,
    *,
    tracks: Optional[list[Track]] = None,
) -> VOScriptBundle:
    """Resolve legacy text when available, otherwise generate channel-aligned VO scripts."""

    tracks = tracks or []
    paths.vo_script_txt.parent.mkdir(parents=True, exist_ok=True)

    existing_text = _read_primary_existing_text(vo_config.existing_asset_dir) if vo_config.existing_asset_prefer else None
    context = _build_context(spec, base_text, tracks)

    intro_text: Optional[str] = None
    outro_text: Optional[str] = None
    full_text: Optional[str] = None
    source_map: dict[str, str] = {}

    if existing_text:
        derived = _derive_texts_from_existing_text(existing_text, vo_config)
        full_text = derived[VOSegmentKind.FULL]
        if vo_config.intro_enabled:
            intro_text = derived[VOSegmentKind.INTRO]
            source_map[VOSegmentKind.INTRO.value] = "existing_text_excerpt"
        if vo_config.outro_enabled:
            outro_text = derived[VOSegmentKind.OUTRO]
            source_map[VOSegmentKind.OUTRO.value] = "existing_text_excerpt"
        source_map[VOSegmentKind.FULL.value] = "existing_text"
    else:
        full_text = _generate_segment_text(channel_profile, context, VOSegmentKind.FULL)
        source_map[VOSegmentKind.FULL.value] = "generated"
        if vo_config.intro_enabled:
            intro_text = _generate_segment_text(channel_profile, context, VOSegmentKind.INTRO)
            source_map[VOSegmentKind.INTRO.value] = "generated"
        if vo_config.outro_enabled:
            outro_text = _generate_segment_text(channel_profile, context, VOSegmentKind.OUTRO)
            source_map[VOSegmentKind.OUTRO.value] = "generated"

    intro_ssml = paragraphs_to_ssml(intro_text.split(". "), break_sec=2.5) if intro_text else None
    outro_ssml = paragraphs_to_ssml(outro_text.split(". "), break_sec=2.5) if outro_text else None
    full_ssml = paragraphs_to_ssml(strip_ssml(full_text).split(". "), break_sec=2.5) if full_text else None

    paths.vo_script_txt.write_text(_sectioned_txt(intro_text, outro_text, full_text), encoding="utf-8")
    paths.vo_script_ssml.write_text(_sectioned_ssml(intro_ssml, outro_ssml, full_ssml), encoding="utf-8")
    meta = {
        "channel_profile": channel_profile.profile_id,
        "language": vo_config.language,
        "source_map": source_map,
        "title": context["title"],
        "track_count": len(tracks),
        "tone_profile": channel_profile.tone_profile,
        "pacing_profile": channel_profile.pacing_profile,
    }
    paths.vo_script_meta_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    log_info(f"[vo/script] Wrote VO script bundle for {spec.episode_id}")

    return VOScriptBundle(
        txt_path=paths.vo_script_txt,
        ssml_path=paths.vo_script_ssml,
        meta_path=paths.vo_script_meta_json,
        intro_text=intro_text,
        outro_text=outro_text,
        full_text=full_text,
        intro_ssml=intro_ssml,
        outro_ssml=outro_ssml,
        full_ssml=full_ssml,
        metadata=meta,
    )
