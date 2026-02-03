from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from collections import deque
from pathlib import Path
from typing import Any, Optional

from ...core.logging import log_info, log_warning
from .budget import BudgetExceeded, EpisodeBudget, ensure_budget
from .tokens import (
    extract_content_tokens,
    clean_tokens,
    perturb_tokens,
    build_album_title_prompt_from_tokens,
)
from .validate import (
    validate_album_title_physical,
    _titlecase_clean,
    _is_too_similar,
    extract_core_words,
)
from .fallback import (
    fallback_album_title,
    set_fallback_cooldown,
    set_fallback_hints,
    MATERIAL_WORDS,
    PLACE_WORDS,
    ATMOS_WORDS,
    OBJECT_WORDS,
)
from .youtube import _build_youtube_title
from .description import (
    _build_tracklist_text,
    _clean_youtube_description,
    _fallback_description,
    _generate_description_sync,
)
from .openai_api import _openai_chat_sync


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    try:
        r, g, b = rgb
        return f"#{int(r):02X}{int(g):02X}{int(b):02X}"
    except Exception:
        return "#000000"


def _season_hint_from_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    m = re.search(r"(20\d{2})[-_/]?(\d{2})[-_/]?(\d{2})", date_str)
    if not m:
        return None
    month = int(m.group(2))
    if month in {12, 1, 2}:
        return "Winter"
    if month in {3, 4, 5}:
        return "Spring"
    if month in {6, 7, 8}:
        return "Summer"
    return "Autumn"


def _load_historical_titles() -> list[str]:
    """
    Load historical album titles if available (for similarity scoring only).
    """
    path = _repo_root() / "mcpos" / "data" / "historical_titles.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        titles = payload.get("album_titles") or []
        if isinstance(titles, list):
            return [str(t) for t in titles if str(t).strip()]
    except Exception:
        return []
    return []


def _normalize_date_key(date_str: str | None) -> str:
    if not date_str:
        return "00000000"
    m = re.search(r"(20\d{2})[-_/]?(\d{2})[-_/]?(\d{2})", date_str)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"
    return date_str


def _load_recent_album_titles_from_outputs(channel_id: str, limit: int = 30) -> list[str]:
    """
    Load recent album titles from episode recipe.json outputs.
    """
    output_root = _repo_root() / "channels" / channel_id / "output"
    archived_root = output_root / "Archived"

    recipe_paths: set[Path] = set()
    for root in [output_root, archived_root]:
        if root.exists():
            for recipe_path in root.rglob("recipe.json"):
                recipe_paths.add(recipe_path)

    entries: list[tuple[str, str]] = []
    for recipe_path in recipe_paths:
        try:
            payload = json.loads(recipe_path.read_text(encoding="utf-8"))
            date_str = payload.get("schedule_date") or payload.get("date") or None
            title = payload.get("album_title") or None
        except Exception:
            date_str = None
            title = None

        if not date_str:
            m = re.search(r"(20\d{6})", recipe_path.parent.name)
            date_str = m.group(1) if m else "00000000"
        if title:
            entries.append((_normalize_date_key(str(date_str)), str(title)))

    entries.sort(key=lambda x: x[0])
    return [t for _, t in entries[-limit:]]


_M_SET = {w.lower() for w in MATERIAL_WORDS}
_P_SET = {w.lower() for w in PLACE_WORDS}
_A_SET = {w.lower() for w in ATMOS_WORDS}
_O_SET = {w.lower() for w in OBJECT_WORDS}


def _infer_roles_sequence(title: str) -> list[str]:
    words = re.findall(r"[A-Za-z]+", title)
    roles: list[str] = []
    for w in words:
        lw = w.lower()
        if lw in {"lp", "vinyl"}:
            continue
        if lw in {"in", "on", "under", "at", "by", "from", "through", "along", "near"}:
            continue
        if lw in _M_SET:
            roles.append("M")
        elif lw in _P_SET:
            roles.append("P")
        elif lw in _A_SET:
            roles.append("A")
        elif lw in _O_SET:
            roles.append("O")
    return roles


def _infer_structure_and_leading_role(title: str) -> tuple[str, str]:
    roles = _infer_roles_sequence(title)
    if not roles:
        return "UNKNOWN", "UNKNOWN"
    structure = " ".join(roles)
    return structure, roles[0]


@dataclass
class _RecentCache:
    initialized: bool = False
    recent_titles: deque[str] = field(default_factory=lambda: deque(maxlen=7))
    recent_structures: deque[str] = field(default_factory=lambda: deque(maxlen=7))
    recent_roles: deque[str] = field(default_factory=lambda: deque(maxlen=7))
    recent_core_words: deque[list[str]] = field(default_factory=lambda: deque(maxlen=20))

    def cooldown_set(self) -> set[str]:
        out: set[str] = set()
        for ws in self.recent_core_words:
            out.update(ws)
        return out

    def cooldown_last7_set(self) -> set[str]:
        out: set[str] = set()
        # take last 7 from core_words deque tail
        tail = list(self.recent_core_words)[-7:]
        for ws in tail:
            out.update(ws)
        return out


