#!/usr/bin/env python3
# coding: utf-8
"""揪出**采集留下的机器痕迹**,在源头隔离 —— 不是靠听感,是靠统计指纹。

两类,都不需要人耳判断,靠数据本身就能证伪:

【① 等长切割 fixed_length_cut】
语音按停顿切分,时长必然连续分布。若某个时长上精确堆着上百条原子,那是
**按长度下刀**留下的指纹,不是语音边界。2026-08-12 实测:可用池 1396 条里
有 156 条时长恰好 1.09s,而次高的时长只有 17 条 —— 相差九倍。
这 156 条中 148 条来自 `0906Fall_Asleep` 与 `Rest_Secure` 两支母带,正是
CLAUDE.md 记载的幻觉重灾区(305 / 191 词每分钟,正常值 58–124)。
文本也印证:「is deeper than」「wrap me in」「around you like」全是句中碎片,
只因凑够 3 个词而侥幸通过词数门。

  ⚠ 判据是**异常聚集**,不是「1.09s 这个数」。阈值按分布现算:某时长上的
    条数超过中位数的 20 倍才算指纹。换一批母带重采后,这个数会自己变。

【② 截断重复 truncated_duplicate】
同一句话库里同时存在完整版与残缺版:
    残「Your word says, you will keep in perfect.」   ← 少了 peace
    全「that says, you will keep in perfect peace those whose minds are steadfast.」
残缺版进片就是半句经文。判据:归一化文本是另一条的**真前缀**。
完整版留着,残缺版隔离 —— 库里不缺这句话,缺的是把它说完整。

  ./.venv/bin/python scripts/sg/audit_fragment_artifacts.py            # 只报告
  ./.venv/bin/python scripts/sg/audit_fragment_artifacts.py --mark     # 写回隔离
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atom_quality import key, load_whitelist, reject_reason
from sg_media import backup_with_retention

MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
SPIKE_RATIO = 20.0      # 某时长的条数 > 中位数 × 此值 → 判为等长切割指纹
MIN_SPIKE = 30          # 且至少这么多条,免得小样本上误判


def _incomplete(text: str) -> bool:
    """这条原子在**句法上**是不是残的:没有句末标点,或以小写起头。

    时长指纹只能证明「这一批是按长度切的」,不能证明「这一条切坏了」——
    刀切一百下,总有几下正好落在句号上。`Where fear comes.` 就是 1.09s 的
    完整短句,拿它当病灶隔离纯属误伤。两者都成立才动手。
    """
    t = (text or "").strip()
    return bool(t) and (t[-1] not in ".!?" or t[0].islower())


def find_fixed_length(pool: list[dict]) -> tuple[set[str], list[tuple[float, int]]]:
    c = collections.Counter(round(float(a.get("duration_sec") or 0), 2) for a in pool)
    if len(c) < 5:
        return set(), []
    med = statistics.median(c.values())
    spikes = {d for d, n in c.items() if n >= MIN_SPIKE and n > med * SPIKE_RATIO}
    hit = {a["id"] for a in pool
           if round(float(a.get("duration_sec") or 0), 2) in spikes
           and _incomplete(a.get("text") or "")}
    return hit, sorted(((d, c[d]) for d in spikes), key=lambda x: -x[1])


def find_truncated(pool: list[dict]) -> tuple[set[str], list[tuple[str, str]]]:
    """A 的文本是 B 的真前缀,且 A **自己没说完** → A 是截断残留。

    ⚠ 必须比对**原文**,不能比对 key() 归一化后的文本:归一化会去掉标点,
    于是「Welcome to Sleep in Grace.」(完整句)与「you will keep in perfect」
    (缺了 peace)看起来是同一类东西。第一版就是这么把频道招牌、
    「You are safe.」「I will fear no evil.」一起判成残句的 —— 完整的短句
    本来就可能是某条长原子的前缀,那不是缺陷,是包含关系。
    """
    raws = sorted({(a.get("text") or "").strip() for a in pool if a.get("text")})
    by_raw: dict[str, list[dict]] = {}
    for a in pool:
        by_raw.setdefault((a.get("text") or "").strip(), []).append(a)
    hit: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for t in raws:
        if len(t.split()) < 3 or not _incomplete(t):
            continue
        full = next((o for o in raws if len(o) > len(t) and o.startswith(t)), None)
        if full:
            pairs.append((t, full))
            hit.update(a["id"] for a in by_raw[t])
    return hit, pairs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mark", action="store_true", help="写回 manifest 的 quarantined")
    a = ap.parse_args()

    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    wl = load_whitelist()
    pool = [x for x in man["atoms"] if reject_reason(x, wl) is None]
    print(f"可用池 {len(pool)} 条\n")

    fl, spikes = find_fixed_length(pool)
    print("=== ① 等长切割 ===")
    if spikes:
        for d, n in spikes:
            print(f"  时长 {d:.2f}s 上堆着 {n} 条 ← 指纹")
        src = collections.Counter(
            Path(x.get("source_master", "?")).stem[:30] for x in pool if x["id"] in fl)
        for s, n in src.most_common(3):
            print(f"     来自 {s}: {n} 条")
    print(f"  命中 {len(fl)} 条")

    tr, pairs = find_truncated(pool)
    print(f"\n=== ② 截断重复 ===\n  {len(pairs)} 组 / 命中 {len(tr)} 条")
    for k, full in pairs[:5]:
        print(f"    残「{k[:42]}」")
        print(f"    全「{full[:58]}」")

    doomed = fl | tr
    print(f"\n合计待隔离 {len(doomed)} 条 → 可用池将变为 {len(pool)-len(doomed)} 条")
    if not a.mark:
        print("\n(未写回。加 --mark 执行隔离)")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup_with_retention(MANIFEST, "frag")
    now = datetime.now(timezone.utc).isoformat()
    n = 0
    for x in man["atoms"]:
        if x["id"] in fl:
            x["quarantined"], x["quarantined_at"] = "fixed_length_cut", now
            n += 1
        elif x["id"] in tr:
            x["quarantined"], x["quarantined_at"] = "truncated_duplicate", now
            n += 1
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n🔒 已隔离 {n} 条(备份 manifest.json.bak_frag_{stamp})")
    print("   白名单需同步重建:verify_atom_texts.py --mark --write-whitelist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
