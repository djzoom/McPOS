from __future__ import annotations

import re
from typing import Iterable


DEFAULT_MAX_BYTES = 60

# Optional connector words allowed at most once per album title.
ALLOWED_CONNECTORS = {
    "in", "on", "under", "at", "by", "from", "through", "along", "near",
}

# Articles are not allowed as standalone words.
ARTICLES = {"a", "an", "the"}

# Common prepositions (for disallowed-preposition detection).
COMMON_PREPOSITIONS = {
    "of", "to", "with", "without", "over", "under", "between", "inside", "outside",
    "near", "through", "along", "around", "across", "before", "after", "during",
    "into", "onto", "off", "up", "down", "in", "on", "at", "by", "from",
    "beneath", "beside", "behind", "above", "below", "within", "upon",
}

# SEO intent words must never appear in album titles.
SEO_WORDS = {
    "lofi", "lo-fi", "ambient",
    "focus", "study", "sleep", "calm", "work", "coding", "productivity",
    "background", "music",
}

# Prompt / process / UI junk. Match by stem containment on normalized words.
PROMPT_GARBAGE_STEMS = {
    "render", "styliz", "simplif", "illustr", "decor", "background", "wallpaper",
    "prompt", "photo", "image", "artwork", "digital", "abstract", "infographic",
    "framed", "frame", "placed", "place", "designed", "design", "depict",
    "mode", "video", "track", "mix",
}

TRUNCATED_FRAGMENTS = {
    "decorat", "illustrat", "styliz", "simplif", "render",
    "guit", "cabi", "morph", "morphs",
}

# Short concrete words that are allowed (avoid false positives for 3–5 letter nouns).
SHORT_WORD_ALLOWLIST = {
    "cat", "bus", "map", "case", "lamp", "dial", "tape",
    "rain", "mist", "haze", "dew", "dawn", "dusk", "glow",
    "road", "lane", "dock", "quay", "hall", "loft",
    "wood", "gold", "iron", "tile", "glass",
    "moon", "star", "sun", "pine", "yard",
}

# Some -ed words are acceptable as tangible surface states.
ALLOWED_ED_WORDS = {"gilded", "frosted", "weathered", "polished", "mossed", "etched"}


def _normalize_word(word: str) -> str:
    return re.sub(r"[^A-Za-z]", "", word).lower()


def _strip_outer_quotes(text: str) -> str:
    stripped = text.strip()
    if len(stripped) >= 2 and stripped[0] in {'"', "'", "“", "”"} and stripped[-1] in {'"', "'", "“", "”"}:
        return stripped[1:-1].strip()
    return stripped


