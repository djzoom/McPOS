#!/usr/bin/env python3
# coding: utf-8
"""原子库标注体检 — 逐个原子 whisper 转录,与库中文本比对。

2026-08-05 ep01 的 VO 质检发现:部分原子的 text 与音频不符,标注整体
向前漂移约一条(一句话的音频被切在了下一条的文本上),切点还落在词中。
这类原子会把错误规模化到全部十期,必须先查清范围。

判据(每条原子):
  OK       转录与库文本词序列一致(相似度 ≥0.80,容忍转写噪声)
  DRIFT    转录内容能在**相邻**原子的文本里找到 → 标注错位
  MISMATCH 转录与库文本对不上,也不属于相邻条 → 标注错误
  EMPTY    音频里几乎没有语音

产出白名单 config/sg_atom_whitelist.json:只有 OK 的原子允许进入出片。

  ./.venv/bin/python scripts/sg/audit_atom_library.py --limit 50   # 抽检
  ./.venv/bin/python scripts/sg/audit_atom_library.py --resume     # 全库/续跑
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ATOMS = Path.home() / "Studio/Library/sg/atoms"
MANIFEST = ATOMS / "manifest.json"
CONF = Path(__file__).resolve().parents[2] / "config"
OUT = CONF / "sg_atom_whitelist.json"
REPORT = CONF / "sg_atom_audit.json"
MODEL = Path("/Users/z/Projects/whisper.cpp/models/ggml-large-v3-turbo.bin")
ENV = {"KMP_DUPLICATE_LIB_OK": "TRUE", "PATH": "/opt/homebrew/bin:/usr/bin:/bin"}
SIM_OK = 0.80


def words(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]", " ", s.lower()).split()


def sim(a: list[str], b: list[str]) -> float:
    if not a or not b:
        return 0.0
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    return sum(x.size for x in sm.get_matching_blocks()) / max(len(a), len(b))


def transcribe(path: Path, tmp: Path) -> str:
    wav = tmp / "a.wav"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error",
                    "-i", str(path), "-ar", "16000", "-ac", "1", str(wav)],
                   check=False)
    r = subprocess.run(["whisper-cli", "-m", str(MODEL), "-l", "en", "-nt",
                        str(wav)], capture_output=True, text=True, env=ENV)
    return " ".join(r.stdout.split())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="只查前 N 条(抽检)")
    ap.add_argument("--resume", action="store_true", help="接着上次的报告继续")
    ap.add_argument("--relabel", action="store_true",
                    help="用音频转录重写 manifest 与边车的 text(修复模式)")
    a = ap.parse_args()

    atoms = [x for x in json.loads(MANIFEST.read_text())["atoms"] if x.get("text")]
    done: dict[str, dict] = {}
    if a.resume and REPORT.exists():
        done = {r["id"]: r for r in json.loads(REPORT.read_text())["rows"]}
    todo = [x for x in atoms if x["id"] not in done]
    if a.limit:
        todo = todo[: a.limit]

    # 按母带+起始时间排序,用于判定"相邻条"
    order = sorted(atoms, key=lambda x: (x.get("source_master", ""),
                                         x.get("t_start", 0)))
    pos = {x["id"]: i for i, x in enumerate(order)}

    rows = list(done.values())
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for k, x in enumerate(todo, 1):
            p = Path(x["path"])
            if not p.exists():
                rows.append({"id": x["id"], "verdict": "MISSING", "sim": 0.0})
                continue
            heard = transcribe(p, tmp)
            hw, rw = words(heard), words(x["text"])
            s = sim(rw, hw)
            if not hw:
                v = "EMPTY"
            elif s >= SIM_OK:
                v = "OK"
            else:
                v = "MISMATCH"
                i = pos.get(x["id"], -1)
                for j in (i - 2, i - 1, i + 1, i + 2):
                    if 0 <= j < len(order) and \
                            sim(words(order[j]["text"]), hw) >= SIM_OK:
                        v = "DRIFT"
                        break
            rows.append({"id": x["id"], "verdict": v, "sim": round(s, 2),
                         "text": x["text"][:80], "heard": heard[:80],
                         "path": str(p)})
            if k % 25 == 0 or k == len(todo):
                print(f"  {k}/{len(todo)} …", flush=True)
                REPORT.write_text(json.dumps(
                    {"updated": datetime.now(timezone.utc).isoformat(),
                     "rows": rows}, ensure_ascii=False, indent=1))

    if a.relabel:
        heard_by = {r["id"]: r.get("heard", "") for r in rows}
        man = json.loads(MANIFEST.read_text())
        stamp = datetime.now().strftime("%Y%m%d")
        bak = MANIFEST.with_suffix(f".json.bak_{stamp}")
        if not bak.exists():
            bak.write_text(MANIFEST.read_text())
        changed = 0
        for x in man["atoms"]:
            h = heard_by.get(x["id"])
            if h is None:
                continue          # 本轮没转写到,保持原样
            h = h.strip()
            # 空转写 / 幻听词 ≠「转写失败,沿用旧文本」,而是「这段音频没有语音」。
            # 2026-08-05 血的教训:原先这里 `continue` 保留旧文本,导致 397 条
            # 静音片段永久钉着相邻句子的文本,合成时渲染成有字幕却无声。
            if not h or h.lower().rstrip(".") in ("thank you", "you", "bye", "so"):
                x["text_was"] = x.get("text")
                x["quarantined"] = "no_speech"
                x["quarantined_at"] = datetime.now(timezone.utc).isoformat()
                continue
            if h != x.get("text"):
                x["text_original"] = x.get("text")
                x["text"] = h
                x["relabeled_at"] = datetime.now(timezone.utc).isoformat()
                changed += 1
            side = Path(x["path"]).with_suffix(".json")
            if side.exists():
                sd = json.loads(side.read_text())
                if sd.get("text") != h:
                    sd["text_original"] = sd.get("text")
                    sd["text"] = h
                    side.write_text(json.dumps(sd, ensure_ascii=False, indent=1))
        man["relabeled"] = {"at": datetime.now(timezone.utc).isoformat(),
                            "changed": changed, "backup": bak.name}
        MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1))
        print(f"重标注 {changed} 条(备份 {bak.name})")

    tally: dict[str, int] = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    REPORT.write_text(json.dumps(
        {"updated": datetime.now(timezone.utc).isoformat(),
         "tally": tally, "rows": rows}, ensure_ascii=False, indent=1))
    ok = [r["id"] for r in rows if r["verdict"] == "OK"]
    OUT.write_text(json.dumps(
        {"generated": datetime.now(timezone.utc).isoformat(),
         "criterion": f"whisper 复核相似度 >= {SIM_OK}",
         "checked": len(rows), "whitelisted": len(ok), "ids": ok},
        ensure_ascii=False, indent=1))
    print(f"\n体检 {len(rows)} 条: {tally}")
    print(f"白名单 {len(ok)} 条 → {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
