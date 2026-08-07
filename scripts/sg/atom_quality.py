#!/usr/bin/env python3
# coding: utf-8
"""原子可用性的**唯一权威判据**。

在此之前,同一套门禁被抄在 build_tts_batch / tag_addressee / rebuild_atom_faithful
等至少五个脚本里,各自演化。2026-08-05 加语速上界时才发现:改一处不影响其他,
盘点数字因此互相矛盾。所有脚本一律 `from atom_quality import usable`。

两道门:
  ① 词数 ≥3   —— 更短的切片没有独立语义,拼进去像口吃
  ② 未被隔离  —— 自比上帝(self-deification)、无语音(no_speech)

**不设语速/密度门禁。** 2026-08-05 一度加过 0.9–4.0 词/秒的上下界,
用它发现了 418 条「静音挂着别句文本」的原子(那批已按 no_speech 永久隔离,
靠隔离标记就能挡住,不需要每次重算密度)。但下界是彻底的误判:

    这是助眠频道 —— 缓慢的语速和超大的间隔**正是想要的效果**,
    "Take a deep breath in." 读满 9 秒是设计,不是缺陷。

拿正常朗读的语速(2–3 词/秒)去卡冥想朗读,只会误杀好素材。
文本与音频不匹配的问题改由隔离标记与句法完整性判据承担。
"""
from __future__ import annotations

import re

MIN_WORDS = 3


def words(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]", " ", (s or "").lower()).split()


def key(s: str) -> str:
    """去重用的归一化键。"""
    return " ".join(words(s))


def reject_reason(x: dict) -> str | None:
    """返回不可用的原因;可用则返回 None。"""
    if x.get("quarantined"):
        return f"隔离({x['quarantined']})"
    t = x.get("text")
    if not t:
        return "无文本"
    n = len(words(t))
    if n < MIN_WORDS:
        return f"词数 {n} < {MIN_WORDS}"
    return None


def usable(x: dict) -> bool:
    return reject_reason(x) is None


# —— 句法完整性:**建议性**判据,不是剔除理由 ——
# 以 "And…" 开头的经文续句本身没问题,只要紧跟它的前一句播放就完整。
# 编排器的 directly_continues 支持这种续接,所以这里只做标记,
# 由盘点区分「自由可用」与「仅可作续接」—— 后者不能算进期数供给。
_NO_END = re.compile(r"[.!?]\s*[\"”]?\s*$")
_FRAG_START = re.compile(
    r"^\s*(and|but|or|because|so that|nor|yet|as|when|while|if)\b", re.I)
_FRAG_END = re.compile(
    r"\b(a|an|the|and|but|or|to|of|in|for|with|that|who|which|is|are|was|were|"
    r"my|your|his|our)\s*[,]?\s*$", re.I)


def fragment_reason(x: dict) -> str | None:
    """返回「为何只能作续接」;句法完整则返回 None。

    两类证据,波形优先:
      · 波形证据(head_cut / tail_cut)—— 切点落在连续语流中间,首/尾词被削。
        由 audit_boundaries.py 用 RMS 包络判定,这是**唯一可信**的边界依据。
        whisper 会脑补熟悉的经文:2026-08-05 它在一段纯数字静音上补出了
        "Do not",差点让我把 2 秒静音接进原子里。
      · 句法证据 —— 无句末标点、以连词开头、以虚词结尾。
    """
    if x.get("head_cut"):
        return "波形:起点切穿语流(首词被削)"
    if x.get("tail_cut"):
        return "波形:终点切穿语流(尾词被削)"
    t = (x.get("text") or "").strip()
    if not t:
        return None
    if not _NO_END.search(t):
        return "无句末标点(切在句中)"
    if _FRAG_START.match(t):
        return "以连词/从句引导词开头"
    if _FRAG_END.search(t):
        return "以虚词结尾"
    return None


def standalone(x: dict) -> bool:
    """自由可用:过质量门,且句法完整,可放在任意位置。"""
    return usable(x) and fragment_reason(x) is None
