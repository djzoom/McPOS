#!/usr/bin/env python3
# coding: utf-8
"""按原子忠实度重建十期台词 — 只有原子库,没有 TTS,文本必须迁就音频。

模型:**一个原子 = 一句台词 = 一条字幕**。原子边界就是 Locke 录音里的自然
停顿,在原子内部切音频既无词级时间戳支撑,也会破坏呼吸感。

因此只允许两种不改变声音的操作:
  DROP  丢弃坏原子(重复、转写变体、动词悬空、词组重叠、CTA)
  FIX   排版修正(首字母大写、补句末标点、经文 31.6 → 31:6、去多余空格)

不允许:加词、换词、跨原子合并、原子内切分。

  ./.venv/bin/python scripts/sg/rebuild_atom_faithful.py --episodes 1
  ./.venv/bin/python scripts/sg/rebuild_atom_faithful.py --all
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

BD = Path.home() / ("Studio/Workspace/outputs/sg/sessions/"
                    "sg_toytune_ep1/text_batch_10")
OUT = BD / "atom_faithful"

BOOKS = ("Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|"
         "Samuel|Kings|Job|Psalms?|Proverbs|Ecclesiastes|Isaiah|Jeremiah|"
         "Lamentations|Ezekiel|Daniel|Hosea|Joel|Micah|Zephaniah|Zechariah|"
         "Malachi|Matthew|Mark|Luke|John|Acts|Romans|Corinthians|Galatians|"
         "Ephesians|Philippians|Colossians|Thessalonians|Timothy|Titus|"
         "Hebrews|James|Peter|Jude|Revelation")

TRANSITIVE_DANGLE = {"abandon", "abandons", "forsake", "forsakes",
                     "carry", "carries", "bring", "brings"}
# 2026-08-05 复审:46.5% 的原子音频里只有 1-2 个词,且多数时长很长
# (7.5s 只说了 "Lord.")—— 它们是长静默里挂着零星词的片段,不是台词。
MIN_WORDS = 3
# 语速下限已废除 —— 助眠频道的缓慢朗读与大间隔是刻意效果,不是缺陷
#（详见 atom_quality 模块头）
CTA = re.compile(r"\b(subscribe|comment|like this video|share this|"
                 r"turn on notifications|link in)", re.I)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def typographic_fix(t: str) -> str:
    """只动排版,不动词。"""
    t = " ".join(t.split())
    # 经文引用 31.6 → 31:6(仅书卷名后)
    t = re.sub(rf"\b({BOOKS})\s+(\d+)\.(\d+)", r"\1 \2:\3", t)
    # 句中孤立的大写接续词 → 小写(转写把一句切两半的痕迹)
    t = re.sub(r"(?<=[a-z],) (As|And|But|So|When|Then|That)\b",
               lambda m: " " + m.group(1).lower(), t)
    if t and t[0].islower():
        t = t[0].upper() + t[1:]
    if t and t[-1] not in ".!?,;:—-":
        t += "."
    return t


def defect(t: str, seen: dict, idx: int, dur: float = 0.0) -> str | None:
    """判定该原子是否必须丢弃;返回原因,None 表示保留。"""
    n = norm(t)
    if not n:
        return "空文本"
    nwords = len(n.split())
    if nwords < MIN_WORDS:
        return f"词片({nwords} 词)"
    if CTA.search(t):
        return "CTA"
    # 完全重复 / 转写变体(词集合高度重合且长度相近)
    if n in seen:
        return f"与第 {seen[n]} 条完全重复"
    # 转写变体 ≠ 排比。排比("You are not too broken/weary")只差一个实词却
    # 是刻意修辞;真变体是同一句话的两次转写,差的是虚词(It's/There is)。
    nl = n.split()
    STOP = {"it", "its", "it's", "there", "is", "are", "was", "the", "a", "an",
            "that", "this", "of", "to", "and", "you", "your", "i", "my", "he",
            "his", "we", "our", "in", "on", "at", "be", "do", "no", "not"}
    # 缩写被规范化后会留下单字母残片(It's → it s),不算实词
    core = [w for w in nl if w not in STOP and len(w) > 1]
    for prev, j in seen.items():
        pl = prev.split()
        pcore = [w for w in pl if w not in STOP and len(w) > 1]
        if len(core) < 3 or len(pcore) < 3:
            continue
        # 实词序列完全一致 → 同一句的两次转写(虚词不同不算新内容)
        if core == pcore and nl != pl:
            return f"与第 {j} 条为转写变体"
    # 及物动词悬空(宾语掉在别的原子里)
    m = re.search(r"\b(\w+)[.!?]?$", t.strip())
    if m and m.group(1).lower() in TRANSITIVE_DANGLE:
        if not re.search(r"\b(we|you|they|i)\s+\w+\W*$", t, re.I):
            return f"及物动词「{m.group(1)}」悬空"
    # 词组重叠("the burdens the burdens")
    if re.search(r"\b(\w+\s+\w+)\s+\1\b", t, re.I):
        return "词组重叠"
    return None


def load_manifest_text() -> dict[str, str]:
    """manifest 是文本的唯一权威 —— 剧本源文件里的 text 是生成时的快照,
    重标注(audit_atom_library.py --relabel)不会传导过去,必须在此覆盖。"""
    man = json.loads((Path.home() /
                      "Studio/Library/sg/atoms/manifest.json").read_text())
    return {a["id"]: a["text"] for a in man["atoms"] if a.get("text")}


def rebuild(n: int) -> dict:
    src = json.loads((BD / f"sg_text_ep{n:02d}.json").read_text())
    authoritative = load_manifest_text()
    atoms = []
    for a in src["plan"]:
        t = authoritative.get(a["id"])
        atoms.append({**a, "text": t} if t else a)
    stale = sum(1 for a, b in zip(src["plan"], atoms) if a["text"] != b["text"])
    if stale:
        print(f"     (从 manifest 刷新了 {stale} 条陈旧文本)")
    kept, dropped, seen = [], [], {}
    for i, a in enumerate(atoms):
        why = defect(a["text"], seen, i, a.get("duration_sec", 0.0))
        if why:
            dropped.append({"id": a["id"], "text": a["text"][:70], "why": why})
            continue
        seen[norm(a["text"])] = i
        kept.append({"id": a["id"], "section": a["section"],
                     "path": a["path"], "duration_sec": a["duration_sec"],
                     "text": typographic_fix(a["text"])})

    # 收尾必须是 Amen —— 若被丢或缺失,从原子里补一条真实的 Amen
    def is_amen(t): return norm(t) in ("amen",)
    if not kept or not is_amen(kept[-1]["text"]):
        amen = next((a for a in reversed(atoms) if is_amen(a["text"])), None)
        if amen:
            kept = [k for k in kept if not is_amen(k["text"])]
            kept.append({"id": amen["id"], "section": "closing",
                         "path": amen["path"],
                         "duration_sec": amen["duration_sec"], "text": "Amen."})

    dur = sum(k["duration_sec"] for k in kept)
    return {"episode_id": src["episode_id"],
            "perspective": src["qa"]["perspective"],
            "source_atoms": len(atoms), "kept": len(kept),
            "dropped": dropped, "audio_sec": round(dur, 1), "plan": kept}


def render_md(r: dict) -> str:
    out = [f"# {r['episode_id']} · atom-faithful", "",
           "每句 = 一个真实录音原子;只做了丢弃与排版修正,未加改任何词。  ",
           f"Perspective: `{r['perspective']}`  ",
           f"Atoms: `{r['kept']}` / {r['source_atoms']}(丢弃 {len(r['dropped'])})  ",
           f"Audio: `{r['audio_sec'] / 60:.1f}` 分钟", ""]
    for sec, title in (("opening", "Opening"), ("prayer", "Prayer"),
                       ("closing", "Closing")):
        seg = [k["text"] for k in r["plan"] if k["section"] == sec]
        if seg:
            out += [f"## {title}", "", " ".join(seg), ""]
    if r["dropped"]:
        out += ["## Dropped atoms", ""]
        out += [f"- `{d['id']}` — {d['why']} — {d['text']}" for d in r["dropped"]]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int)
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    nums = range(1, 11) if a.all else [a.episodes or 1]
    OUT.mkdir(exist_ok=True)

    tot_a = tot_d = 0
    for n in nums:
        r = rebuild(n)
        r["generated_at"] = datetime.now(timezone.utc).isoformat()
        (OUT / f"sg_text_ep{n:02d}.json").write_text(
            json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        (OUT / f"sg_text_ep{n:02d}.md").write_text(render_md(r), encoding="utf-8")
        tot_a += r["kept"]
        tot_d += len(r["dropped"])
        print(f"✅ ep{n:02d}  保留 {r['kept']:3d} / {r['source_atoms']:3d} 原子"
              f"(丢弃 {len(r['dropped']):2d})  音频 {r['audio_sec']/60:.1f} 分")
    print(f"\n合计 {tot_a} 原子,丢弃 {tot_d};全部为真实录音,零合成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
