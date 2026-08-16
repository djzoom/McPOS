#!/usr/bin/env python3
# coding: utf-8
"""原子可用性的**唯一权威判据**。

在此之前,同一套门禁被抄在 build_tts_batch / tag_addressee / rebuild_atom_faithful
等至少五个脚本里,各自演化。2026-08-05 加语速上界时才发现:改一处不影响其他,
盘点数字因此互相矛盾。所有脚本一律 `from atom_quality import usable`。

三道门:
  ① 词数 ≥3   —— 更短的切片没有独立语义,拼进去像口吃
  ② 未被隔离  —— 自比上帝(self-deification)、无语音(no_speech)
  ③ whisper 复核白名单 —— **仅选片/盘点侧**,由调用方传入 load_whitelist()

**不设语速/密度门禁。** 2026-08-05 一度加过 0.9–4.0 词/秒的上下界,
用它发现了 418 条「静音挂着别句文本」的原子(那批已按 no_speech 永久隔离,
靠隔离标记就能挡住,不需要每次重算密度)。但下界是彻底的误判:

    这是助眠频道 —— 缓慢的语速和超大的间隔**正是想要的效果**,
    "Take a deep breath in." 读满 9 秒是设计,不是缺陷。

拿正常朗读的语速(2–3 词/秒)去卡冥想朗读,只会误杀好素材。
文本与音频不匹配的问题改由隔离标记与句法完整性判据承担。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

MIN_WORDS = 3

# —— 相邻/续接的间隔判据(秒),全管线只此一份 ——
# 曾在 build_session 与 vo_score 各定义一份(两者互不能 import:编排器已经
# import 打分器,反向会成环)。出片端与验收端各持一份同名常量,就是
# VO_PIPELINE 第 5 条教训「同一概念两处判据」的标准起手式,故收归这里。
#
# MAX_OVERLAP:相邻原子允许的最大重叠。实测全库 1388 对相邻原子中 18.5% 有
# 重叠,幅度只有 0.090s 与 0.210s 两档 —— 采集切分的固定伪影。原先写 −0.15
# 恰好卡在两档之间,0.210s 那批被判「不相邻」。取 −0.25 覆盖全部实测值。
MAX_OVERLAP = -0.25
# WAVEFORM_REPAIR_GAP:被削掉的半个词只可能躺在**紧挨着**的下一条里。
# 实测 85 条 tail_cut 中 60% 的后继隔了 0.35–18s —— 那几秒话采集时就丢了,
# 拿 18s 容差去「补完」削词补的是空气。
WAVEFORM_REPAIR_GAP = 0.35
# SYNTAX_REPAIR_GAP:句子说到一半,后继不可能隔 18 秒才来。已交付三期
# 15 对真实续句的间隔全落在 −0.09～6.63s(中位 1.91s),8 秒留足余量。
SYNTAX_REPAIR_GAP = 8.0
# FLOW_GAP:语流衔接 —— 刻意的长停顿,两句各自完整,这才是 18s 的本职。
FLOW_GAP = 18.0

# —— whisper 复核白名单:选片侧的第三道门 ——
# 2026-08-05 04:55 生成(逐条复核 1818,相似度 ≥0.8 者 827 入册),
# 但生成后没有任何代码消费它 —— qc01~qc08 照样混入 42–46% 病态原子。
# 白名单只约束**选片/盘点侧**(build_session / inventory / build_tts_batch):
# 审计侧工具(verify_atom_texts / audit_boundaries / tag_addressee …)
# 正是产出复核数据的一环,拿白名单卡它们是循环依赖,永远不传。
WHITELIST_PATH = Path(__file__).resolve().parents[2] / "config" / "sg_atom_whitelist.json"


def load_whitelist(path: Path = WHITELIST_PATH) -> frozenset[str]:
    """读取白名单原子 id。文件缺失或为空一律抛异常 —— 选片侧宁可停线,
    也不能静默退回「无白名单」状态:检不出自己失效的门禁比没有门禁更危险。"""
    ids = frozenset(json.loads(path.read_text(encoding="utf-8")).get("ids") or [])
    if not ids:
        raise ValueError(f"白名单为空: {path}")
    return ids


def words(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]", " ", (s or "").lower()).split()


def key(s: str) -> str:
    """去重用的归一化键。"""
    return " ".join(words(s))


def reject_reason(x: dict, whitelist: frozenset[str] | None = None) -> str | None:
    """返回不可用的原因;可用则返回 None。选片/盘点侧必须传入 load_whitelist()。"""
    if x.get("quarantined"):
        return f"隔离({x['quarantined']})"
    t = x.get("text")
    if not t:
        return "无文本"
    n = len(words(t))
    if n < MIN_WORDS:
        return f"词数 {n} < {MIN_WORDS}"
    if whitelist is not None and x.get("id") not in whitelist:
        return "未过 whisper 复核白名单"
    return None


def usable(x: dict, whitelist: frozenset[str] | None = None) -> bool:
    return reject_reason(x, whitelist) is None


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


# —— 边界证据:两项独立测量,互相印证才算数(2026-08-11)——
#
#   tail_cut       母带在原子终点之外还在发声 → 采集**丢了话**
#                  (audit_boundaries.py,量母带包络)
#   tail_hard_cut  原子文件自己的尾部停在满音量 → 音频**被削掉半个词**
#                  (audit_atom_edges.py,量原子自身电平)
#
# 单独用任何一项都会出错,实测数据(白名单可用池 728 条):
#   · 已知收音干净的 584 条里,仍有 19 条尾部电平高于 −8 dB → 单靠电平会误杀
#   · 42 条只有母带续声:采集是丢了话,但这条自己收得干干净净,不必拦
#   · 25 条只有自身硬切:母带那边已经没声了,多半是电平判据的噪声
# 两项同时成立的 43 条才是确凿的「尾词被削」—— 只对这批要求紧邻补救。
#
# 头部没有对应判据:**语音的起音本来就陡**,第一个重读音节在 120ms 内就能
# 逼近全局峰值。按同样的方法量首部,第一个被判「首词被削」的是频道招牌
# 「Welcome to Sleep in Grace.」。物理不成立的测量不能当门禁,故头部仍只用
# 母带证据(head_cut)与句法证据。
# 悬空收尾:句子停在一个**必须带宾语/补语**的功能词上,且没有逗号收束。
# 这种句子只能由「下一个词」接上,不可能由一个大写开头的新句子补完:
#     「…the Spirit of God dwells in you and he does not」
#     ＋「You can rest because he watches over you.」   ← 永远没接上
# 逗号结尾的从句不算:「Even when your mind drifts and wanders,」后面
# 本来就该跟一个大写开头的主句,那是正常的。
_DANGLING = re.compile(
    r"\b(do|does|did|is|are|was|were|be|been|has|have|had|can|could|will|would|"
    r"shall|should|may|might|must|not|never|nor|to|of|in|on|at|for|with|from|"
    r"and|but|or|that|which|the|a|an|my|your|his|her|our|their|its)\s*$", re.I)


def dangling_tail(text: str) -> str | None:
    """返回悬空的那个词;句子收束完整则返回 None。"""
    t = (text or "").strip()
    if not t or t[-1] in ".!?,;:":
        return None
    m = _DANGLING.search(t)
    return m.group(1) if m else None


def completes_dangling(prev_text: str, next_text: str) -> bool:
    """悬空句能否被后继接上 —— 后继必须是**同一句的延续**,不能另起新句。"""
    if not dangling_tail(prev_text):
        return True
    n = (next_text or "").strip()
    if not n:
        return False
    # 小写起头 = 同一句继续;大写起头的完整句子接不上一个悬着的助动词
    return n[0].islower()


def tail_truncated(x: dict) -> bool:
    """尾词是否**确凿**被削:母带续声与自身满音量两项证据同时成立。"""
    return bool(x.get("tail_cut") and x.get("tail_hard_cut"))


def head_fragment_reason(x: dict) -> str | None:
    """头部残缺:这条原子必须**紧跟母带前句**播放,否则开头缺字/没头没脑。"""
    if x.get("head_cut"):
        return "母带:起点处仍在发声(首词可能被削)"
    t = (x.get("text") or "").strip()
    if t and _FRAG_START.match(t):
        return "以连词/从句引导词开头"
    return None


def tail_fragment_reason(x: dict) -> str | None:
    """尾部残缺:这条原子必须**被母带后继接上**,否则话说一半。"""
    if tail_truncated(x):
        return "双证:尾词被削(母带续声+自身满音量)"
    if x.get("tail_cut"):
        return "母带:终点处仍在发声(采集丢词)"
    t = (x.get("text") or "").strip()
    if not t:
        return None
    if not _NO_END.search(t):
        return "无句末标点(切在句中)"
    if _FRAG_END.search(t):
        return "以虚词结尾"
    return None


def fragment_reason(x: dict) -> str | None:
    """返回「为何只能作续接」;句法完整则返回 None。

    两类证据,波形优先:
      · 波形证据(head_cut / tail_cut)—— 切点落在连续语流中间,首/尾词被削。
        由 audit_boundaries.py 用 RMS 包络判定,这是**唯一可信**的边界依据。
        whisper 会脑补熟悉的经文:2026-08-05 它在一段纯数字静音上补出了
        "Do not",差点让我把 2 秒静音接进原子里。
      · 句法证据 —— 无句末标点、以连词开头、以虚词结尾。

    方向有讲究(2026-08-10 拆分):头部残缺要求**紧跟前句**,尾部残缺要求
    **后继接上**。编排器与 vo_score 都按方向分别校验,不能混为一谈。
    """
    return head_fragment_reason(x) or tail_fragment_reason(x)


def standalone(x: dict) -> bool:
    """自由可用:过质量门,且句法完整,可放在任意位置。"""
    return usable(x) and fragment_reason(x) is None
