#!/usr/bin/env python3
# coding: utf-8
"""SiG 打磨稿翻译+SRT 管线 — 会话供稿,十道门禁裁判,单时间轴三语幕。

输入:polished/sg_text_epNN.json(五门已过的英文定稿,含分句表)
供稿:--zh 文件 {"opening":[...],"prayer":[...],"closing":[...]} 逐句 1:1
门禁:结构纯净/无英文残留/1:1 对齐/单数视角禁我们/经文书卷+章节数字/
      否定词保留/阿们收尾 —— 全过才落盘;OpenCC s2twp 生成繁体。
SRT:同一时间轴出 en / zh-CN / zh-TW 三份(字幕对齐同一条 VO);
     时轴为慢速祷告语速估算(0.48s/词+句间 1.5s,节间 3s,起始 10s),
     TTS 录出后用真实 VO 重对齐即可。

  ./.venv/bin/python scripts/sg/translate_polished.py --episodes 1 --zh <file>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from translate_text_batch import gate_atom            # noqa: E402  十门中的逐句门

BATCH_DIR = Path.home() / ("Studio/Workspace/outputs/sg/sessions/"
                           "sg_toytune_ep1/text_batch_10")
POLISHED = BATCH_DIR / "polished"
TRANS_DIR = POLISHED / "translations"
SRT_DIR = POLISHED / "srt"

VO_START = 10.0
PER_WORD = 0.48
SENT_PAD = 0.7
GAP = 1.5
SECTION_GAP = 3.0
SECTIONS = ("opening", "prayer", "closing")


def timeline(sentences: dict) -> list[tuple[float, float]]:
    """慢速祷告语速的估算时轴,三语共用。"""
    t = VO_START
    spans = []
    for sec in SECTIONS:
        for s in sentences[sec]:
            words = max(1, len(s.split()))
            dur = max(1.6, words * PER_WORD + SENT_PAD)
            spans.append((t, t + dur))
            t += dur + GAP
        t += SECTION_GAP - GAP
    return spans


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(path: Path, spans, texts) -> None:
    out = []
    for i, ((a, b), txt) in enumerate(zip(spans, texts), 1):
        out.append(f"{i}\n{_srt_time(a)} --> {_srt_time(b)}\n{txt}\n")
    path.write_text("\n".join(out), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True, type=int)
    ap.add_argument("--zh", required=True, type=Path)
    a = ap.parse_args()
    n = a.episodes

    src = json.loads((POLISHED / f"sg_text_ep{n:02d}.json").read_text())
    eid, perspective = src["episode_id"], src["perspective"]
    en = src["sentences"]
    zh = json.loads(a.zh.read_text())

    # 门禁:1:1 对齐 + 逐句十门
    errors: list[str] = []
    for sec in SECTIONS:
        if len(zh.get(sec, [])) != len(en[sec]):
            errors.append(f"{sec} 句数不齐: en {len(en[sec])} vs zh "
                          f"{len(zh.get(sec, []))}")
    if not errors:
        for sec in SECTIONS:
            for e_s, z_s in zip(en[sec], zh[sec]):
                for msg in gate_atom(e_s, z_s, perspective):
                    errors.append(f"[{sec}] {msg}")
    last = (zh.get("closing") or [""])[-1].strip()
    if last not in ("阿们。", "阿们"):
        errors.append(f"结尾非阿们: {last[:20]}")
    if errors:
        print(f"⛔ {eid} FAIL({len(errors)} 处):")
        for e in errors[:10]:
            print("   " + e)
        return 1

    from opencc import OpenCC
    cc = OpenCC("s2twp")
    zh_tw = {sec: [cc.convert(s) for s in zh[sec]] for sec in SECTIONS}

    TRANS_DIR.mkdir(exist_ok=True)
    SRT_DIR.mkdir(exist_ok=True)
    titles = {"opening": ("开场", "開場"), "prayer": ("祷告", "禱告"),
              "closing": ("结尾", "結尾")}
    for lang, data, tw in (("zh-CN", zh, False), ("zh-TW", zh_tw, True)):
        md = [f"# {eid} · {'繁體中文' if tw else '简体中文'}", "",
              "QA: `PASS`(十门全过)  ",
              f"{'視角' if tw else '视角'}: `{perspective}`", ""]
        for sec in SECTIONS:
            md += [f"## {titles[sec][1 if tw else 0]}", "",
                   "".join(data[sec]), ""]
        (TRANS_DIR / f"{eid}.{lang}.md").write_text("\n".join(md),
                                                    encoding="utf-8")

    pairs = []
    for sec in SECTIONS:
        for e_s, z_s, t_s in zip(en[sec], zh[sec], zh_tw[sec]):
            pairs.append({"section": sec, "en": e_s, "zh": z_s, "zh_tw": t_s})
    (TRANS_DIR / f"{eid}.translations.json").write_text(json.dumps({
        "episode_id": eid, "perspective": perspective,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "translator": "claude-session", "qa": {"ok": True, "pairs": len(pairs)},
        "pairs": pairs}, ensure_ascii=False, indent=1), encoding="utf-8")

    spans = timeline(en)
    flat_en = [s for sec in SECTIONS for s in en[sec]]
    flat_zh = [s for sec in SECTIONS for s in zh[sec]]
    flat_tw = [s for sec in SECTIONS for s in zh_tw[sec]]
    write_srt(SRT_DIR / f"{eid}.en.srt", spans, flat_en)
    write_srt(SRT_DIR / f"{eid}.zh-CN.srt", spans, flat_zh)
    write_srt(SRT_DIR / f"{eid}.zh-TW.srt", spans, flat_tw)
    total = spans[-1][1] + 5
    print(f"✅ {eid} PASS({len(pairs)} 句, 估时 {total/60:.1f} 分钟)"
          f"→ {eid}.zh-CN/zh-TW.md + 三语 SRT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
