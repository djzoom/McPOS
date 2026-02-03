# coding: utf-8
"""
Fallback Album Title Generator (High-Score Physical)

Design goals
- Deterministic (seeded)
- No model calls
- Matches the same "physical, sleeve-ready noun phrase" style as the AI prompt
- Majority 4–6 words; 3-word titles are a minority, 2-word titles are rare
- Enforces a rolling cooldown of recent core words to reduce repetition
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from ...core.logging import log_warning
from .tokens import clean_tokens
from .utils import seeded_random
from .validate import validate_album_title_physical


# Expanded, non-overlapping vocab pools to escape "Glass/Atrium/Rain" loops.
MATERIAL_WORDS: list[str] = [
    "Porcelain", "Linen", "Cedar", "Copper", "Bronze", "Chrome", "Enamel",
    "Tile", "Plaster", "Concrete", "Leather", "Canvas", "Wool", "Felt",
    "Slate", "Basalt", "Travertine", "Rattan", "Brass", "Tin", "Lacquer",
    "Marble", "Granite", "Obsidian", "Ivory", "Glass", "Stone",
]

PLACE_WORDS: list[str] = [
    "Corridor", "Passage", "Stairwell", "Landing", "Workshop", "Loft",
    "Basement", "Studio", "Bay", "Booth", "Hallway", "Arcade",
    "Lane", "Dock", "Backroom", "Greenroom", "Threshold",
    "Entryway", "Gallery", "Alcove", "Courtyard", "Harbor", "Promenade",
    "Rooftop", "Alley", "Quay",
]

ATMOS_WORDS: list[str] = [
    "Haze", "Condensation", "Steam", "Static", "Glare", "Dimlight",
    "Afterglow", "Embers", "Cinders", "Draft", "Chill", "Dew", "Gloom",
    "Foglight", "Mist", "Drift", "Frost", "Glow", "Rain", "Dusk", "Dawn",
]

OBJECT_WORDS: list[str] = [
    "Record", "Sleeve", "Needle", "Plinth", "Cassette", "Spool", "Notebook",
    "Tape", "Switch", "Dial", "Speaker", "Lamp", "Window", "Doorway",
    "Tilework", "Skylight", "Turntable", "Map", "Bus", "Cat", "Case",
]

DETAIL_WORDS: list[str] = [
    "Corridor", "Stairwell", "Passage", "Doorway", "Shoreline", "Awning",
    "Tilework", "Skylight", "Cobblestone", "Workshop", "Landing", "Threshold",
]

CONNECTORS: list[str] = ["In", "On", "Under", "At", "By", "From", "Through", "Along", "Near"]

# Normalized sets (lowercase) for role matching.
_M_SET = {w.lower(): w for w in MATERIAL_WORDS}
_P_SET = {w.lower(): w for w in PLACE_WORDS}
_A_SET = {w.lower(): w for w in ATMOS_WORDS}
_O_SET = {w.lower(): w for w in OBJECT_WORDS}
_D_SET = {w.lower(): w for w in DETAIL_WORDS}

# Global, per-process hints. Service should refresh these before calling fallback.
_COOLDOWN_SET: set[str] = set()
_COOLDOWN_LAST7: set[str] = set()
_HINT_RECENT_STRUCTURES: list[str] = []
_HINT_RECENT_ROLES: list[str] = []


def set_fallback_cooldown(cooldown_words: Iterable[str], last7_words: Iterable[str] | None = None) -> None:
    global _COOLDOWN_SET, _COOLDOWN_LAST7
    _COOLDOWN_SET = {str(w).lower() for w in cooldown_words if str(w).strip()}
    _COOLDOWN_LAST7 = {str(w).lower() for w in (last7_words or []) if str(w).strip()}


def set_fallback_hints(recent_structures: list[str] | None = None, recent_roles: list[str] | None = None) -> None:
    global _HINT_RECENT_STRUCTURES, _HINT_RECENT_ROLES
    _HINT_RECENT_STRUCTURES = list(recent_structures or [])
    _HINT_RECENT_ROLES = list(recent_roles or [])


def _canonical_from_role_sets(token: str) -> tuple[str | None, str | None]:
    """
    Return (role, canonical_word) if token matches a known role vocabulary.
    role is one of: M, P, A, O, D, or None.
    """
    t = token.lower()
    if t in _M_SET:
        return "M", _M_SET[t]
    if t in _P_SET:
        return "P", _P_SET[t]
    if t in _A_SET:
        return "A", _A_SET[t]
    if t in _O_SET:
        return "O", _O_SET[t]
    if t in _D_SET:
        return "D", _D_SET[t]
    return None, None


_ROLE_SYNONYMS: dict[str, dict[str, list[str]]] = {
    "P": {
        "atrium": ["Corridor", "Hallway", "Gallery"],
        "quay": ["Landing", "Dock", "Entryway"],
        "harbor": ["Dock", "Shoreline", "Promenade"],
        "rooftop": ["Landing", "Loft", "Workshop"],
        "courtyard": ["Gallery", "Passage", "Arcade"],
        "studio": ["Workshop", "Booth", "Backroom"],
    },
    "A": {
        "rain": ["Haze", "Condensation", "Mist", "Drift"],
        "dusk": ["Afterglow", "Dimlight", "Gloom"],
        "dawn": ["Dew", "Glare", "Foglight"],
        "glow": ["Afterglow", "Glare", "Foglight"],
        "mist": ["Haze", "Foglight", "Condensation"],
    },
    "M": {
        "glass": ["Chrome", "Enamel", "Tile"],
        "stone": ["Slate", "Basalt", "Travertine"],
        "granite": ["Basalt", "Slate", "Travertine"],
        "marble": ["Travertine", "Tile", "Plaster"],
        "copper": ["Brass", "Tin", "Chrome"],
    },
    "O": {
        "vinyl": ["Record", "Sleeve", "Needle"],
        "turntable": ["Plinth", "Needle", "Dial"],
        "speaker": ["Dial", "Switch", "Lamp"],
        "map": ["Notebook", "Tape", "Spool"],
        "case": ["Sleeve", "Tape", "Notebook"],
    },
}


def _cooling_pick(
    rnd,
    pool: list[str],
    used_local: set[str],
    prefer_not_in_last7: bool = True,
    token_first: Optional[list[str]] = None,
) -> tuple[str | None, bool]:
    """
    Deterministic cooling-aware selection.

    Returns: (word | None, cooldown_break)
    """
    token_first = token_first or []

    def _candidates(p: list[str], allow_cooldown: bool, allow_last7: bool) -> list[str]:
        out: list[str] = []
        for w in p:
            lw = w.lower()
            if lw in used_local:
                continue
            if not allow_cooldown and lw in _COOLDOWN_SET:
                continue
            if prefer_not_in_last7 and not allow_last7 and lw in _COOLDOWN_LAST7:
                continue
            out.append(w)
        return out

    # 1) Prefer token-derived candidates (already canonicalized) if they are not cooled.
    if token_first:
        c = _candidates(token_first, allow_cooldown=False, allow_last7=False)
        if c:
            choice = rnd.choice(c)
            used_local.add(choice.lower())
            return choice, False

    # 2) Pick from pool avoiding cooldown and last7.
    c = _candidates(pool, allow_cooldown=False, allow_last7=False)
    if c:
        choice = rnd.choice(c)
        used_local.add(choice.lower())
        return choice, False

    # 3) Relax: allow words in cooldown set but avoid last7.
    c = _candidates(pool, allow_cooldown=True, allow_last7=False)
    if c:
        choice = rnd.choice(c)
        used_local.add(choice.lower())
        return choice, True

    # 4) Relax: allow anything not used locally.
    c = _candidates(pool, allow_cooldown=True, allow_last7=True)
    if c:
        choice = rnd.choice(c)
        used_local.add(choice.lower())
        return choice, True

    return None, True


def _infer_token_role_candidates(tokens: list[str]) -> dict[str, list[str]]:
    """
    Partition cleaned tokens into role candidates.
    Each candidate list contains canonical Title Case words when matched to known vocab.
    """
    out: dict[str, list[str]] = {"M": [], "P": [], "A": [], "O": [], "D": []}
    for t in tokens:
        role, canon = _canonical_from_role_sets(t)
        if role and canon:
            out[role].append(canon)
    # Deduplicate while preserving order.
    for k in out:
        seen: set[str] = set()
        unique: list[str] = []
        for w in out[k]:
            lw = w.lower()
            if lw in seen:
                continue
            seen.add(lw)
            unique.append(w)
        out[k] = unique
    return out


def _transform_blocked_token(role: str, token: str, rnd) -> list[str]:
    """
    If a token word is cooled, propose deterministic physical alternatives.
    """
    lt = token.lower()
    options = _ROLE_SYNONYMS.get(role, {}).get(lt, [])
    if not options:
        return []
    # Deterministic order: shuffle with rnd.
    opts = options[:]
    rnd.shuffle(opts)
    return opts


def _choose_template(rnd, token_rich: bool) -> list[str]:
    """
    Choose a slot template. Bias toward 4–6 words to avoid 3-word domination.
    """
    # Primary (4 words)
    templates_4 = [
        ["M", "P", "A", "O"],
        ["M", "O", "P", "A"],
        ["O", "M", "P", "A"],
        ["M", "P", "O", "A"],
        # Variety (still 4 roles, different lead)
        ["P", "M", "A", "O"],
        ["O", "P", "M", "A"],
    ]

    # Secondary/minority (3 words)
    templates_3 = [
        ["M", "P", "A"],
        ["M", "O", "P"],
        ["O", "M", "P"],
    ]

    # Occasional longer (5–6 words) using one connector + detail.
    templates_5 = [
        ["M", "P", "A", "Through", "D"],
        ["M", "O", "P", "Near", "D"],
        ["O", "M", "P", "Under", "D"],
        ["M", "P", "A", "At", "D"],
    ]
    templates_6 = [
        ["O", "M", "P", "A", "Near", "D"],
        ["M", "O", "P", "A", "Through", "D"],
    ]

    candidates: list[tuple[list[str], float]] = []

    def _sig_roles(tpl: list[str]) -> str:
        roles = [t for t in tpl if t in {"M", "P", "A", "O"}]
        return " ".join(roles) if roles else "UNKNOWN"

    def _leading_role(tpl: list[str]) -> str:
        for t in tpl:
            if t in {"M", "P", "A", "O"}:
                return t
        return "UNKNOWN"

    def _count(hay: list[str], needle: str) -> int:
        return sum(1 for x in hay if str(x).strip() == needle)

    # Base weights: heavily favor 4–6 words; keep 3-word templates as a minority.
    for tpl in templates_4:
        candidates.append((tpl, 20.0))
    for tpl in templates_3:
        candidates.append((tpl, 2.0))
    for tpl in templates_5:
        candidates.append((tpl, 6.0 if token_rich else 2.0))
    if token_rich:
        for tpl in templates_6:
            candidates.append((tpl, 3.0))

    # Soft penalties for recent structures/leading roles to force rotation.
    weighted: list[tuple[list[str], float]] = []
    for tpl, base_w in candidates:
        sig = _sig_roles(tpl)
        lead = _leading_role(tpl)

        struct_count = _count(_HINT_RECENT_STRUCTURES, sig)
        role_count = _count(_HINT_RECENT_ROLES, lead)

        # Penalize but never fully ban.
        # Gentle decay: diversify without collapsing into mostly 3-word titles.
        w = base_w * (0.80 ** struct_count) * (0.90 ** role_count)
        weighted.append((tpl, max(0.05, w)))

    total = sum(w for _, w in weighted)
    if total <= 0:
        return rnd.choice(templates_4)

    pick = rnd.random() * total
    acc = 0.0
    for tpl, w in weighted:
        acc += w
        if acc >= pick:
            return tpl
    return weighted[-1][0]


def _render_template(template: list[str], slots: dict[str, str | None]) -> str:
    words: list[str] = []
    for s in template:
        if s in {"M", "P", "A", "O", "D"}:
            v = slots.get(s)
            if v:
                words.append(v)
        elif s in CONNECTORS:
            words.append(s)
        else:
            # Unknown token: ignore
            continue
    return " ".join(words).strip()


def fallback_album_title(
    tokens: list[str],
    seed: str,
    forbidden_words: Iterable[str] | None = None,  # kept for backward compat; ignored
    min_words: int = 3,
    max_words: int = 7,
) -> str:
    rnd = seeded_random(seed + "|fallback")

    cleaned = clean_tokens(tokens)
    token_candidates = _infer_token_role_candidates(cleaned)
    token_rich = len(cleaned) >= 4

    used_local: set[str] = set()
    cooldown_break = False

    # Pick per-role words with cooling-aware selection.
    # If token candidate is cooled, attempt role-specific transforms first.
    slots: dict[str, str | None] = {"M": None, "P": None, "A": None, "O": None, "D": None}

    def _pick_role(role: str, pool: list[str]) -> None:
        nonlocal cooldown_break
        t_candidates = token_candidates.get(role, [])
        # If token candidates exist but are cooled, try transformed alternatives.
        transformed: list[str] = []
        for t in t_candidates:
            if t.lower() in _COOLDOWN_SET or t.lower() in _COOLDOWN_LAST7:
                transformed.extend(_transform_blocked_token(role, t, rnd))
        # token_first order: transformed first, then original token candidates.
        token_first = transformed + t_candidates
        choice, broke = _cooling_pick(rnd, pool, used_local, token_first=token_first)
        cooldown_break = cooldown_break or broke
        slots[role] = choice

    _pick_role("M", MATERIAL_WORDS)
    _pick_role("P", PLACE_WORDS)
    _pick_role("A", ATMOS_WORDS)
    _pick_role("O", OBJECT_WORDS)
    _pick_role("D", DETAIL_WORDS)

    template = _choose_template(rnd, token_rich=token_rich)
    title = _render_template(template, slots)

    # Enforce min/max word count by trimming and (rarely) extending.
    words = title.split()
    if len(words) > max_words:
        words = words[:max_words]
    title = " ".join(words)

    ok, _ = validate_album_title_physical(title, min_words=min_words, max_words=max_words)
    if not ok:
        # One deterministic repair attempt, without token anchoring.
        rnd2 = seeded_random(seed + "|fallback|repair")
        used_local.clear()
        slots = {"M": None, "P": None, "A": None, "O": None, "D": None}
        cooldown_break = False
        slots["M"], b1 = _cooling_pick(rnd2, MATERIAL_WORDS, used_local)
        slots["P"], b2 = _cooling_pick(rnd2, PLACE_WORDS, used_local)
        slots["A"], b3 = _cooling_pick(rnd2, ATMOS_WORDS, used_local)
        slots["O"], b4 = _cooling_pick(rnd2, OBJECT_WORDS, used_local)
        slots["D"], b5 = _cooling_pick(rnd2, DETAIL_WORDS, used_local)
        cooldown_break = b1 or b2 or b3 or b4 or b5
        template = _choose_template(rnd2, token_rich=True)
        title = _render_template(template, slots)
        words = title.split()
        if len(words) > max_words:
            title = " ".join(words[:max_words])
        ok, _ = validate_album_title_physical(title, min_words=min_words, max_words=max_words)

    if not ok:
        title = "Bronze Studio Cabinet"

    if cooldown_break:
        log_warning("fallback cooldown_break (reused recent core word due to exhaustion)")

    return title
