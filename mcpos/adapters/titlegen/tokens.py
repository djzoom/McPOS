from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .utils import seeded_random


# NOTE: Token cleaning is a deterministic, local guardrail. This is NOT a "banned words"
# system for creative output; it only removes filename/process junk and functional glue.
CONTENT_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "so", "yet",
    "of", "to", "in", "on", "at", "by", "from", "with", "without", "over",
    "under", "between", "inside", "outside", "beside", "near", "through",
    "along", "around", "across", "before", "after", "during", "into", "onto",
    "off", "up", "down", "out", "about", "as", "per", "via", "while",
    # View/camera leftovers that often appear in MJ-style filenames.
    "front", "back", "view",
    "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "my", "your", "his", "her", "their",
    "our", "its", "me", "you", "him", "her", "them", "us", "it",
    "no", "not", "only", "just",
}

# Common prompt/process glue that should never become a title anchor.
PROMPT_GARBAGE = {
    "render", "rendered", "rendering",
    "stylize", "stylized", "stylizing", "stylised", "stylish",
    "simplify", "simplified", "simplifying",
    "illustrate", "illustrated", "illustrating",
    "depict", "depicted", "depicting",
    "design", "designed", "designing",
    "frame", "framed", "framing",
    "place", "placed", "placing",
    "decorate", "decorated", "decorative",
    "background", "wallpaper",
    "photo", "image", "artwork", "digital", "abstract", "infographic",
    "prompt", "mode", "video",
    "unsee", "unseen",
}

SEO_GARBAGE = {
    "lofi", "lo-fi", "ambient", "focus", "study", "sleep", "calm", "work", "coding", "productivity",
}

ADJECTIVE_GARBAGE = {
    "small", "tiny", "cute", "quiet", "calm",
    "bright", "brightly",
    "huge", "large",
    "minimal", "simple", "clean",
    "vintage", "modern", "abstract",
}

TRUNCATED_FRAGMENTS = {
    # Midjourney / prompt stems frequently truncated by filename tokenization.
    "decorat", "illustrat", "styliz", "simplif",
    # Common "looks like a word but isn't finished" stems.
    "guit", "cabi", "morph", "morphs",
}

SHORT_WORD_ALLOWLIST = {
    # Concrete nouns likely to appear in filenames.
    "cat", "bus", "map", "case", "lamp", "dial",
    "rain", "mist", "haze", "dawn", "dusk", "glow",
    "road", "lane", "dock", "quay", "hall", "loft",
    "wood", "gold", "iron", "tile", "glass",
    "moon", "star", "sun", "pine", "yard",
}

MIN_TOKEN_LEN = 3


def parse_filename_semantics(image_filename: str) -> list[str]:
    if not image_filename:
        return []
    name = Path(image_filename).stem
    if name.startswith("0x") or name.startswith("@"):
        name = re.sub(r"^(0x[^-_]+|@[^-_]+)[-_]*", "", name)
    name = re.sub(r"[_-][0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$", "", name)

    raw_tokens = re.split(r"[^A-Za-z]+", name)
    tokens: list[str] = []
    for t in raw_tokens:
        if not t:
            continue
        if len(t) < MIN_TOKEN_LEN:
            continue
        if re.search(r"\d", t):
            continue
        tokens.append(t.lower())
    return tokens


def _looks_like_gibberish(token: str) -> bool:
    """
    Cheap heuristic for clipped/hash-like fragments:
    - very low vowel ratio (y counts as vowel for stability)
    - no vowels at all for short tokens
    """
    t = token.lower()
    vowels = sum(1 for ch in t if ch in "aeiouy")
    if len(t) <= 4:
        return vowels == 0
    return (vowels / max(1, len(t))) < 0.22


def _is_truncated_fragment(token: str) -> bool:
    t = token.lower()
    if t in TRUNCATED_FRAGMENTS:
        return True
    # Common truncated stems with short length.
    for stem in ["decorat", "illustrat", "styliz", "simplif", "render"]:
        if t.startswith(stem) and len(t) <= len(stem) + 2:
            return True
    return False


