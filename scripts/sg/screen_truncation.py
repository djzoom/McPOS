#!/usr/bin/env python3
# coding: utf-8
"""排查「起点切掉前导词」的原子 —— 否定词一旦被切掉,意思会静默反转。

2026-08-05 实例(约翰福音 14:1):

    母带音频     "Do not let your hearts be troubled."
    原子边界     [168.77 …]  ← "Do not" 在 168.77 之前,被切在原子外
    入库文本     "Let your hearts be troubled."   ← 意思完全相反

这条原子**语法完整、首字母大写、句末有句号**,所有句法检查都发现不了。
它在质检里活到了成片阶段,只有人读文案时才可能发现。

更麻烦的是:它前面的间隔有 4.6 秒,按「切点在停顿处 = 安全」的判据
反而被归为安全。真相是那段语音**落在两条原子之间的空隙里,没有任何
原子覆盖它** —— 切分器整段漏掉了它。

判据只能是听:对每条原子向前多取 LOOKBACK 秒重新转写,若扩展后的
文本在原子文本之前多出了词,说明原子丢了前导。

  ./.venv/bin/python scripts/sg/screen_truncation.py --dry-run
  ./.venv/bin/python scripts/sg/screen_truncation.py --repair
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import harvest_whisper as hw
from atom_quality import usable, words

MANIFEST = Path.home() / "Studio/Library/sg/atoms/manifest.json"
CONF = Path(__file__).resolve().parents[2] / "config"
LOOKBACK = 2.0          # 向前多听几秒
MAX_PREFIX = 6          # 多出的前导词超过这么多,说明听进了上一句,不算截断

# 丢掉就会让意思**反转**的前导词 —— 这类必须修,不能只是标记
NEGATION = {"not", "never", "no", "nor", "neither", "don't", "do", "cannot",
            "can't", "won't", "shall", "will"}


BATCH = 120


def hear_batch(jobs: list[tuple[str, Path, float, float]],
               model: Path) -> dict[str, str]:
    """批量转写。key → 听到的文本。

    whisper-cli 每次调用都要重新加载 1.5GB 模型(约 5 秒),而实际转写
    只要零点几秒 —— 逐条调用时 95% 的时间花在加载上,全库要跑 2.5 小时。
    CLI 支持一次传多个文件(`whisper-cli [options] file0 file1 …`),
    配 `-otxt` 会在每个输入旁生成同名 .txt,映射明确。
    """
    out: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        wavs: list[tuple[str, Path]] = []
        for k, master, t0, t1 in jobs:
            w = d / f"{len(wavs):05d}.wav"
            r = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, t0):.3f}",
                 "-to", f"{t1:.3f}", "-i", str(master),
                 "-ar", "16000", "-ac", "1", str(w)],
                capture_output=True, text=True)
            if r.returncode == 0 and w.exists():
                wavs.append((k, w))
        if not wavs:
            return out
        subprocess.run(
            ["whisper-cli", "-m", str(model), "-nt", "-l", "en", "-otxt"]
            + [str(w) for _, w in wavs],
            capture_output=True, text=True)
        for k, w in wavs:
            txt = Path(str(w) + ".txt")
            if txt.exists():
                out[k] = " ".join(txt.read_text(errors="ignore").split()).strip()
    return out


def missing_prefix(extended: str, atom_text: str) -> list[str] | None:
    """扩展转写相对原子文本多出的前导词;不是「多出前导」的情形返回 None。"""
    e, a = words(extended), words(atom_text)
    if not a or len(e) <= len(a):
        return None
    # 原子文本必须是扩展文本的**后缀**,否则两者不是同一段话
    if e[-len(a):] != a:
        return None
    pre = e[:-len(a)]
    return pre if 0 < len(pre) <= MAX_PREFIX else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--repair", action="store_true",
                    help="把丢失的前导词补回来:扩展 t_start 并从母带重切")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    model = hw.resolve_model(None)
    man = json.loads(MANIFEST.read_text())
    todo = [x for x in man["atoms"] if usable(x) and Path(x["path"]).exists()]
    if a.limit:
        todo = todo[:a.limit]
    print(f"排查 {len(todo)} 条可用原子(向前多听 {LOOKBACK}s)…\n")

    # 回溯边界取到**前一条原子的结束点**为止。丢失的词就落在这段空隙里;
    # 越过它就会把上一条已经收录的语音再抓一遍,同一句话在一期里播两次。
    prev_end: dict[str, float] = {}
    by_master: dict[str, list[dict]] = collections.defaultdict(list)
    for x in man["atoms"]:
        by_master[x.get("source_master", "?")].append(x)
    for items in by_master.values():
        items.sort(key=lambda z: z.get("t_start", 0.0))
        for j, z in enumerate(items):
            prev_end[z["id"]] = float(items[j - 1]["t_end"]) if j else 0.0

    jobs: list[tuple[str, Path, float, float]] = []
    starts: dict[str, float] = {}
    by_id = {x["id"]: x for x in todo}
    for x in todo:
        master = Path(x["source_master"])
        if not master.exists():
            continue
        floor = prev_end.get(x["id"], 0.0)
        t0 = max(float(x["t_start"]) - LOOKBACK, floor)
        if float(x["t_start"]) - t0 < 0.15:
            continue                      # 与上一条紧邻,空隙里塞不下词
        jobs.append((x["id"], master, t0, float(x["t_end"])))
        starts[x["id"]] = t0
    print(f"  其中 {len(jobs)} 条起点前有空隙,需要重听\n")

    found: list[tuple[dict, list[str], str, float]] = []
    for b in range(0, len(jobs), BATCH):
        chunk = jobs[b:b + BATCH]
        heard = hear_batch(chunk, model)
        for k, ext in heard.items():
            pre = missing_prefix(ext, by_id[k]["text"])
            if pre:
                found.append((by_id[k], pre, ext, starts[k]))
        print(f"  …{min(b + BATCH, len(jobs))}/{len(jobs)}  已发现截断 {len(found)}")

    inverting = [f for f in found if any(w in NEGATION for w in f[1])]
    print(f"\n=== 结果 ===")
    print(f"  起点丢了前导词      {len(found):>5}")
    print(f"  其中丢的是否定词    {len(inverting):>5}  ← 意思已反转,必须修")

    if inverting:
        print(f"\n--- 语义反转(全部列出)---")
        for x, p, e, _ in inverting:
            print(f"  {x['id']}")
            print(f"    现文本: {x['text'][:60]}")
            print(f"    真实是: {e[:70]}")
    if found:
        print(f"\n--- 其他截断(前 10)---")
        for x, p, e, _ in [f for f in found if f not in inverting][:10]:
            print(f"  丢「{' '.join(p)}」 → {x['text'][:52]}")

    CONF.mkdir(exist_ok=True)
    (CONF / "sg_truncation_review.json").write_text(json.dumps(
        {"generated": datetime.now(timezone.utc).isoformat(),
         "checked": len(todo), "truncated": len(found),
         "inverting": len(inverting),
         "rows": [{"id": x["id"], "text": x["text"], "missing": p,
                   "actual": e, "inverts": any(w in NEGATION for w in p)}
                  for x, p, e, _ in found]}, ensure_ascii=False, indent=1))

    if not a.repair or a.dry_run:
        print("\n(未修改。加 --repair 把前导词补回并从母带重切)")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    MANIFEST.with_suffix(f".json.bak_trunc_{stamp}").write_text(MANIFEST.read_text())
    fixed = 0
    ids = {x["id"]: (p, e, t0) for x, p, e, t0 in found}
    for x in man["atoms"]:
        if x["id"] not in ids:
            continue
        pre, ext, t0 = ids[x["id"]]
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, t0):.3f}",
             "-to", f"{float(x['t_end']):.3f}", "-i", x["source_master"],
             "-c:a", "libmp3lame", "-q:a", "2", x["path"]],
            capture_output=True, text=True)
        if r.returncode != 0:
            continue
        x["text_was"], x["text"] = x["text"], ext
        x["t_start"] = max(0.0, t0)
        x["duration_sec"] = round(float(x["t_end"]) - x["t_start"], 3)
        x["repaired_at"] = datetime.now(timezone.utc).isoformat()
        x["repair"] = "restored_truncated_prefix"
        fixed += 1
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1))
    print(f"\n✅ 已补回 {fixed} 条的前导词并重切(备份 manifest.json.bak_trunc_{stamp})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
