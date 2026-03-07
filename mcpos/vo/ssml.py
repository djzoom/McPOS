"""Helpers for building and parsing SSML."""

from __future__ import annotations

import html
import re
from typing import Iterable

_BREAK_RE = re.compile(r"<break\s+time=['\"](?P<value>[0-9.]+)s['\"]\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def paragraphs_to_ssml(lines: Iterable[str], *, break_sec: float = 2.0) -> str:
    cleaned = [line.strip() for line in lines if line and line.strip()]
    if not cleaned:
        return ""
    parts: list[str] = []
    for idx, line in enumerate(cleaned):
        parts.append(html.escape(line))
        if idx != len(cleaned) - 1:
            parts.append(f"<break time=\"{break_sec:.1f}s\" />")
    return " ".join(parts)


def strip_ssml(ssml_text: str) -> str:
    if not ssml_text:
        return ""
    without_breaks = _BREAK_RE.sub(" ", ssml_text)
    plain = _TAG_RE.sub("", without_breaks)
    return html.unescape(re.sub(r"\s+", " ", plain)).strip()


def parse_ssml_timeline_tokens(ssml_text: str) -> list[dict[str, float | str]]:
    """Split SSML into text and break tokens for rough timeline allocation."""

    if not ssml_text:
        return []

    tokens: list[dict[str, float | str]] = []
    cursor = 0
    for match in _BREAK_RE.finditer(ssml_text):
        text_chunk = strip_ssml(ssml_text[cursor:match.start()])
        if text_chunk:
            tokens.append({"type": "text", "text": text_chunk})
        tokens.append({"type": "break", "seconds": float(match.group("value"))})
        cursor = match.end()

    tail = strip_ssml(ssml_text[cursor:])
    if tail:
        tokens.append({"type": "text", "text": tail})
    return tokens


def excerpt_text(text: str, *, from_end: bool = False, max_words: int = 90) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    if from_end:
        return " ".join(words[-max_words:]).strip()
    return " ".join(words[:max_words]).strip()