_CACHE_BY_CHANNEL: dict[str, _RecentCache] = {}
_HISTORICAL_TITLES: list[str] | None = None


def _get_cache(channel_id: str) -> _RecentCache:
    cache = _CACHE_BY_CHANNEL.get(channel_id)
    if cache is None:
        cache = _RecentCache()
        _CACHE_BY_CHANNEL[channel_id] = cache

    if not cache.initialized:
        # Bootstrap from existing outputs so diversity survives process restarts.
        titles = _load_recent_album_titles_from_outputs(channel_id, limit=30)
        for t in titles[-20:]:
            cache.recent_core_words.append(extract_core_words(t))
        for t in titles[-7:]:
            cache.recent_titles.append(t)
            s, r = _infer_structure_and_leading_role(t)
            cache.recent_structures.append(s)
            cache.recent_roles.append(r)
        cache.initialized = True

    return cache


def _ensure_historical_titles_loaded() -> list[str]:
    global _HISTORICAL_TITLES
    if _HISTORICAL_TITLES is None:
        _HISTORICAL_TITLES = _load_historical_titles()
    return _HISTORICAL_TITLES


def _apply_recent_penalty_once(
    title: str,
    cache: _RecentCache,
    tokens: list[str],
    seed: str,
    max_album_title_bytes: int,
) -> str:
    """
    Zero-API safety valve: if the title exactly matches a recent one, rebuild once via fallback.
    """
    recent_lower = {t.strip().lower() for t in cache.recent_titles}
    if title.strip().lower() not in recent_lower:
        return title

    log_warning("Album title matches a recent title; applying one-shot dedup fallback.")
    set_fallback_cooldown(cache.cooldown_set(), cache.cooldown_last7_set())
    set_fallback_hints(list(cache.recent_structures), list(cache.recent_roles))
    alt = fallback_album_title(tokens=tokens, seed=seed + "|dedup", min_words=3, max_words=7)
    ok, reason = validate_album_title_physical(alt, min_words=3, max_words=7, max_bytes=max_album_title_bytes)
    if not ok:
        log_warning(f"One-shot dedup fallback failed validation ({reason}); keeping original title.")
        return title
    return alt


def _finalize_and_cache_title(channel_id: str, cache: _RecentCache, title: str) -> None:
    cache.recent_titles.append(title)
    structure, role = _infer_structure_and_leading_role(title)
    cache.recent_structures.append(structure)
    cache.recent_roles.append(role)
    cache.recent_core_words.append(extract_core_words(title))


def _strict_ai_enabled(api_key: str | None) -> bool:
    return bool(api_key and str(api_key).strip())


