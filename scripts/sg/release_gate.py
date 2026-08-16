#!/usr/bin/env python3
# coding: utf-8
"""一期节目能不能发 —— 把散在四处的门禁串成**单一裁决**。

在此之前,「这期到底过没过」要跑四个脚本、看四种输出格式,而且每个脚本
只管自己那一段:build_session 出片时过了内容门禁与 VO 检测门,qc_session
另外跑 B 层,中文字幕的十道门在第三个脚本里,连排重叠度在第四个。
于是「三期成品已交付」这句话,谁也说不清到底代表哪几关过了。

七关,任何一关不过就不可发布(--strict 下警告也算不过):

  R1 产物齐全      vo / bed / final_mix / srt / session.json / rings.mp4
  R2 内容门禁      audit_plan_content —— 半截句、指代硬切、隔离泄漏…
  R3 VO 检测门     vo_score ≥95(时序 40 / 清晰 30 / 结构 30)
  R4 音画一致      qc_session B 层:WER ≤6% · 漏句 0 · 多出片段 0
  R5 边界完整      片中无「双证确凿削词且无紧邻补救」的原子
  R6 中文字幕      简繁两版存在、条数与时间轴同英文逐条对齐
  R7 时长一致      final_mix / rings.mp4 / session.json 三处时长互相吻合

R4 要跑 whisper 反查(分钟级),其余都是秒级。--fast 跳过 R4 用于迭代中途
自查;**发布前必须跑全套** —— 只有 R4 能发现音频与字幕对不上。

  ./.venv/bin/python scripts/sg/release_gate.py --session sg_gold_001
  ./.venv/bin/python scripts/sg/release_gate.py --all --fast
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_session as bs
from atom_quality import tail_truncated
from vo_score import WAVEFORM_REPAIR_GAP, _is_continuation, score_plan

SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"
HERE = Path(__file__).resolve().parent
PY = Path(__file__).resolve().parents[2] / ".venv/bin/python"
DUR_TOLERANCE = 1.0     # 三处时长互差超过这么多秒即判不一致


class Result:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, bool, str]] = []

    def add(self, key: str, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append((key, name, ok, detail))

    @property
    def ok(self) -> bool:
        return all(r[2] for r in self.rows)


from sg_media import probe_duration as probe  # noqa: E402


def srt_times(path: Path) -> list[str]:
    return re.findall(r"^\d\d:\d\d:\d\d,\d\d\d --> .*$",
                      path.read_text(encoding="utf-8"), re.M)


def check(session: str, *, fast: bool) -> Result:
    R = Result()
    D = SESSIONS / session
    meta_path = D / f"{session}_session.json"

    # —— R1 产物齐全 ——
    need = {
        "vo": D / f"{session}_vo.mp3",
        "bed": D / f"{session}_bed.mp3",
        "mix": D / f"{session}_final_mix.mp3",
        "srt": D / f"{session}.srt",
        "meta": meta_path,
        "video": D / f"{session}_rings.mp4",
    }
    missing = [k for k, p in need.items() if not p.exists()]
    R.add("R1", "产物齐全", not missing,
          "缺 " + "/".join(missing) if missing else
          f"{len(need)} 件齐备")
    if not meta_path.exists():
        return R

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    plan = meta.get("plan") or []
    atoms = [p for p in plan if p.get("type") == "atom"]

    # —— R2 内容门禁(现场重算,不信 session.json 里存的旧结论)——
    grammar = bs.load_grammar(Path(meta.get("grammar_path")
                                   or bs.DEFAULT_GRAMMAR))
    audit = bs.audit_plan_content(plan, grammar)
    R.add("R2", "内容门禁", bool(audit.get("ok")),
          "; ".join(audit.get("errors") or [])[:80] or f"{len(atoms)} 条原子全过")

    # —— R3 VO 检测门 ——
    verdict = score_plan({**meta, "audit": audit, "plan": plan})
    R.add("R3", "VO 检测门", verdict["pass"],
          f"{verdict['score']} 分(时序 {verdict['timing']}/40 · "
          f"清晰 {verdict['clarity']}/30 · 结构 {verdict['structure']}/30)"
          + ("" if verdict["pass"] else " ← " + (verdict["notes"] or [""])[0][:50]))

    # —— R5 边界完整 ——
    # 标记一律从**当前 manifest** 取,不信 session.json 里的快照:出片当时
    # 若还没跑过边界审计,plan 里就没有 tail_hard_cut 字段,照着它查等于
    # 每期都报「无确凿削词」——2026-08-12 拿 qc03 试出来的,那期实测 45.6%
    # 病态原子却全绿。门禁读陈旧数据,就是在发通行证。
    live = {x["id"]: x for x in
            json.loads((Path.home() / "Studio/Library/sg/atoms/manifest.json")
                       .read_text(encoding="utf-8"))["atoms"]}
    # 「已不在库中」分两种:文件还在 = 素材库演进了(重采/重建),成品完好且
    # 可修复,只提示;文件也没了 = 成品失去修复能力、出处不可考,才算不过。
    # 2026-08-14 实测:重采两支母带后,已交付四期的 27+ 条旧原子出库,
    # 音频全部烘焙在成片里、R4 反查照过 —— 按旧判据四期全数误判不可发布。
    stale = [p for p in atoms if p["id"] not in live]
    stale_lost = [p["id"] for p in stale if not Path(p.get("path", "")).exists()]
    merged = [{**p, **{k: live[p["id"]].get(k) for k in
                       ("tail_cut", "tail_hard_cut", "head_cut")}}
              if p["id"] in live else p for p in atoms]
    broken = [i + 1 for i, p in enumerate(merged)
              if tail_truncated(p) and not (
                  i + 1 < len(merged)
                  and _is_continuation(p, merged[i + 1], WAVEFORM_REPAIR_GAP))]
    quarantined = [i + 1 for i, p in enumerate(atoms)
                   if live.get(p["id"], {}).get("quarantined")]
    R.add("R5", "边界完整", not broken and not quarantined and not stale_lost,
          "; ".join(filter(None, [
              f"确凿削词 cue {broken}" if broken else "",
              f"含已隔离原子 cue {quarantined}" if quarantined else "",
              f"{len(stale_lost)} 条原子文件已丢失" if stale_lost else "",
              (f"另 {len(stale)-len(stale_lost)} 条已出库(文件仍在,成品可修复)"
               if len(stale) > len(stale_lost) else ""),
          ])) or "无确凿削词、无隔离原子")

    # —— R6 中文字幕 ——
    en = D / f"{session}.srt"
    hans, hant = D / f"{session}.zh-Hans.srt", D / f"{session}.zh-Hant.srt"
    if not (hans.exists() and hant.exists()):
        R.add("R6", "中文字幕", False, "简/繁 SRT 缺失")
    else:
        t_en, t_s, t_t = srt_times(en), srt_times(hans), srt_times(hant)
        same = t_en == t_s == t_t
        R.add("R6", "中文字幕", same,
              f"简繁各 {len(t_s)} 条,时间轴与英文逐条一致" if same
              else f"条数/时间轴不符 en {len(t_en)} · 简 {len(t_s)} · 繁 {len(t_t)}")

    # —— R7 时长一致 ——
    dm, dv = probe(need["mix"]), probe(need["video"])
    dj = float(meta.get("total_duration_sec") or 0)
    vals = [x for x in (dm, dv, dj) if x]
    spread = (max(vals) - min(vals)) if len(vals) == 3 else 999.0
    R.add("R7", "时长一致", spread <= DUR_TOLERANCE,
          f"混音 {dm and dm/60:.2f} min · 视频 {dv and dv/60:.2f} min · "
          f"元数据 {dj/60:.2f} min(互差 {spread:.2f}s)"
          if len(vals) == 3 else "无法读出三处时长")

    # —— R4 音画一致(最慢,放最后)——
    if fast:
        R.add("R4", "音画一致", True, "⏭ --fast 跳过(发布前必须跑)")
    else:
        r = subprocess.run([str(PY), str(HERE / "qc_session.py"),
                            "--session", session], capture_output=True, text=True)
        out = r.stdout
        m = re.search(r"B1 WER ([\d.]+)%", out)
        miss = re.search(r"B2 漏句 (\d+)", out)
        extra = re.search(r"B3 音频多出剧本没有的片段 (\d+)", out)
        ok = r.returncode == 0 and bool(m)
        detail = (f"WER {m.group(1)}% · 漏句 {miss.group(1) if miss else '?'}"
                  f" · 多出 {extra.group(1) if extra else '?'}") if m else "未跑出结果"
        R.add("R4", "音画一致", ok, detail)
    return R


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--session")
    g.add_argument("--all", action="store_true", help="检所有 sg_gold_* 期")
    ap.add_argument("--fast", action="store_true", help="跳过 R4(whisper 反查)")
    a = ap.parse_args()

    sessions = ([a.session] if a.session else
                sorted(p.name for p in SESSIONS.iterdir()
                       if p.is_dir() and p.name.startswith("sg_gold_")))
    all_ok = True
    for s in sessions:
        R = check(s, fast=a.fast)
        mark = "✅ 可发布" if R.ok else "❌ 不可发布"
        print(f"\n=== {s} · {mark} ===")
        for key, name, ok, detail in sorted(R.rows):
            print(f"  {'✅' if ok else '❌'} {key} {name:<8} {detail}")
        all_ok &= R.ok
    print(f"\n{'✅ 全部可发布' if all_ok else '❌ 有未过关的期次'}"
          f"({len(sessions)} 期)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
