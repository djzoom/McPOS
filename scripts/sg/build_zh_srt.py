#!/usr/bin/env python3
# coding: utf-8
"""英文 SRT + 译表 → 简体 / 繁体 SRT，带 TRANSLATION_QA_FAILURE_MEMO 的十条门禁。

背景（2026-08-04 的失败，见 sessions/sg_toytune_ep1/TRANSLATION_QA_FAILURE_MEMO.md）：
一轮机器翻译把 `He is strong.` 译成「阿们」、把英文原句整句留在中文稿里、把数组和
JSON 字段混进译文，而当时的自动标记 `翻译 QA：PASS` **只核对了原子数量**。
那份备忘录的第一条教训不是"翻译要小心"，而是：

    一个只数条数的检查，比不检查更危险——它发的是通行证。

所以这个脚本刻意**不做翻译**。翻译是人（或人式逐句）在译表 JSON 里给出的，脚本只
负责两件机器擅长的事：把结构性错误挡住，以及做简→繁转换。凡是机器判不了的（语义、
经文是否忠实、人称指向对不对），脚本明说自己判不了，不假装 PASS。

用法：
    ./.venv/bin/python scripts/sg/build_zh_srt.py --session qc08 --table <译表.json>
    ./.venv/bin/python scripts/sg/build_zh_srt.py --session qc08 --table <t.json> --check-only

译表格式：{"cues": {"1": "译文", ...}, "flags": {"76": "说明"}, "_meta": {...}}
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"

# 门禁 7：Amen 的译法必须稳定。上一轮的错译正是把别的句子译成了「阿们」，
# 所以两个方向都要查：Amen 必须译成阿们，且阿们只能来自 Amen。
AMEN_ZH = "阿们"

# 门禁 6：否定词。中文的否定表达比英文分散，所以不做一对一映射，只比"有无"。
EN_NEG = re.compile(r"\b(not|never|no|don'?t|doesn'?t|didn'?t|cannot|can'?t|won'?t|"
                    r"nothing|neither|nor|without)\b", re.I)
# ⚠ 必须同时列简繁两形。第一版只写了简体的 无/没/别，于是简体稿全过、
# 繁体稿在同一道门禁上报了 8 条假失败（無/沒 不在表里）——这道门禁跑在自己
# 的输出上，才把自己的漏洞照出来。检查器要能在两种字形上都成立。
ZH_NEG = re.compile(r"不|没|沒|无|無|非|未|勿|别|別")

# 门禁 1/2：结构污染与英文残留。
JSON_JUNK = re.compile(r"[{}\[\]]|^\s*(?:```|json\b)|\"\s*:\s*\"")
LATIN_RUN = re.compile(r"[A-Za-z]{3,}")


def parse_srt(path: Path) -> list[tuple[str, str, str]]:
    """→ [(编号, 时间轴, 文本)]。文本内换行折成空格（字幕一行放得下）。"""
    out = []
    for block in path.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = [x for x in block.split("\n") if x.strip()]
        if len(lines) < 3:
            continue
        out.append((lines[0].strip(), lines[1].strip(), " ".join(lines[2:]).strip()))
    return out


def gate(cues, table, brand_whitelist) -> tuple[list[str], list[str]]:
    """返回 (硬失败, 需人工复核)。硬失败非空 → 不出文件。"""
    hard, soft = [], []
    tr = table.get("cues") or {}

    # 门禁 3：每个英文原子必须且只能对应一个中文原子
    en_ids = [c[0] for c in cues]
    missing = [i for i in en_ids if i not in tr]
    extra = [i for i in tr if i not in set(en_ids)]
    if missing:
        hard.append(f"门禁3 缺译 {len(missing)} 条: {missing[:12]}")
    if extra:
        hard.append(f"门禁3 译表多出 {len(extra)} 条（无对应英文）: {extra[:12]}")
    if len(tr) != len(en_ids) and not missing and not extra:
        hard.append(f"门禁3 条数不符: 英文 {len(en_ids)} vs 译文 {len(tr)}")

    for cid, ts, en in cues:
        zh = tr.get(cid)
        if zh is None:
            continue
        # 门禁 1：必须是纯字符串
        if not isinstance(zh, str):
            hard.append(f"门禁1 cue{cid} 不是字符串: {type(zh).__name__}")
            continue
        if not zh.strip():
            hard.append(f"门禁1 cue{cid} 译文为空")
            continue
        if JSON_JUNK.search(zh):
            hard.append(f"门禁1 cue{cid} 含结构字符: {zh[:40]}")
        # 门禁 2：英文残留（品牌名白名单之外）
        probe = zh
        for b in brand_whitelist:
            probe = probe.replace(b, "")
        if LATIN_RUN.search(probe):
            hard.append(f"门禁2 cue{cid} 残留英文: {LATIN_RUN.search(probe).group()} | {zh[:40]}")
        # 门禁 6：否定语义
        if EN_NEG.search(en) and not ZH_NEG.search(zh):
            hard.append(f"门禁6 cue{cid} 英文有否定、中文无: EN「{en[:44]}」ZH「{zh[:30]}」")
        if ZH_NEG.search(zh) and not EN_NEG.search(en):
            soft.append(f"门禁6 cue{cid} 中文有否定、英文无（可能是意译，需人眼）: "
                        f"EN「{en[:40]}」ZH「{zh[:28]}」")
        # 门禁 7：Amen 双向
        if re.search(r"\bamen\b", en, re.I) and AMEN_ZH not in zh:
            hard.append(f"门禁7 cue{cid} Amen 未译作{AMEN_ZH}")
        if AMEN_ZH in zh and not re.search(r"\bamen\b", en, re.I):
            hard.append(f"门禁7 cue{cid} 凭空出现{AMEN_ZH}（上一轮的典型错译）")
        # 门禁 4：人称——机器只能提示，判不了
        if re.search(r"\b(I|my|me|mine)\b", en) and not re.search(r"我", zh):
            soft.append(f"门禁4 cue{cid} 英文第一人称、中文无「我」: EN「{en[:40]}」")
        if re.search(r"\b(we|our|us)\b", en, re.I) and not re.search(r"我们|我", zh):
            soft.append(f"门禁4 cue{cid} 英文第一人称复数、中文无「我们」: EN「{en[:40]}」")
        # 门禁 5：经文引用——书卷/章节/数字必须逐字核对，此处只保证数字没丢
        if re.search(r"\bpsalm\b|\bverse\b", en, re.I):
            en_nums = re.findall(r"\d+", en)
            zh_nums = re.findall(r"\d+", zh)
            if sorted(set(en_nums)) != sorted(set(zh_nums)):
                soft.append(f"门禁5 cue{cid} 经文数字不一致（可能是朗读者逐位念，"
                            f"需人眼）: EN{en_nums} ZH{zh_nums} | 「{en[:44]}」")
    return hard, soft


def write_srt(path: Path, cues, tr) -> None:
    body = "".join(f"{cid}\n{ts}\n{tr[cid]}\n\n" for cid, ts, _ in cues)
    path.write_text(body, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--table", type=Path, required=True, help="译表 JSON")
    ap.add_argument("--srt", type=Path, default=None, help="英文源 SRT（默认 <session>.srt）")
    ap.add_argument("--check-only", action="store_true", help="只跑门禁，不写文件")
    a = ap.parse_args()

    D = SESSIONS / a.session
    src = a.srt or (D / f"{a.session}.srt")
    if not src.exists():
        sys.exit(f"找不到英文 SRT: {src}")
    cues = parse_srt(src)
    table = json.loads(a.table.read_text(encoding="utf-8"))
    brand = (table.get("_meta") or {}).get("brand_whitelist") or []

    print(f"英文源 {src.name} · {len(cues)} 条")
    hard, soft = gate(cues, table, brand)

    for m in soft:
        print(f"  ⚠ {m}")
    for m in hard:
        print(f"  ✗ {m}")
    if hard:
        print(f"\n⛔ {len(hard)} 条硬失败 —— 不出文件。")
        return 1
    print(f"\n结构门禁通过（1/2/3/6/7）。{len(soft)} 条待人工复核（4/5 机器判不了）。")

    flags = table.get("flags") or {}
    if flags:
        print(f"译者标注的 {len(flags)} 处原文问题：")
        for k in sorted(flags, key=int):
            print(f"  cue{k}: {flags[k][:110]}")

    if a.check_only:
        return 0

    tr = table["cues"]
    chs = D / f"{a.session}.zh-Hans.srt"
    write_srt(chs, cues, tr)
    print(f"\n✅ 简体 → {chs.name}")

    # 门禁 8：简体过检后才生成繁体。简→繁不是逐字映射（发/髮、干/乾/幹、
    # 里/裡），所以用 OpenCC 的 s2twp：转字 + 转词 + 台湾用语。
    try:
        import opencc
    except ImportError:
        print("⚠ 未装 opencc，跳过繁体。装法: uv pip install opencc-python-reimplemented")
        return 0
    conv = opencc.OpenCC("s2twp")
    tr_t = {k: conv.convert(v) for k, v in tr.items()}
    # 转换后重跑一遍结构门禁：OpenCC 不该引入英文或结构字符，但"不该"不等于"没有"
    hard_t, _ = gate(cues, {"cues": tr_t, "_meta": {"brand_whitelist": brand}}, brand)
    if hard_t:
        print("⛔ 繁体转换后门禁失败:")
        for m in hard_t[:8]:
            print(f"  ✗ {m}")
        return 1
    cht = D / f"{a.session}.zh-Hant.srt"
    write_srt(cht, cues, tr_t)
    changed = sum(1 for k in tr if tr[k] != tr_t[k])
    print(f"✅ 繁体 → {cht.name}（s2twp 改动 {changed}/{len(tr)} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