def _extract_words(title: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'\-]*", title)


def _is_title_case_word(word: str) -> bool:
    """
    Title Case check that supports hyphens/apostrophes.
    Each segment must be Capitalized (A + lowercase).
    """
    if not word:
        return False
    for seg in re.split(r"[-']", word):
        if not seg:
            return False
        if not ("A" <= seg[0] <= "Z"):
            return False
        if seg[1:] and not seg[1:].islower():
            return False
    return True


def _looks_like_gibberish(token: str) -> bool:
    # very low vowel ratio (treat y as vowel for stability)
    t = token.lower()
    vowels = sum(1 for ch in t if ch in "aeiouy")
    # For short tokens, only treat "no vowel at all" as gibberish.
    # A stricter vowel-ratio check causes false positives for valid nouns like "drift" or "front".
    if len(t) <= 5:
        return vowels == 0
    return (vowels / max(1, len(t))) < 0.22


def _is_prompt_garbage(norm: str) -> bool:
    if not norm:
        return True
    for stem in PROMPT_GARBAGE_STEMS:
        if stem in norm:
            return True
    return False


def _is_truncated_fragment(norm: str) -> bool:
    if norm in TRUNCATED_FRAGMENTS:
        return True
    for stem in ["decorat", "illustrat", "styliz", "simplif", "render"]:
        if norm.startswith(stem) and len(norm) <= len(stem) + 2:
            return True
    return False


def validate_album_title_physical(
    title: str,
    allowed_words: Iterable[str] | None = None,  # kept for call-site compatibility; not enforced
    forbidden_words: Iterable[str] | None = None,  # kept for call-site compatibility; not enforced
    min_words: int = 3,
    max_words: int = 7,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> tuple[bool, str]:
    if not title:
        return False, "empty"

    raw = _strip_outer_quotes(title).strip()
    raw = re.sub(r"\s+", " ", raw).strip()

    if re.search(r"\d", raw):
        return False, "contains_digits"
    if re.search(r"[^A-Za-z'\- ]", raw):
        return False, "contains_invalid_chars"

    words = _extract_words(raw)
    if len(words) < min_words or len(words) > max_words:
        return False, "word_count"

    if not all(_is_title_case_word(w) for w in words):
        return False, "not_title_case"

    # Count and validate connectors/prepositions.
    connector_count = 0

    seen: set[str] = set()
    for w in words:
        norm = _normalize_word(w)
        if not norm:
            return False, "invalid_word"

        if norm in seen:
            return False, "duplicated_word"
        seen.add(norm)

        if norm in SEO_WORDS:
            return False, "seo_word"

        if norm in ARTICLES:
            return False, "contains_article"

        # Preposition management: allow at most one connector from a limited set.
        if norm in COMMON_PREPOSITIONS:
            if norm not in ALLOWED_CONNECTORS:
                return False, "contains_disallowed_preposition"
            connector_count += 1
            if connector_count > 1:
                return False, "too_many_prepositions"

        # Prompt/process junk words or stems.
        if _is_prompt_garbage(norm):
            return False, "prompt_garbage"

        # Truncated fragments.
        if _is_truncated_fragment(norm):
            return False, "truncated_fragment"

        # Avoid adverbs and verb-like forms that break noun-phrase feel.
        if len(norm) >= 5 and norm.endswith("ly"):
            return False, "adverb_form"

        if len(norm) >= 6 and norm.endswith("ing"):
            return False, "verb_form"
        if len(norm) >= 6 and norm.endswith("ed") and norm not in ALLOWED_ED_WORDS:
            return False, "verb_form"

        # Suspicious short fragments (e.g., Cab, Guit, Bca) unless allowlisted.
        if 3 <= len(norm) <= 5 and norm not in SHORT_WORD_ALLOWLIST:
            if _looks_like_gibberish(norm):
                return False, "suspicious_fragment"

    if len(raw.encode("utf-8")) > max_bytes:
        return False, "byte_length"

    return True, "ok"


def _titlecase_clean(text: str) -> str:
    cleaned = _strip_outer_quotes(text)
    cleaned = re.sub(r"[^A-Za-z'\- ]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    out_words: list[str] = []
    for w in cleaned.split():
        parts = w.split("-")
        fixed_parts: list[str] = []
        for p in parts:
            if not p:
                continue
            # keep apostrophes inside part
            subparts = p.split("'")
            fixed_sub: list[str] = []
            for sp in subparts:
                if not sp:
                    continue
                fixed_sub.append(sp[:1].upper() + sp[1:].lower())
            fixed_parts.append("'".join(fixed_sub))
        out_words.append("-".join(fixed_parts))
    return " ".join(out_words)


def _title_similarity(a: str, b: str) -> float:
    aw = set(re.findall(r"[A-Za-z]+", a.lower()))
    bw = set(re.findall(r"[A-Za-z]+", b.lower()))
    if not aw or not bw:
        return 0.0
    return len(aw & bw) / max(1, len(aw | bw))


def _is_too_similar(title: str, historical: list[str], threshold: float = 0.85) -> bool:
    for h in historical:
        if title.strip().lower() == h.strip().lower():
            return True
        if _title_similarity(title, h) >= threshold:
            return True
    return False


def extract_core_words(title: str) -> list[str]:
    """
    Minimal, deterministic "core words" extraction for cooldown.
    Drops connectors and label fragments.
    """
    raw = _strip_outer_quotes(title).strip()
    words = re.findall(r"[A-Za-z]+", raw)
    out: list[str] = []
    for w in words:
        lw = w.lower()
        if len(lw) < 3:
            continue
        if lw in ALLOWED_CONNECTORS:
            continue
        if lw in {"lp", "vinyl"}:
            continue
        out.append(lw)
    return out
