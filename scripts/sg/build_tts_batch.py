#!/usr/bin/env python3
# coding: utf-8
"""生成待录 TTS 纯文本 —— 去重、验规、按优先级排序、精确控字符。

TTS 按字符计费,所以每一句都要值钱:
  · 与库中 868 条现有文案比对,完全重复与近似重复(≥0.82)一律剔除
  · 组与组之间也去重,避免跨组撞车
  · 六条硬规则自动验(句长/编号写法/引文头/addressee/易错发音)
  · 按优先级排序,先补解锁期数最多的
  · 输出**纯文本**:一行一句,无标题无注释,可直接贴进 ElevenLabs

  ./.venv/bin/python scripts/sg/build_tts_batch.py --group G1 --budget 9800
  ./.venv/bin/python scripts/sg/build_tts_batch.py --check out.txt   # 只验规
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path

from atom_quality import MIN_WORDS, key, usable, words

MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
SCRIPTS = Path.home() / "Studio/Library/sg/catalog/scripts"
NEAR = 0.82
# 易错发音:只拦**实证被念错**的词形。"peace" 是频道核心词,库里已有
# 上百条正确发音的实例,不能一律拦截 —— 只拦已知出错的搭配。
#
# "in grace" 曾在这份名单上(Locke 读起来接近 "and Grace"),2026-08-06 移除:
# 那是频道名 Sleep in Grace,发音特征反而是记忆点,不是缺陷。品牌该用就用。
RISKY = re.compile(r"\bnights\b|\bsofter\b|\brestores\b|"
                   r"\bpiece\b|\bpeace settle\b", re.I)

# 元语言词 —— 只会出现在我写给自己的注释里,绝不会出现在祷告词中。
# 2026-08-05:一句注释「This block doubles it. Deepen = the slow descent
# into stillness.」以大写开头、句号结尾,完美伪装成台词溜过白名单,
# 靠用户在录制前肉眼发现才拦下。不能指望人逐行检查 195 句。
META = re.compile(
    r"\b(block|role|atom|atoms|episode|episodes|library|corpus|unique|slot|"
    r"slots|addressee|doubles|tightest|recorded|goal|budget|character[s]? "
    r"count|whisper|manifest|TTS|dedup|pauses|sentences|marker|cue|cues)\b"
    r"|=|→|·", re.I)

# 句中出现全大写单词 = 写给自己的指令,不是祷告词。
# 2026-08-06:「Pauses BETWEEN sentences, never inside one.」大写开头、
# 句号结尾,完美伪装成台词溜过白名单 —— 与用户上次抓到的
# 「Deepen = the slow descent into stillness.」是同一类事故。
# 靠不断扩充词表追不上,判结构比判词汇可靠。
SHOUT = re.compile(r"(?<!^)\b[A-Z]{2,}\b")
DIVINE = re.compile(r"\bI (am with you|will strengthen|will uphold|give them|"
                    r"have called|have redeemed)", re.I)




def library_keys() -> set[str]:
    """库中**已可用**的文案 —— 用来避免重复付费录已有内容。

    注意用的是 atom_quality.usable:被隔离或文本错配的原子不算「库里已有」,
    否则它们的假文本会挡住真正需要补录的句子。"""
    man = json.loads(MANIFEST.read_text())
    return {key(x["text"]) for x in man["atoms"] if usable(x)}


def existing_batches(exclude: str) -> set[str]:
    """已生成过的**其他组**待录文本也要去重,避免跨组撞车。

    必须排除本组自己上一次的输出 —— 否则重跑会把自己的产物当成别组,
    把整批剔成空(2026-08-05 踩过:168 句被判「组间重复」)。
    """
    out = set()
    for p in SCRIPTS.glob("tts_*.txt"):
        if p.stem == f"tts_{exclude.lower()}":
            continue
        for l in p.read_text(encoding="utf-8").splitlines():
            if l.strip():
                out.add(key(l))
    return out


def validate(line: str) -> str | None:
    w = words(line)
    if len(w) < MIN_WORDS:
        return f"句长 {len(w)} 词 < {MIN_WORDS}"
    if re.search(r"\b\d+\s*[:.]\s*\d+", line):
        return "经文编号须写口读形式"
    if DIVINE.search(line) and "says" not in line.lower():
        return "神性第一人称须与 says 同句"
    if re.search(r"\b(He|His)\s+\w+\s+you\b", line) and \
            re.search(r"\bYou (are|have|will)\b", line):
        return "同句混用两种 addressee"
    if RISKY.search(line):
        return f"含易错发音词:{RISKY.search(line).group(0)}"
    if META.search(line):
        return f"疑似注释残留(元语言词「{META.search(line).group(0)}」)"
    if SHOUT.search(line):
        return f"疑似指令残留(句中全大写「{SHOUT.search(line).group(0)}」)"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, help="草稿文件(带注释的 _TTS.txt)")
    ap.add_argument("--group", default="G1")
    ap.add_argument("--budget", type=int, default=9800, help="字符上限")
    ap.add_argument("--check", type=Path, help="只校验某个纯文本")
    a = ap.parse_args()

    if a.check:
        lines = [l.strip() for l in a.check.read_text().splitlines() if l.strip()]
        bad = [(l, v) for l in lines if (v := validate(l))]
        print(f"{a.check.name}: {len(lines)} 句 · "
              f"{sum(len(l) for l in lines)} 字符 · 违规 {len(bad)}")
        for l, v in bad[:10]:
            print(f"  ✗ {v}: {l[:60]}")
        return 1 if bad else 0

    src = a.source or (SCRIPTS / f"{a.group.lower()}_bless_insomnia_TTS.txt")
    raw = [l.strip() for l in src.read_text(encoding="utf-8").splitlines()]
    # 只取可读句。判据用**正向白名单**而非排除注释:
    # 可读句 = 以大写或引号开头、以句末标点结尾、不含冒号式标注。
    # (状态机试过两次都不可靠:草稿里注释块与正文之间不一定有空行)
    def speakable(l: str) -> bool:
        if not l or len(l) < 12:
            return False
        if not l[0].isupper() and l[0] not in "\"'":
            return False
        if l[-1] not in ".!?":
            return False
        if re.match(r"^[A-Za-z ]{2,20}:", l):      # "Goal: …" / "Voice: …"
            return False
        if l.startswith(("SLEEP", "BLOCK", "RULES", "Read ", "Goal", "Voice")):
            return False
        return True

    cand = [l for l in raw if speakable(l)]

    lib, prev = library_keys(), existing_batches(a.group)
    seen, out, drop = set(), [], {"库中已有": 0, "近似重复": 0, "组间重复": 0,
                                  "违规": 0, "超预算": 0}
    libkeys = list(lib)
    chars = 0
    for l in cand:
        k = key(l)
        if k in lib:
            drop["库中已有"] += 1; continue
        if k in prev:
            drop["组间重复"] += 1; continue
        if k in seen:
            drop["近似重复"] += 1; continue
        if difflib.get_close_matches(k, libkeys, n=1, cutoff=NEAR):
            drop["近似重复"] += 1; continue
        if validate(l):
            drop["违规"] += 1; continue
        if chars + len(l) + 1 > a.budget:
            drop["超预算"] += 1; continue
        seen.add(k); out.append(l); chars += len(l) + 1

    dest = SCRIPTS / f"tts_{a.group.lower()}.txt"
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"候选 {len(cand)} → 采用 {len(out)} 句 · {chars} 字符 "
          f"({chars/a.budget:.0%} 预算) · 约 {chars/590:.1f} 分钟")
    print(f"剔除:{drop}")
    print(f"→ {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
