#!/usr/bin/env python3
# coding: utf-8
"""独立内容检测门 —— 只看成片音频,严格放行(2026-08-17 用户令)。

「独立」的含义:本门对**渲染出的 VO 成品**重新转写,检查听者实际听到的
内容;出片器的编排计划、选段逻辑、任何中间产物都不参与判断。它从
session.json 拿的只有两样:音频路径,和「本期主题经文」这一句声明
(声明也要被音频验证,而不是反过来)。

六项检查,全部达标才放行;任何一项不过,本期作废重排:
  G1 块完整   每个发声块(≥6s 静默为界)首字成头、尾有交代 —— 听得懂在说什么
  G2 稀疏     块间距全部 ≥10s 且中位 ≥16s —— 语音必须疏,呼吸感是产品本体
  G3 语音占比 VO 区 ≤60%、全片 ≤40% —— 节制表达,音乐与静默是主角
  G4 一处经文 音频中听到的经文引用全部属于本期声明的主题集,且主经文确被读出
  G5 无混乱   无重复块、无孤词块、块数在节制范围(5–16)
  G6 语速     全局 0.5–2.8 词/秒 —— 睡眠向朗读的合理区间

放行时,本门的转写(真实成品时间戳)回填 session.json 的 plan 并产出
英文 SRT —— 字幕与视频文字直接来自成片音频,音画错位从结构上不可能。

  KMP_DUPLICATE_LIB_OK=TRUE ./.venv/bin/python scripts/sg/content_gate.py \\
      --session ~/Studio/Workspace/outputs/sg/sessions/sg_mol_001
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_session import build_srt                      # noqa: E402
from harvest_whisper import resolve_model, span_phrases, to_wav16k  # noqa: E402
from molecule_quality import text_complete                # noqa: E402
from sg_media import probe_duration                       # noqa: E402

WORK = Path.home() / "Studio/Workspace/temp/sg_content_gate"

# ── 门槛 ──
# 听感分块阈值 10s 的依据:母带内部停顿实测最长 7.9s(1914 个停顿中
# ≥10s 者为零),而出片器块间距下限 16s —— 10s 恰在两者之间,合并型
# 分子(内含 6–8s 长停)不会被误拆,出片间距必然成为块界。
BLOCK_SPLIT = 10.0
MIN_BLOCK_GAP = 14.0     # 任何两块之间至少 14s(设计值 16s 留 2s 容差)
MIN_MEDIAN_GAP = 20.0    # 块间距中位数至少 20s
MAX_SPEECH_RATIO_VO = 0.60
MAX_SPEECH_RATIO_ALL = 0.40
BLOCKS_MIN, BLOCKS_MAX = 5, 16
RATE_MIN, RATE_MAX = 0.5, 2.8

BOOKS = ("Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|"
         "Samuel|Kings|Chronicles|Ezra|Nehemiah|Esther|Job|Psalms?|Proverbs|"
         "Ecclesiastes|Song of Solomon|Isaiah|Jeremiah|Lamentations|Ezekiel|"
         "Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|"
         "Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|"
         "Romans|Corinthians|Galatians|Ephesians|Philippians|Colossians|"
         "Thessalonians|Timothy|Titus|Philemon|Hebrews|James|Peter|Jude|"
         "Revelation")
REF_RE = re.compile(rf"\b({BOOKS})\b", re.IGNORECASE)


def norm_book(s: str) -> str:
    return s.lower().rstrip("s") if s.lower().startswith("psalm") else s.lower()


def group_blocks(utts: list[tuple[float, float, str]]
                 ) -> list[dict]:
    """转写条目按 ≥BLOCK_SPLIT 的间隙聚成「听感块」。"""
    blocks: list[dict] = []
    for t0, t1, tx in utts:
        if blocks and t0 - blocks[-1]["end"] < BLOCK_SPLIT:
            b = blocks[-1]
            b["end"] = t1
            b["speech"] += t1 - t0
            b["text"] += " " + tx
            b["utts"].append((t0, t1, tx))
        else:
            blocks.append({"start": t0, "end": t1, "speech": t1 - t0,
                           "text": tx, "utts": [(t0, t1, tx)]})
    return blocks


def judge(blocks: list[dict], vo_ends: float, total: float,
          claimed: list[str], primary: str) -> dict:
    checks: dict[str, dict] = {}

    bad = [i for i, b in enumerate(blocks) if text_complete(b["text"])]
    checks["G1_blocks_complete"] = {
        "pass": not bad,
        "detail": [f"块{i}: [{text_complete(blocks[i]['text'])}] "
                   f"「{blocks[i]['text'][:60]}」" for i in bad]}

    gaps = [round(blocks[i + 1]["start"] - blocks[i]["end"], 1)
            for i in range(len(blocks) - 1)]
    med = sorted(gaps)[len(gaps) // 2] if gaps else 0.0
    checks["G2_sparse"] = {
        "pass": bool(gaps) and min(gaps) >= MIN_BLOCK_GAP and med >= MIN_MEDIAN_GAP,
        "detail": f"块间距 min={min(gaps) if gaps else 0}s 中位={med}s "
                  f"(门槛 ≥{MIN_BLOCK_GAP}/{MIN_MEDIAN_GAP})"}

    speech = sum(b["speech"] for b in blocks)
    r_vo = speech / vo_ends if vo_ends else 1.0
    r_all = speech / total if total else 1.0
    checks["G3_speech_ratio"] = {
        "pass": r_vo <= MAX_SPEECH_RATIO_VO and r_all <= MAX_SPEECH_RATIO_ALL,
        "detail": f"VO 区 {r_vo:.0%}(≤{MAX_SPEECH_RATIO_VO:.0%}) · "
                  f"全片 {r_all:.0%}(≤{MAX_SPEECH_RATIO_ALL:.0%})"}

    all_text = " ".join(b["text"] for b in blocks)
    heard = {norm_book(m.group(1)) for m in REF_RE.finditer(all_text)}
    # claimed 是库级实测的书卷表(采集时对母带全文量出),不是编排的产物;
    # 门用它当白名单,但主经文仍必须在音频里真实读出。
    allowed = {norm_book(b) for b in claimed} if claimed else set()
    prim_books = {norm_book(m.group(1)) for m in REF_RE.finditer(primary)}
    foreign = heard - allowed
    checks["G4_one_scripture"] = {
        "pass": not foreign and bool(heard & prim_books),
        "detail": f"听到 {sorted(heard)} · 声明 {sorted(allowed)} · "
                  f"越界 {sorted(foreign) or '无'} · 主经文读出 {bool(heard & prim_books)}"}

    norm = [re.sub(r"\W+", " ", b["text"].lower()).strip() for b in blocks]
    dups = [t[:50] for i, t in enumerate(norm) if t in norm[:i]]
    orphans = [b["text"] for b in blocks
               if len(b["text"].split()) < 2
               and "amen" not in b["text"].lower()]
    checks["G5_no_confusion"] = {
        "pass": not dups and not orphans and BLOCKS_MIN <= len(blocks) <= BLOCKS_MAX,
        "detail": f"块数 {len(blocks)}({BLOCKS_MIN}–{BLOCKS_MAX}) · "
                  f"重复 {dups or '无'} · 孤词 {orphans or '无'}"}

    words = len(all_text.split())
    rate = words / speech if speech else 0.0
    checks["G6_pace"] = {
        "pass": RATE_MIN <= rate <= RATE_MAX,
        "detail": f"{rate:.2f} 词/秒({RATE_MIN}–{RATE_MAX})"}

    return {"pass": all(c["pass"] for c in checks.values()), "checks": checks,
            "blocks": len(blocks), "speech_sec": round(speech, 1),
            "judged_at": datetime.now(timezone.utc).isoformat()}


# 品牌名与常见转写听差的规范表 —— 只修**显示文本**(字幕/视频文字),
# 判定(G1–G6)一律用原始转写;音频本身没错,是 whisper 听差。
CANON = [
    (re.compile(r"\bSleep\s+and\s+Grace\b", re.IGNORECASE), "Sleep in Grace"),
]


def canon_text(t: str) -> str:
    for pat, rep in CANON:
        t = pat.sub(rep, t)
    return t


def utterance_plan(blocks: list[dict]) -> list[dict]:
    """转写条目 → 渲染器/字幕用的 plan(真实成品时间戳)。

    source_sequence_index 的连号规则复用 build_srt 的续句判定:块内间隙
    ≤2.5s 视为同句被停顿切开(小写续排),更大间隙或跨块则断号。
    """
    plan: list[dict] = []
    seq = 0
    for bi, b in enumerate(blocks):
        prev_end = None
        for t0, t1, tx in b["utts"]:
            seq += 1 if (prev_end is not None and t0 - prev_end <= 2.5) else 10
            plan.append({
                "slot": f"BLOCK_{bi:02d}", "type": "atom",
                "id": f"utt_{len(plan):03d}", "role": "molecule",
                "text": canon_text(tx),
                "vo_start_sec": round(t0, 3), "vo_end_sec": round(t1, 3),
                "start_sec": round(t0, 3), "end_sec": round(t1, 3),
                "duration_sec": round(t1 - t0, 3),
                "pad_after_sec": 0.0,
                "source_master": "content_gate_transcript",
                "source_sequence_index": seq,
            })
            prev_end = t1
    return plan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", type=Path, required=True)
    ap.add_argument("--report-only", action="store_true",
                    help="只判不写(不回填 plan/不出 SRT)")
    a = ap.parse_args()
    sdir = a.session.expanduser()
    eid = sdir.name
    meta_path = sdir / f"{eid}_session.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    vo = Path(meta["paths"]["vo"])
    claimed = (meta.get("scripture_books_allowed")
               or [m.group(1) for ref in (meta.get("scriptures") or [])
                   for m in [REF_RE.search(ref)] if m])
    primary = meta.get("primary_scripture") or ""

    WORK.mkdir(parents=True, exist_ok=True)
    model = resolve_model(None)
    wav = to_wav16k(vo, WORK / f"{eid}_vo.wav")
    utts = span_phrases(wav, model, WORK, min_sil=0.8, pad=0.12,
                        min_speech=0.4)
    total = meta.get("total_duration_sec") or probe_duration(vo) or 0.0
    vo_ends = meta.get("vo_ends_sec") or total
    blocks = group_blocks(utts)
    verdict = judge(blocks, vo_ends, total, claimed, primary)

    print(f"═══ 内容门 · {eid} ═══")
    for name, c in verdict["checks"].items():
        mark = "✅" if c["pass"] else "❌"
        print(f" {mark} {name}")
        det = c["detail"]
        for line in (det if isinstance(det, list) else [det]):
            print(f"     {line}")

    meta["content_gate"] = verdict
    if verdict["pass"] and not a.report_only:
        plan = utterance_plan(blocks)
        meta["molecule_plan"] = meta.get("plan")
        meta["plan"] = plan
        srt = sdir / f"{eid}.srt"
        srt.write_text(build_srt(plan), encoding="utf-8")
        meta["paths"]["srt"] = str(srt)
        print(f"✅ 放行:plan 回填 {len(plan)} 条转写 · 字幕 {srt.name}")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    if not verdict["pass"]:
        print("⛔ 不放行 —— 本期作废,换种子重排")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
