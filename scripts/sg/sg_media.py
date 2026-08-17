#!/usr/bin/env python3
# coding: utf-8
"""ffmpeg / ffprobe 的公共封装 —— 时长探测只此一份。

`probe_duration` 曾在六个脚本里各抄了一份,其中五份在探测失败时返回 `0.0`。
2026-08-11 查出的 222 条时长漂移就出在这上面:

    duration_sec = round(probe_duration(out) or (t1 - t0), 3)
                                          ^^^^ 0.0 被当成「没测到」,
    于是悄悄换成母带时间戳跨度 —— 两者最大差 7.66s(标称 11.85 / 实际 4.19)。

时长是选片打分、语速门、密度填充与发布门禁 R7 的共同输入,错一处全线错。
所以这里的契约是:**测不出就返回 None**,让调用方无法假装没事。
需要兜底的地方必须把兜底**写出来**(`probe_duration(p) or DEFAULT`),
那样至少读代码时看得见。
"""
from __future__ import annotations

import datetime as _dt
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def backup_with_retention(src: Path, tag: str, keep: int = 5) -> Path:
    """备份一份,并只保留最近 keep 份同类备份。

    manifest 每次隔离/校正都留一份,一天下来堆了 14 份 20MB,而真正会被
    回滚到的只有最近那一两份。不设上限的备份最后没人敢删,也没人看。
    """
    src = Path(src)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = src.with_suffix(f"{src.suffix}.bak_{tag}_{stamp}")
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    olds = sorted(src.parent.glob(f"{src.name}.bak_{tag}_*"), reverse=True)
    for p in olds[keep:]:
        p.unlink()
    return dst


def probe_duration(path: str | Path) -> float | None:
    """媒体文件时长(秒);读不出返回 **None**,不是 0.0。"""
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def probe_duration_or_die(path: str | Path, what: str = "") -> float:
    """时长探不出就**停下来**。

    给那些「拿到 0 就会静默出错」的地方用:视频渲染按 0 秒会渲出空片,
    混音按 0 秒会把人声轨截没。与其产出一个坏成品,不如当场报错。
    """
    d = probe_duration(path)
    if d is None or d <= 0:
        raise SystemExit(f"读不出时长{('(' + what + ')') if what else ''}: {path}")
    return d


def measure_loudness(path: str | Path) -> dict | None:
    """整段响度实测:integrated LUFS / LRA / true peak。探测失败返 None,不猜。

    用 loudnorm 的测量模式(print_format=json)而不是 ebur128 文本抓行 ——
    JSON 是稳定契约,文本格式随 ffmpeg 版本漂。
    """
    import json as _json
    import re as _re
    import subprocess as _sp
    r = _sp.run(
        ["ffmpeg", "-hide_banner", "-i", str(path),
         "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True)
    m = _re.search(r"\{[^{}]*\}", r.stderr[-2500:])
    if not m:
        return None
    try:
        d = _json.loads(m.group(0))
        return {"I": float(d["input_i"]), "LRA": float(d["input_lra"]),
                "TP": float(d["input_tp"])}
    except (KeyError, ValueError):
        return None
