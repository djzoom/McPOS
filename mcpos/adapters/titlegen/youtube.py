from __future__ import annotations

from .utils import seeded_random


# Subtitle is SEO-forward (functional), not creative. No model calls.
# Keep subtitles as plain English phrases (no periods). Avoid duplicate words.
_SUBTITLES: list[str] = [
    "LoFi for Study and Focus",
    "LoFi for Deep Focus",
    "LoFi for Coding and Work",
    "LoFi Beats for Coding",
    "LoFi Beats for Deep Work",
    "LoFi Beats for Study",
    "LoFi Beats for Focus",
    "LoFi for Reading and Writing",
    "LoFi for Writing and Work",
    "LoFi for Work and Focus",
    "LoFi for Work and Study",
    "LoFi for Calm Study",
    "Ambient for Deep Work",
    "Ambient for Study and Focus",
    "Ambient for Coding and Work",
    "Ambient for Focus and Calm",
    "Ambient for Reading and Writing",
    "Ambient for Meditation and Calm",
    "Ambient for Sleep and Calm",
    "Ambient for Relax and Focus",
    "Ambient for Work and Focus",
    "Ambient for Work and Study",
    "White Noise for Sleep",
    "White Noise for Sleep and Calm",
    "White Noise for Deep Sleep",
    "White Noise for Relax and Calm",
    "White Noise for Focus",
    "White Noise for Study and Focus",
    "White Noise for Coding",
    "White Noise for Work",
    "Vinyl White Noise for Sleep",
    "Vinyl White Noise for Focus",
    "Vinyl White Noise for Study",
    "Vinyl White Noise for Coding",
    "Analog Noise for Sleep",
    "Analog Noise for Focus",
    "Analog Noise for Study",
    "Analog Noise for Deep Work",
    "Analog Noise for Calm",
    "LoFi and White Noise for Sleep",
    "LoFi and White Noise for Focus",
    "LoFi and White Noise for Study",
    "LoFi and White Noise for Coding",
    "Ambient and White Noise for Sleep",
    "Ambient and White Noise for Focus",
    "Ambient and White Noise for Study",
    "Ambient and White Noise for Coding",
    "LoFi for Study and Relax",
    "LoFi for Sleep and Calm",
    "LoFi for Meditation and Calm",
    "LoFi for Relax and Calm",
    "LoFi for Focus and Calm",
    "LoFi for Study and Work",
    "LoFi Beats for Relax",
    "LoFi Beats for Calm",
    "LoFi Beats for Sleep",
    "LoFi Beats for Meditation",
    "Ambient for Calm Work",
    "Ambient for Focus Work",
    "Ambient for Coding Focus",
    "Ambient for Study Focus",
    "Ambient for Night Work",
    "Ambient for Quiet Work",
    "White Noise for Night Sleep",
    "White Noise for Office Focus",
    "White Noise for Study Time",
    "White Noise for Coding Time",
    "Vinyl Noise for Sleep",
    "Vinyl Noise for Focus",
    "Vinyl Noise for Study",
    "Vinyl Noise for Coding",
    "Analog Vinyl Noise for Sleep",
    "Analog Vinyl Noise for Focus",
    "Analog Vinyl Noise for Study",
    "Analog Vinyl Noise for Coding",
    "LoFi for Late Night Work",
    "LoFi for Morning Focus",
    "LoFi for Afternoon Study",
    "LoFi for Evening Relax",
    "Ambient for Morning Focus",
    "Ambient for Evening Calm",
    "Ambient for Late Night Study",
    "Ambient for Late Night Coding",
    "White Noise for Late Night Sleep",
    "White Noise for Late Night Focus",
    "LoFi for Clean Desk Work",
    "LoFi for Creative Focus",
    "LoFi for Steady Work",
    "Ambient for Steady Work",
    "Ambient for Creative Work",
    "White Noise for Steady Focus",
    "Vinyl White Noise for Deep Focus",
    "LoFi Beats for Steady Focus",
    "Ambient for Deep Focus",
    "LoFi for Deep Work and Focus",
    "Ambient for Deep Work and Focus",
    "LoFi for Study Coding and Focus",
    "Ambient for Study Coding and Focus",
    "LoFi for Work Coding and Focus",
    "White Noise for Work and Focus",
]


def _subtitle_bytes(s: str) -> int:
    return len(s.encode("utf-8"))


# Group by actual UTF-8 byte length; keys can be used as "fits <= key" buckets.
SUBTITLE_POOL_BY_BYTES: dict[int, list[str]] = {}
for _s in _SUBTITLES:
    SUBTITLE_POOL_BY_BYTES.setdefault(_subtitle_bytes(_s), []).append(_s)

_MIN_SUBTITLE = min(_SUBTITLES, key=_subtitle_bytes)

PRESENTS_PREFIX = "Kat Records Presents"


def _fits(text: str, max_chars: int, max_bytes: int) -> bool:
    return len(text) <= max_chars and len(text.encode("utf-8")) <= max_bytes


def _choose_subtitle(seed: str, remaining_chars: int, remaining_bytes: int) -> str:
    rnd = seeded_random(seed + "|subtitle")

    candidates = [
        s for s in _SUBTITLES
        if len(s) <= remaining_chars and _subtitle_bytes(s) <= remaining_bytes
    ]
    if candidates:
        return rnd.choice(candidates)

    # No subtitle fully fits: use the shortest (deterministic) and let truncation handle final fit.
    return _MIN_SUBTITLE


def _truncate_words_to_fit(subtitle: str, remaining_chars: int, remaining_bytes: int) -> str:
    words = subtitle.split()
    while words:
        candidate = " ".join(words)
        if len(candidate) <= remaining_chars and _subtitle_bytes(candidate) <= remaining_bytes:
            return candidate
        words.pop()
    return "LoFi"  # last resort; should still fit in almost all cases


def _build_youtube_title(album_title: str, seed: str, max_chars: int, max_bytes: int) -> str:
    album_title = (album_title or "").strip() or "Untitled"

    prefix = f"{album_title} LP | {PRESENTS_PREFIX} "
    remaining_chars = max_chars - len(prefix)
    remaining_bytes = max_bytes - len(prefix.encode("utf-8"))

    subtitle = _choose_subtitle(seed, remaining_chars, remaining_bytes)
    subtitle = _truncate_words_to_fit(subtitle, remaining_chars, remaining_bytes)

    candidate = prefix + subtitle
    if _fits(candidate, max_chars, max_bytes):
        return candidate

    # Extremely rare: prefix itself is too long; truncate subtitle completely.
    candidate = (prefix.rstrip() + " LoFi")[:max_chars].rstrip()
    encoded = candidate.encode("utf-8")[:max_bytes]
    return encoded.decode("utf-8", errors="ignore").rstrip()

