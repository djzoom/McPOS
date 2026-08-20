#!/usr/bin/env python3
# coding: utf-8
"""发布链路体检 —— 只查本地状态与路径,不花配额,可随时复跑。

为什么要有这个:2026-08-18/19 连着两次险情都**不在音频里**,而在发布层的
状态与指针 ——
  · recall 每次运行都重新推导删除目标 → 差一步删掉刚上线的三期
  · 撤回后 hold 冻结了装着新内容的行 → 那期会静默地永不上传,到期开天窗
两次都是「看出来的」,不是「被拦住的」。内容有十一道门,发布层却一道没有,
这就是本脚本要补的位。

九项检查,任一不过即非零退出(可挂进 daily_ops 或 CI):
  P1 产物齐全   每行 output/srt/cover 三件都在
  P2 路径归属   三件产物必须落在**本行 episode_id 的目录**里 —— 防串期
                (主表是脚本批量改写的,一个下标错位就会把 A 期的视频
                 传成 B 期,而文件都存在、时长也对,肉眼极难发现)
  P3 时长一致   视频 ≈ 混音(±1.5s)
  P4 字幕三语   en/zh-Hans/zh-Hant 条数一致、时间轴逐条一致
  P5 内容门     session.json 里有 content_gate 且 pass
  P6 标志合法   recall_needed/hold/video_id 的组合不自相矛盾
  P7 排期       日期严格递增、未来期均为周六、时间 19:00 ET
  P8 标题同步   主表 title 与 upload_meta 真源一致
  P9 分子在位   被引用的分子音频文件都还在库里

  ./.venv/bin/python scripts/sg/audit_publish_chain.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT.parent / "config" / "sg_schedule_master.json"
SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"
MOL_MANIFEST = Path.home() / "Studio/Library/sg/molecules/manifest.json"
TOL_DUR = 1.5          # 视频与混音时长容差(秒)


def _dur(p: Path) -> float | None:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def _cues(p: Path) -> list[tuple[str, str]]:
    """SRT → [(时间轴, 文本)];解析失败返回空表。"""
    if not p.exists():
        return []
    out = []
    for blk in p.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = [x for x in blk.split("\n") if x.strip()]
        if len(lines) >= 3:
            out.append((lines[1].strip(), " ".join(lines[2:]).strip()))
    return out


def main() -> int:
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    rows = master.get("episodes", [])
    bad: list[str] = []
    warn: list[str] = []
    today = date.today()

    mol_paths = {m["id"]: Path(m["path"])
                 for m in json.loads(MOL_MANIFEST.read_text()).get("molecules", [])} \
        if MOL_MANIFEST.exists() else {}

    prev_date = ""
    for r in rows:
        n = r.get("episode_number")
        eid = r.get("episode_id") or ""
        tag = f"Ep{n}"
        d = SESSIONS / eid

        # P1 + P2:三件产物存在,且必须在本行自己的目录里
        for key in ("output_file", "srt_file", "cover_file"):
            v = r.get(key)
            if not v:
                bad.append(f"{tag} 缺字段 {key}")
                continue
            p = Path(v)
            if not p.exists():
                bad.append(f"{tag} {key} 文件不存在: {p.name}")
                continue
            if p.parent != d or not p.name.startswith(eid):
                bad.append(f"{tag} {key} 串期!指向 {p.parent.name}/{p.name} "
                           f"而本行是 {eid}")

        meta_p = d / f"{eid}_session.json"
        if not meta_p.exists():
            bad.append(f"{tag} 缺 session.json({eid})")
            continue
        meta = json.loads(meta_p.read_text(encoding="utf-8"))

        # P3 时长一致
        vid = Path(r.get("output_file") or "")
        mix = d / f"{eid}_final_mix.mp3"
        if vid.exists() and mix.exists():
            dv, dm = _dur(vid), _dur(mix)
            if dv is None or dm is None:
                bad.append(f"{tag} 时长探测失败(不静默兜底)")
            elif abs(dv - dm) > TOL_DUR:
                bad.append(f"{tag} 视频 {dv:.1f}s 与混音 {dm:.1f}s 差 "
                           f"{abs(dv-dm):.1f}s > {TOL_DUR}s")

        # P4 三语字幕对齐
        en = _cues(Path(r.get("srt_file") or ""))
        if not en:
            bad.append(f"{tag} 英文字幕为空或解析失败")
        for suf in (".zh-Hans", ".zh-Hant"):
            zh = _cues(d / f"{eid}{suf}.srt")
            if not zh:
                bad.append(f"{tag} 缺 {suf} 字幕")
            elif len(zh) != len(en):
                bad.append(f"{tag} {suf} 条数 {len(zh)} ≠ 英文 {len(en)}")
            elif [t for t, _ in zh] != [t for t, _ in en]:
                bad.append(f"{tag} {suf} 时间轴与英文不一致")

        # P5 内容门(原子期没有内容门,只查分子期)
        if eid.startswith("sg_mol"):
            g = meta.get("content_gate") or {}
            if not g.get("pass"):
                bad.append(f"{tag} 内容门未放行或无判决")

        # P6 标志组合
        if r.get("hold") and r.get("status") == "ready":
            bad.append(f"{tag} 既 hold 又 ready —— 冻结会让它永不上传")
        if r.get("recall_needed") and not r.get("recall_video_id"):
            bad.append(f"{tag} recall_needed 但无 recall_video_id(无从下手)")
        if r.get("recall_video_id") and r.get("recall_video_id") == r.get("video_id"):
            bad.append(f"{tag} 待删 ID 与当前内容指针相同 —— 会删掉在播内容")

        # P7 排期
        sd = r.get("schedule_date") or ""
        if sd <= prev_date:
            bad.append(f"{tag} 排期 {sd} 未严格递增(前一期 {prev_date})")
        prev_date = sd
        if sd and sd >= today.isoformat():
            wd = date.fromisoformat(sd).weekday()
            if wd != 5:
                warn.append(f"{tag} 排期 {sd} 不是周六(周{wd+1})")
            if not str(r.get("publish_at", "")).startswith(f"{sd}T19:00:00-0"):
                warn.append(f"{tag} publish_at 非 19:00 ET: {r.get('publish_at')}")

        # P9 分子在位
        for mid in meta.get("molecule_ids") or []:
            p = mol_paths.get(mid)
            if p is None:
                bad.append(f"{tag} 分子 {mid} 已不在库清单里")
            elif not p.exists():
                bad.append(f"{tag} 分子音频缺失 {p.name}")

    # P8 标题真源
    r8 = subprocess.run([sys.executable, str(Path(__file__).parent / "upload_meta.py"),
                         "--sync-check"], capture_output=True, text=True)
    if "一致" not in r8.stdout:
        bad.append(f"标题真源与主表不一致: {r8.stdout.strip()[:120]}")

    print(f"═══ 发布链路体检 · {len(rows)} 期 ═══")
    for w in warn:
        print(f"  ⚠ {w}")
    for b in bad:
        print(f"  ❌ {b}")
    if not bad:
        print(f"  ✅ 九项全过(警告 {len(warn)} 条)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
