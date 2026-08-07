#!/usr/bin/env python3
# coding: utf-8
"""Generate text-only, atom-sourced SiG episodes and gate their quality.

Each episode uses one source master as its ordered body backbone. Only a clean
brand opening and, when necessary, a closing atom may come from another master.
No prose is invented by this script.
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD_PATH = HERE / "build_session.py"
DEFAULT_ATOMS = Path.home() / "Studio/Library/sg/atoms"


def _load_builder():
    spec = importlib.util.spec_from_file_location("sg_build_session", BUILD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {BUILD_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


B = _load_builder()

# The source masters themselves establish the prayer voice. First-person shifts
# inside cited scripture are tracked separately and do not change that voice.
PERSPECTIVE_RULES = [
    (r"0906Fall_Asleep", "singular"),
    (r"0908_Peace", "singular"),
    (r"God_Is_Still_Speaking", "plural"),
    (r"Peace_Beyond_Understanding", "singular"),
    (r"Rest_Secure", "plural"),
    (r"Isaiah26_Philippians4", "plural"),
    (r"John10_Psalm62", "plural"),
    (r"Psalm121_Lamentations3", "plural"),
    (r"Psalm16_Matthew28", "plural"),
    (r"Welcome_to_Sleep_in_Grace", "plural"),
]

SCRIPTURE_CUE_RE = re.compile(
    r"\b(?:psalm|isaiah|john|matthew|philippians|deuteronomy|romans|scripture|"
    r"verse|jesus said|the word of god|your word says|declares|says,)\b",
    re.I,
)
SCRIPTURE_QUOTE_RE = re.compile(
    r"\b(?:I am with you|I will strengthen you|I will uphold you|I give them eternal life|"
    r"I have set the Lord|I will not be shaken|I lay down and slept|I will fear no evil|"
    r"my refuge and my fortress|my help comes from the Lord|make me dwell in safety|"
    r"the Lord is my shepherd|makes? me lie down|leads? me beside|restores? my soul|"
    r"valley of the shadow of death|they comfort me|I am gentle and lowly|my yoke is easy|"
    r"my burden is light|for you are with me|in whom I trust)\b",
    re.I,
)


def perspective_for(source: str) -> str:
    name = Path(source).name
    for pattern, perspective in PERSPECTIVE_RULES:
        if re.search(pattern, name, re.I):
            return perspective
    raise ValueError(f"No perspective rule for {name}")


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", text or "")


def is_repetitive_atom(text: str) -> bool:
    tokens = re.findall(r"[a-z]+|\d+", (text or "").lower())
    if len(tokens) < 6:
        return False
    trigrams = [tuple(tokens[i:i + 3]) for i in range(len(tokens) - 2)]
    if max(collections.Counter(trigrams).values(), default=0) >= 2:
        return True
    fourgrams = [tuple(tokens[i:i + 4]) for i in range(len(tokens) - 3)]
    repeated_phrase = max(collections.Counter(fourgrams).values(), default=0) >= 2
    low_variety = len(set(tokens)) / len(tokens) < 0.32
    return repeated_phrase or low_variety


def is_quote_context(atoms: list, index: int) -> bool:
    atom = atoms[index]
    text = atom.text or ""
    if atom.role == "scripture" or SCRIPTURE_CUE_RE.search(text) or SCRIPTURE_QUOTE_RE.search(text):
        return True
    for prior in atoms[max(0, index - 3):index]:
        if SCRIPTURE_CUE_RE.search(prior.text or ""):
            return True
    return False


def best_brand(atoms: list):
    exact = [a for a in atoms if (a.text or "").strip().lower() == "welcome to sleep in grace."]
    if not exact:
        raise RuntimeError("Atom library has no exact brand opening")
    return min(exact, key=lambda atom: (atom.duration_sec, atom.id))


def best_amen(atoms: list):
    exact = [a for a in atoms if re.sub(r"[^a-z]", "", (a.text or "").lower()) == "amen"]
    if not exact:
        raise RuntimeError("Atom library has no single Amen closing")
    return min(exact, key=lambda atom: (atom.duration_sec, atom.id))


def plan_item(atom, section: str) -> dict:
    item = asdict(atom)
    item["path"] = str(atom.path)
    item["section"] = section
    return item


def clean_source(source_atoms: list, all_atoms: list) -> tuple[list[dict], dict]:
    source_atoms = sorted(source_atoms, key=lambda atom: (atom.t_start, atom.t_end, atom.id))
    source = source_atoms[0].source_master
    perspective = perspective_for(source)
    brand = next(
        (a for a in source_atoms if (a.text or "").strip().lower() == "welcome to sleep in grace."),
        best_brand(all_atoms),
    )
    invitation = next(
        (a for a in source_atoms[:12] if "invited to rest" in (a.text or "").lower()),
        None,
    )

    closing_candidates = [
        a for a in source_atoms
        if B.is_strong_close_text(a.text or "")
        and B.matches_perspective(a.text or "", perspective)
        and not is_repetitive_atom(a.text or "")
    ]
    exact_amens = [
        a for a in closing_candidates
        if re.sub(r"[^a-z]", "", (a.text or "").lower()) == "amen"
    ]
    closing = exact_amens[-1] if exact_amens else best_amen(all_atoms)

    plan: list[dict] = [plan_item(brand, "opening")]
    seen = {B.normalize_atom_text(brand.text or "")}
    if invitation and invitation.id != brand.id:
        norm = B.normalize_atom_text(invitation.text or "")
        if norm not in seen:
            plan.append(plan_item(invitation, "opening"))
            seen.add(norm)

    bad_repetition_atoms: list[str] = []
    quote_shift_atoms: list[str] = []
    perspective_atoms_removed: list[str] = []
    body: list = []
    body_word_count = 0
    duplicate_streak = 0
    seeking_clean_start = False
    paragraph_break_ids: set[str] = set()

    def rollback_incomplete_tail() -> None:
        nonlocal body_word_count
        while body:
            tail = (body[-1].text or "").strip()
            if tail.endswith((".", "!", "?")) and not B.is_orphan_fragment(tail):
                break
            body_word_count -= len(words(tail))
            body.pop()
    for index, atom in enumerate(source_atoms):
        text = atom.text or ""
        norm = B.normalize_atom_text(text)
        if atom.id in {brand.id, closing.id} or (invitation and atom.id == invitation.id):
            continue
        if B.is_brand_text(text) or B.is_cta_text(text):
            continue
        if is_repetitive_atom(text):
            bad_repetition_atoms.append(atom.id)
            rollback_incomplete_tail()
            seeking_clean_start = True
            continue
        if not norm or B.text_is_duplicate(text, seen):
            duplicate_streak += 1
            if duplicate_streak >= 3 and body_word_count >= 250:
                rollback_incomplete_tail()
                seeking_clean_start = True
            continue
        duplicate_streak = 0

        if B.is_strong_close_text(text) and len(words(text)) <= 6:
            continue

        singular, plural = B.first_person_profile(text)
        if singular and plural:
            perspective_atoms_removed.append(atom.id)
            rollback_incomplete_tail()
            seeking_clean_start = True
            continue
        mismatch = (perspective == "singular" and plural > 0) or (perspective == "plural" and singular > 0)
        if mismatch:
            if is_quote_context(source_atoms, index):
                quote_shift_atoms.append(atom.id)
            else:
                perspective_atoms_removed.append(atom.id)
                rollback_incomplete_tail()
                seeking_clean_start = True
                continue

        if seeking_clean_start:
            if B.is_orphan_fragment(text) or text[:1].islower():
                continue
            paragraph_break_ids.add(atom.id)
            seeking_clean_start = False

        body.append(atom)
        body_word_count += len(words(text))
        seen.add(norm)

    while body and B.is_orphan_fragment(body[-1].text or ""):
        repaired_by_context = False
        # Whisper may split a single closing prayer across many short atoms.
        # Walk back far enough to judge the whole source-contiguous sentence.
        for width in range(2, min(24, len(body)) + 1):
            tail = body[-width:]
            adjacent = all(
                tail[i].sequence_index == tail[i - 1].sequence_index + 1
                for i in range(1, len(tail))
            )
            combined = " ".join(atom.text or "" for atom in tail)
            if adjacent and not B.is_orphan_fragment(combined):
                repaired_by_context = True
                break
        if repaired_by_context:
            break
        body_word_count -= len(words(body[-1].text or ""))
        body.pop()

    for atom in body:
        item = plan_item(atom, "prayer")
        if atom.id in paragraph_break_ids:
            item["paragraph_break_before"] = True
        plan.append(item)
    close_norm = B.normalize_atom_text(closing.text or "")
    if close_norm in seen:
        closing = best_amen(all_atoms)
        close_norm = B.normalize_atom_text(closing.text or "")
    plan.append(plan_item(closing, "closing"))

    all_text = " ".join(str(item.get("text") or "") for item in plan)
    body_sources = {item["source_master"] for item in plan if item["section"] == "prayer"}
    body_indices = [item["sequence_index"] for item in plan if item["section"] == "prayer"]
    canonical = [B.normalize_atom_text(str(item.get("text") or "")) for item in plan]
    errors: list[str] = []
    if not plan or not B.is_brand_text(str(plan[0].get("text") or "")):
        errors.append("missing brand opening")
    if not B.is_strong_close_text(str(plan[-1].get("text") or "")):
        errors.append("missing strong closing")
    if len(body_sources) != 1:
        errors.append(f"body source count is {len(body_sources)}")
    if body_indices != sorted(body_indices):
        errors.append("body source order is not monotonic")
    if len(canonical) != len(set(canonical)):
        errors.append("duplicate canonical text remains")
    word_count = len(words(all_text))
    # Text-only QA accepts compact 2-minute prayers; audio duration is not part
    # of this stage and will be decided only after the text batch is approved.
    if word_count < 180:
        errors.append(f"too short: {word_count} words")
    if word_count > 2200:
        errors.append(f"too long: {word_count} words")

    qa = {
        "ok": not errors,
        "errors": errors,
        "perspective": perspective,
        "word_count": word_count,
        "atom_count": len(plan),
        "body_source": source,
        "source_order_monotonic": body_indices == sorted(body_indices),
        "canonical_duplicates": len(canonical) - len(set(canonical)),
        "cta_count": sum(B.is_cta_text(str(item.get("text") or "")) for item in plan),
        "repetitive_atoms_removed": bad_repetition_atoms,
        "quoted_pronoun_shifts": quote_shift_atoms,
        "perspective_atoms_removed": perspective_atoms_removed,
        "perspective_violations": [],
        "opening_text": plan[0]["text"],
        "closing_text": plan[-1]["text"],
    }
    return plan, qa


def render_markdown(episode_id: str, plan: list[dict], qa: dict) -> str:
    sections = {"opening": [], "prayer": [], "closing": []}
    for item in plan:
        text = " ".join(str(item.get("text") or "").split())
        if item.get("paragraph_break_before"):
            text = "\n\n" + text
        sections[item["section"]].append(text)
    source_name = Path(qa["body_source"]).name
    lines = [
        f"# {episode_id}",
        "",
        f"QA: `{'PASS' if qa['ok'] else 'FAIL'}`  ",
        f"Perspective: `{qa['perspective']}`  ",
        f"Words: `{qa['word_count']}`  ",
        f"Atoms: `{qa['atom_count']}`  ",
        f"Body source: `{source_name}`",
        "",
        "## Opening",
        "",
        " ".join(sections["opening"]),
        "",
        "## Prayer",
        "",
        " ".join(sections["prayer"]),
        "",
        "## Closing",
        "",
        " ".join(sections["closing"]),
        "",
        "## Atom provenance",
        "",
    ]
    lines.extend(
        f"- `{item['id']}` · `{item['section']}` · `{Path(item['source_master']).name}` · "
        f"`{item['t_start']:.3f}–{item['t_end']:.3f}`"
        for item in plan
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atoms-root", type=Path, default=DEFAULT_ATOMS)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--prefix", default="sg_text_ep")
    args = ap.parse_args()

    atoms = B.load_atoms(args.atoms_root / "manifest.json")
    grouped: dict[str, list] = collections.defaultdict(list)
    for atom in atoms:
        grouped[atom.source_master].append(atom)
    if len(grouped) < 10:
        raise RuntimeError(f"Need 10 source masters, found {len(grouped)}")

    args.out.mkdir(parents=True, exist_ok=True)
    episodes: list[dict] = []
    failures: list[dict] = []
    for number, (source, source_atoms) in enumerate(sorted(grouped.items()), 1):
        episode_id = f"{args.prefix}{number:02d}"
        plan, qa = clean_source(source_atoms, atoms)
        record = {
            "episode_id": episode_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "atom_library": str(args.atoms_root / "manifest.json"),
            "qa": qa,
            "plan": plan,
        }
        (args.out / f"{episode_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (args.out / f"{episode_id}.md").write_text(
            render_markdown(episode_id, plan, qa), encoding="utf-8"
        )
        summary = {
            "episode_id": episode_id,
            "ok": qa["ok"],
            "perspective": qa["perspective"],
            "word_count": qa["word_count"],
            "atom_count": qa["atom_count"],
            "body_source": Path(source).name,
            "errors": qa["errors"],
            "quoted_pronoun_shift_count": len(qa["quoted_pronoun_shifts"]),
            "perspective_atoms_removed": len(qa["perspective_atoms_removed"]),
            "repetitive_atoms_removed": len(qa["repetitive_atoms_removed"]),
        }
        episodes.append(summary)
        if not qa["ok"]:
            failures.append(summary)

    report = {
        "ok": not failures and len(episodes) == 10,
        "qualified_count": sum(item["ok"] for item in episodes),
        "requested_count": 10,
        "failures": failures,
        "episodes": episodes,
    }
    (args.out / "qa_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_lines = [
        "# SiG text-only batch QA",
        "",
        f"Overall: `{'PASS' if report['ok'] else 'FAIL'}`  ",
        f"Qualified: `{report['qualified_count']}/10`",
        "",
        "| Episode | QA | Perspective | Words | Atoms | Quote shifts | Perspective removed | Repetition removed |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    report_lines.extend(
        f"| [{item['episode_id']}]({item['episode_id']}.md) | {'PASS' if item['ok'] else 'FAIL'} | "
        f"{item['perspective']} | {item['word_count']} | {item['atom_count']} | "
        f"{item['quoted_pronoun_shift_count']} | {item['perspective_atoms_removed']} | "
        f"{item['repetitive_atoms_removed']} |"
        for item in episodes
    )
    (args.out / "README.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