def _is_garbage_token(token: str) -> bool:
    t = token.lower().strip()
    if not t:
        return True
    if len(t) < MIN_TOKEN_LEN:
        return True
    if t in CONTENT_STOPWORDS:
        return True
    if t in PROMPT_GARBAGE:
        return True
    if t in ADJECTIVE_GARBAGE:
        return True
    if t in SEO_GARBAGE:
        return True
    if _is_truncated_fragment(t):
        return True
    # Adverbs are almost always prompt residue and hurt noun-phrase titles.
    if len(t) >= 5 and t.endswith("ly"):
        return True
    # Drop obvious verb-ish forms that show up as prompt residue ("sitting", "resting", "closed").
    if len(t) >= 6 and t.endswith(("ing",)):
        return True
    if len(t) <= 4 and t not in SHORT_WORD_ALLOWLIST and _looks_like_gibberish(t):
        return True
    return False


def clean_tokens(tokens: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen = set()
    for t in tokens:
        lt = t.lower()
        if _is_garbage_token(lt):
            continue
        if lt in seen:
            continue
        seen.add(lt)
        cleaned.append(lt)
    return cleaned


def extract_content_tokens(image_filename: str) -> list[str]:
    return clean_tokens(parse_filename_semantics(image_filename))


def perturb_tokens(tokens: list[str], seed: str) -> list[str]:
    if not tokens:
        return []

    rnd = seeded_random(seed + "|tokens")
    out = tokens[:]
    if len(out) > 1:
        rnd.shuffle(out)

    # Drop 0–2 tokens deterministically, but keep at least 2 anchors when possible.
    if len(out) > 2:
        drop_max = min(2, len(out) - 2)
        drop_n = rnd.randint(0, drop_max)
        if drop_n:
            out = out[:-drop_n]

    synonym_map = {
        # Adjacent semantics, used to avoid rigid filename mirroring.
        "street": "avenue",
        "road": "lane",
        "lane": "alley",
        "city": "arcade",
        "rain": "drizzle",
        "storm": "haze",
        "snow": "frost",
        "window": "skylight",
        "speaker": "cabinet",
        "turntable": "plinth",
        "vinyl": "record",
        "map": "blueprint",
        "cat": "feline",
        "instrument": "guitar",
        "case": "sleeve",
        "quay": "dock",
        "atrium": "corridor",
    }

    replaced: list[str] = []
    for t in out:
        if t in synonym_map and rnd.random() < 0.35:
            replaced.append(synonym_map[t])
        else:
            replaced.append(t)

    return replaced


def build_album_title_prompt_from_tokens(
    tokens: list[str],
    color_desc: str,
    season_hint: Optional[str] = None,
    recent_titles: Optional[list[str]] = None,
    cooldown_words: Optional[list[str]] = None,
    recent_structures: Optional[list[str]] = None,
    recent_roles: Optional[list[str]] = None,
) -> str:
    token_str = ", ".join(tokens) if tokens else "(none)"
    season_line = f"Season hint: {season_hint}" if season_hint else "Season hint: (none)"
    recent_titles_str = "\n".join(f"- {t}" for t in (recent_titles or [])) or "(none)"
    cooldown_str = ", ".join(cooldown_words or []) or "(none)"
    recent_structures_str = ", ".join(recent_structures or []) or "(none)"
    recent_roles_str = ", ".join(recent_roles or []) or "(none)"

    return (
        "Name a vinyl release for Kat Records.\n\n"
        "Return ONE album title only, as a sleeve-ready noun phrase in Title Case.\n\n"
        "The image filename is your primary source of truth. Your title should feel like it belongs to that cover. "
        "Use the filename tokens to infer what is visibly present, then compress that into a physical, print-ready name.\n\n"
        "Target length:\n"
        "- Prefer 4–6 words\n"
        "- Allow 3–7\n"
        "- Allow 2 only when extremely strong and concrete\n\n"
        "How to use the filename tokens well:\n"
        "- First, extract 2–3 image anchors by answering silently: main subject, main object, setting, style cue.\n"
        "- Convert anchors into concrete nouns that can be printed on a sleeve.\n"
        "- Keep at least one anchor close to a literal token unless it is clearly junk.\n"
        "- If a token is weak, upgrade it rather than discarding it.\n\n"
        "Token to role mapping rules (use as guidance, not as a literal list to copy):\n"
        "Object role: Cat, Speaker, Turntable, Vinyl, Record, Bus, Map, Window, Lantern, Guitar, Table, Doorway.\n"
        "Place role: Studio, Arcade, Alley, Rooftop, Courtyard, Harbor, Quay, Promenade, Atrium, Corner, Backroom, Booth, Gallery, Corridor.\n"
        "Material role: Glass, Marble, Porcelain, Linen, Cedar, Copper, Bronze, Granite, Ivory, Obsidian, Chrome, Tile, Concrete.\n"
        "Atmosphere role: Rain, Mist, Haze, Frost, Glow, Dusk, Dawn, Emberlight, Afterglow, Static, Dimlight.\n\n"
        "If a token is close to a role but not perfect, refine it:\n"
        "- Cabinet/Stack/System/Equipment -> Speaker, Console, Hi-Fi, Cabinet Speaker.\n"
        "- Infographic/Diagram/Grid -> Map, Grid, Blueprint, Street Map.\n"
        "- Minimal/Bauhaus/Bohemian -> do not name the style; translate into an object/place cue (Gallery, Studio, Poster Wall, Linework, Monochrome Print).\n"
        "- City/Street/Road/Lane -> choose one physical setting (Road, Lane, Alley, Boulevard).\n\n"
        "Diversity and freshness:\n"
        "Avoid echoing recent titles:\n"
        f"{recent_titles_str}\n"
        "Do not reuse any cooldown word from the last 20 episodes:\n"
        f"{cooldown_str}\n"
        "If a cooled word is suggested by tokens, substitute a close physical alternative "
        "(Atrium -> Corridor/Hallway. Quay -> Dock/Landing. Rain -> Condensation/Drizzle. Glass -> Pane/Chrome).\n"
        f"Vary structure compared to: {recent_structures_str}.\n"
        f"Rotate the leading role compared to: {recent_roles_str}.\n\n"
        "Avoid SEO/audio/format language inside the album title (keep SEO for the subtitle only):\n"
        "- Never use: LoFi, Lo-Fi, Ambient, Beats, Acoustic, Session, Mix, Music, Focus, Study, Sleep, Calm, Work, Coding, Productivity.\n\n"
        "Avoid abbreviations and code-like words:\n"
        "- Do not use acronyms/initialisms (e.g., RGB, BPM, AI). Every word should look like a normal English noun.\n\n"
        "Choose one structure, based on the strongest visible anchors:\n"
        "1) Object + Material + Place + Atmosphere\n"
        "2) Material + Object + Place + Atmosphere\n"
        "3) Material + Place + Atmosphere + Object\n"
        "4) Object + Place + Material + Atmosphere\n"
        "5) Material + Place + Atmosphere\n"
        "6) Material + Object + Place\n\n"
        "Optional connector, at most one, only if it makes the scene more seeable:\n"
        "In, On, Under, At, By, From, Through, Along, Near.\n\n"
        "Calibration examples (do not copy, only match the level of visual anchoring):\n"
        "Cat Copper Studio Dusk\n"
        "Vinyl Chrome Arcade Glow\n"
        "Speaker Linen Rooftop Rain\n"
        "Bus Obsidian Road Dawn\n"
        "Map Ivory Studio Haze\n"
        "Speaker Bronze Backroom Static\n"
        "Vinyl Through Cedar Corridor Dimlight\n\n"
        "Now use the inputs:\n"
        f"Filename tokens: {token_str}\n"
        f"Color mood: {color_desc}\n"
        f"{season_line}\n"
        f"Recent titles: {recent_titles_str}\n"
        f"Cooldown words: {cooldown_str}\n"
        f"Recent structures: {recent_structures_str}\n"
        f"Recent leading roles: {recent_roles_str}\n\n"
        "Return only the title line.\n"
    )
