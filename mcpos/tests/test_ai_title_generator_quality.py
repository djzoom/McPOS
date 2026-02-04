from __future__ import annotations

import re

from mcpos.adapters.ai_title_generator import MAX_YT_TITLE_CHARS, MAX_YT_TITLE_BYTES
from mcpos.adapters.titlegen.tokens import parse_filename_semantics, clean_tokens
from mcpos.adapters.titlegen.fallback import fallback_album_title, set_fallback_cooldown
from mcpos.adapters.titlegen.validate import validate_album_title_physical
from mcpos.adapters.titlegen.youtube import _build_youtube_title


def _words(title: str) -> list[str]:
    return re.findall(r"[A-Za-z]+", title)


def test_token_cleaning_removes_prompt_junk_and_prepositions():
    filename = (
        "0xgarfield_A_cat_beside_a_large_speaker_simplified_into_decorat_"
        "a45775db-81c1-4ed3-afb0-6c547dc06ad2.png"
    )
    raw = parse_filename_semantics(filename)
    cleaned = clean_tokens(raw)
    assert "cat" in cleaned
    assert "speaker" in cleaned
    assert "beside" not in cleaned
    assert "simplified" not in cleaned
    assert "into" not in cleaned
    assert "decorat" not in cleaned


def test_token_cleaning_removes_unsee_and_handles_uuid_suffix():
    filename = (
        "0xgarfield_A_cat_near_a_closed_instrument_case_instrument_unsee_"
        "765ad812-9b30-43b2-8c7e-0f498ffc3438.png"
    )
    raw = parse_filename_semantics(filename)
    cleaned = clean_tokens(raw)
    assert "cat" in cleaned
    assert "instrument" in cleaned
    assert "case" in cleaned
    assert "near" not in cleaned
    assert "unsee" not in cleaned
    assert "ffc" not in cleaned


def test_fallback_titles_validate_and_avoid_junk_words():
    tokens = ["cat", "instrument", "case", "window", "harbor"]
    set_fallback_cooldown(set())  # no cooling for this test
    for i in range(50):
        title = fallback_album_title(tokens, seed=f"seed-{i}", min_words=3, max_words=7)
        ok, reason = validate_album_title_physical(title, min_words=3, max_words=7)
        assert ok, (title, reason)
        lowered = [w.lower() for w in _words(title)]
        # obvious junk/functional residues must not appear
        assert all(w not in {"the", "out", "while", "video", "mode", "rendered", "simplified", "decorat"} for w in lowered)


def test_youtube_title_format_and_length():
    album = "Bronze Studio Cabinet"
    title = _build_youtube_title(album, seed="test-seed", max_chars=MAX_YT_TITLE_CHARS, max_bytes=MAX_YT_TITLE_BYTES)
    assert len(title) <= MAX_YT_TITLE_CHARS
    assert len(title.encode("utf-8")) <= MAX_YT_TITLE_BYTES
    assert title.startswith(f"{album} LP | Kat Records Presents ")
    assert "Kat Records Presents" in title