async def generate_album_title(
    track_titles: list[str],
    image_filename: str,
    theme_color_rgb: tuple[int, int, int],
    episode_date: str | None,
    api_key: str | None,
    api_base: str | None,
    model: str | None,
    channel_id: str,
    budget: EpisodeBudget | None,
    seed_salt: str | None,
    openai_available: bool,
    openai_class,
    title_cfg: dict[str, Any],
    max_album_title_bytes: int,
) -> str:
    seed_parts = [image_filename, episode_date or "", channel_id]
    if seed_salt:
        seed_parts.append(seed_salt)
    seed = "|".join(seed_parts)

    budget = ensure_budget(budget, max_calls=2)
    strict_ai = _strict_ai_enabled(api_key)

    if strict_ai and (not openai_available or openai_class is None):
        raise RuntimeError("OpenAI client not available (missing python package). AI title generation is required.")

    cache = _get_cache(channel_id)
    cooldown_words = sorted(cache.cooldown_set())
    recent_titles = list(cache.recent_titles)
    recent_structures = list(cache.recent_structures)
    recent_roles = list(cache.recent_roles)

    # Token pipeline: parse -> clean -> perturb -> clean.
    tokens = extract_content_tokens(image_filename)
    tokens = clean_tokens(perturb_tokens(tokens, seed))

    color_desc = _rgb_to_hex(theme_color_rgb)
    season_hint = _season_hint_from_date(episode_date)

    title: Optional[str] = None
    if api_key and openai_available and openai_class is not None:
        try:
            budget.consume("album_title")
            prompt = build_album_title_prompt_from_tokens(
                tokens=tokens,
                color_desc=color_desc,
                season_hint=season_hint,
                recent_titles=recent_titles,
                cooldown_words=cooldown_words,
                recent_structures=recent_structures,
                recent_roles=recent_roles,
            )
            system_prompt = "You are a music label naming assistant. Output only the title."
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(
                None,
                _openai_chat_sync,
                api_key,
                api_base,
                model,
                system_prompt,
                prompt,
                title_cfg["timeout"],
                title_cfg["max_tokens"],
                title_cfg["temperature"],
                openai_available,
                openai_class,
            )
            title = _titlecase_clean(raw)
            ok, reason = validate_album_title_physical(
                title,
                min_words=3,
                max_words=7,
                max_bytes=max_album_title_bytes,
            )
            if not ok:
                msg = f"Album title failed validation ({reason}): {title}"
                log_warning(msg)
                if strict_ai:
                    raise RuntimeError(msg)
                title = None
        except BudgetExceeded:
            msg = "Album title skipped due to budget guard."
            log_warning(msg)
            if strict_ai:
                raise RuntimeError(msg)
        except Exception as e:
            msg = f"Album title AI call failed: {e}"
            log_warning(msg)
            if strict_ai:
                raise RuntimeError(msg)

    if title:
        # Similarity heuristic (no retries): if too close to historical catalog, fall back once.
        historical = _ensure_historical_titles_loaded()
        if historical and _is_too_similar(title, historical, threshold=0.90):
            msg = "Album title too similar to historical titles."
            log_warning(msg)
            if strict_ai:
                raise RuntimeError(msg)
            title = None

    if not title:
        if strict_ai:
            raise RuntimeError("Album title generation failed (strict AI mode).")
        set_fallback_cooldown(cache.cooldown_set(), cache.cooldown_last7_set())
        set_fallback_hints(recent_structures, recent_roles)
        title = fallback_album_title(tokens=tokens, seed=seed, min_words=3, max_words=7)

    if strict_ai:
        recent_lower = {t.strip().lower() for t in cache.recent_titles}
        if title.strip().lower() in recent_lower:
            raise RuntimeError("Album title matches a recent title (strict AI mode, no fallback).")

    title = _apply_recent_penalty_once(title, cache, tokens=tokens, seed=seed, max_album_title_bytes=max_album_title_bytes)

    _finalize_and_cache_title(channel_id, cache, title)
    return title


async def generate_youtube_title_and_description(
    album_title: str,
    playlist_data: dict[str, Any],
    api_key: str | None,
    api_base: str | None,
    model: str | None,
    channel_id: str,
    budget: EpisodeBudget | None,
    openai_available: bool,
    openai_class,
    max_title_chars: int,
    max_title_bytes: int,
    description_cfg: dict[str, Any],
    default_hashtags: list[str],
) -> tuple[str, str]:
    if not album_title:
        album_title = "Untitled"

    budget = ensure_budget(budget, max_calls=2)
    # Keep album titles strict (no fallback) at generation time, but allow descriptions
    # to fall back locally so production can continue during transient network/API issues.
    strict_desc = False

    tracks_a = playlist_data.get("tracks_a", [])
    tracks_b = playlist_data.get("tracks_b", [])
    clean_timeline = playlist_data.get("clean_timeline", [])

    tracklist_text = _build_tracklist_text(tracks_a, tracks_b, clean_timeline)

    seed = f"{album_title}|{channel_id}"
    youtube_title = _build_youtube_title(album_title, seed, max_title_chars, max_title_bytes)

    text_content: str
    if api_key and openai_available and openai_class is not None:
        try:
            raw_desc = _generate_description_sync(
                album_title=album_title,
                tracks_a=tracks_a,
                tracks_b=tracks_b,
                tracklist_text=tracklist_text,
                api_key=api_key,
                api_base=api_base,
                model=model,
                budget=budget,
                openai_available=openai_available,
                openai_class=openai_class,
                timeout=description_cfg["timeout"],
                max_tokens=description_cfg["max_tokens"],
                temperature=description_cfg["temperature"],
            )
            text_content = _clean_youtube_description(raw_desc)
            log_info(f"YouTube 描述生成成功（{len(text_content)} 字符）")
        except BudgetExceeded:
            msg = "Description skipped due to budget guard."
            log_warning(msg)
            if strict_desc:
                raise RuntimeError(msg)
            text_content = _fallback_description(album_title, len(tracks_a) + len(tracks_b))
        except Exception as e:
            msg = f"Description AI call failed: {e}"
            log_warning(msg)
            if strict_desc:
                raise RuntimeError(msg)
            text_content = _fallback_description(album_title, len(tracks_a) + len(tracks_b))
    else:
        text_content = _fallback_description(album_title, len(tracks_a) + len(tracks_b))

    if tracklist_text:
        description = text_content + f"\n\nTracklist / Timecode\n\n{tracklist_text}"
    else:
        description = text_content
    description += "\n\n" + " ".join(default_hashtags)

    return youtube_title, description
