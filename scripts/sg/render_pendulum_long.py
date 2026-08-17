#!/usr/bin/env python3
# coding: utf-8
"""长视频摆锤层 —— 金环之外的第二种视觉(2026-08-17 用户点题:摆锤)。

与金环层同一套因果观:**声音和光是同一个因的两个果**。语音起点让锤球
亮起一拍,音乐 RMS 让光晕慢呼吸 —— 摆本身按自己的周期走,谁也不追谁。

视觉:一根极细的金线从画幅上缘垂下,末端一颗柔光锤球,8 秒一个整摆
(睡眠节律,比舞台催眠的 2-3 秒慢得多);摆幅 ±12° 并随音乐微息。
色板与金环层同一组暗青铜→暖金,同一种气质。

性能:沿用金环层的「只算所在扇区」思路 —— 摆只扫过 ±(A+ε) 的扇区,
预处理一次扇区像素的极坐标,每帧只是几次 numpy 运算。
编码沿用分块并行直灌 ffmpeg,峰值磁盘 = 成品大小。

  ./.venv/bin/python scripts/sg/render_pendulum_long.py --session sg_mol_smoke --seconds 40
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_rings_long import (          # noqa: E402
    BG_DIM, BG_DIR, FPS, H, SUB_FADE, SUB_SIZE, W,
    draw_subtitle, load_font, rms_envelope, speech_onsets)
from sg_media import probe_duration_or_die  # noqa: E402

SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"

# ── 摆的几何与节律 ──
PIVOT_Y = -0.06 * H     # 悬点略高于画幅上缘:画面里只见线,不见机括
LINE_LEN = 0.78 * H     # 线长(悬点到锤心)
SWING_A = math.radians(12.0)   # 摆幅
SWING_T = 8.0           # 整摆周期(秒):睡眠节律,不是舞台催眠
BOB_R = 16.0            # 锤球芯半径(px)
GLOW_R = 90.0           # 柔光半径
LINE_HW = 0.55          # 线半宽:与金环线宽同级,同一种细
# 色板沿用金环层(同一品牌气质)
WARM_LO = np.float32([108, 84, 36])
WARM_HI = np.float32([147, 150, 118])
DECAY, STRIKE_LEN = 0.9, 3.0    # 锤球亮起的拖尾(比环的击打更绵长)


def build_sector(cx: float, py: float):
    """预处理摆扫过的扇区像素:极坐标 + 索引,每帧只算这些。"""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx, dy = xx - cx, yy - py
    rad = np.hypot(dx, dy)
    ang = np.arctan2(dx, dy)          # 相对竖直向下的偏角
    # 余量必须盖住锤球柔光:L·sin(margin) ≥ GLOW_R+BOB_R,
    # 否则柔光被扇区边界切出直边(首版实测 4° 只够 59px)。
    margin = math.radians(8.0)
    sel = (np.abs(ang) < SWING_A + margin) & \
          (rad < LINE_LEN + BOB_R + GLOW_R) & (yy >= 0)
    idx = np.flatnonzero(sel.ravel())
    r = rad.ravel()[idx].copy()
    g = ang.ravel()[idx].copy()
    # 扇区边缘软窗:柔光高斯尾衰减很慢,硬边界会切出可见直边(实测两版)。
    # 角向与径向都在最后 3°/40px 内余弦渐没,任何贡献到边界必为零。
    edge_w = (np.clip(((SWING_A + margin) - np.abs(g))
                      / math.radians(3.0), 0, 1)
              * np.clip((LINE_LEN + BOB_R + GLOW_R - r) / 40.0, 0, 1)
              ).astype(np.float32)
    return idx, r, g, edge_w


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--seconds", type=float, default=40.0)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--bg", default=None)
    ap.add_argument("--still", type=float, default=None)
    a = ap.parse_args()

    D = SESSIONS / a.session
    meta = json.loads((D / f"{a.session}_session.json").read_text())
    plan = meta.get("plan") or []
    vo = D / f"{a.session}_vo.mp3"
    bed = D / f"{a.session}_bed.mp3"
    mix = D / f"{a.session}_final_mix.mp3"
    out = a.out or (D / f"{a.session}_pendulum_sample.mp4")
    if a.seconds <= 0:
        a.seconds = max(0.0, probe_duration_or_die(mix, "final_mix") - a.start)
        if a.out is None:
            out = D / f"{a.session}_pendulum.mp4"

    onsets = [t for t in speech_onsets(vo)
              if a.start <= t < a.start + a.seconds]
    frames = int(a.seconds * FPS)
    env = rms_envelope(bed, 1.0 / FPS, frames + int(a.start * FPS))[int(a.start * FPS):]

    plate = np.zeros((H, W, 3), dtype=np.float32)
    bgs = sorted(BG_DIR.glob("*.png"))
    if bgs:
        from PIL import Image
        pick = bgs[len(bgs) // 3]
        if a.bg:
            pick = bgs[int(a.bg) % len(bgs)] if a.bg.isdigit() else \
                next((b for b in bgs if a.bg in b.stem), pick)
        plate = np.asarray(Image.open(pick).convert("RGB").resize((W, H)),
                           dtype=np.float32) * BG_DIM
        print(f"  背景 {pick.stem[:52]}")

    from build_session import subtitle_typography
    plan_atoms = [p for p in plan if p.get("type") == "atom"]
    subs = []
    for i, p in enumerate(plan_atoms):
        if p.get("vo_start_sec") is None:
            continue
        prev = plan_atoms[i - 1] if i else None
        cont = bool(prev and prev.get("source_master") == p.get("source_master")
                    and int(p.get("source_sequence_index", -1))
                    == int(prev.get("source_sequence_index", -2)) + 1)
        subs.append((float(p["vo_start_sec"]), float(p["vo_end_sec"]),
                     subtitle_typography(p.get("text") or "", continues_prev=cont)))
    font = load_font(SUB_SIZE)
    print(f"  字幕 {len(subs)} 条 · 语音起点 {len(onsets)} 处")

    cx = W / 2.0
    idx, rad, ang, edge_w = build_sector(cx, PIVOT_Y)
    print(f"  扇区像素 {idx.size}(全幅 {W*H} 的 {idx.size/(W*H):.1%})")

    strike = np.zeros(frames, dtype=np.float32)
    for t in onsets:
        s = int((t - a.start) * FPS)
        for off in range(int(STRIKE_LEN * FPS)):
            if 0 <= s + off < frames:
                strike[s + off] = max(strike[s + off],
                                      math.exp(-off / (FPS * DECAY)))

    def draw(f: int) -> np.ndarray:
        t = a.start + f / FPS
        img = plate.copy()
        breathe = 1.0 + 0.30 * (env[f] if f < env.size else 0.0)
        s = float(strike[f]) if f < strike.size else 0.0
        theta = SWING_A * math.sin(2 * math.pi * t / SWING_T)
        # 线:到摆线的垂距(小角近似在 ±16° 内误差可忽略)
        d_line = rad * np.sin(ang - theta)
        on_line = np.clip(rad / LINE_LEN, 0, 1) * (rad <= LINE_LEN)
        line_i = np.exp(-(np.abs(d_line) / (LINE_HW + 0.8)) ** 2) * on_line
        # 锤球:芯 + 柔光(余弦定理求到锤心距离)
        d_bob = np.sqrt(np.maximum(
            rad * rad + LINE_LEN * LINE_LEN
            - 2 * rad * LINE_LEN * np.cos(ang - theta), 0.0))
        core = np.exp(-(d_bob / BOB_R) ** 2)
        glow = np.exp(-(d_bob / (GLOW_R * (1 + 0.18 * s))) ** 1.6)
        vis = (0.55 * line_i + 1.0 * core
               + (0.16 + 0.22 * s) * glow) * breathe * edge_w
        v = np.clip(vis, 0.0, 3.0).astype(np.float32)
        vv = np.minimum(1.0, v * 1.35)
        # alpha 不设常数基值:金环版的基值有 band 覆盖率压零,这里没有 band,
        # 常数基值会把整个摆扫扇区提亮成一个可见的三角楔(首版实测)。
        al = np.clip(340.0 * v, 0, 255) / 255.0
        flat = img.reshape(-1, 3)
        for c in range(3):
            warm = WARM_LO[c] + WARM_HI[c] * vv
            flat[idx, c] = flat[idx, c] * (1 - al) + warm * al
        for s0, s1, txt in subs:
            if s0 - SUB_FADE <= t <= s1 + SUB_FADE:
                al2 = ((t - (s0 - SUB_FADE)) / SUB_FADE if t < s0
                       else 1.0 - (t - s1) / SUB_FADE if t > s1 else 1.0)
                img = draw_subtitle(img, txt, max(0.0, min(1.0, al2)), font)
                break
        return np.clip(img, 0, 255).astype(np.uint8)

    if a.still is not None:
        from PIL import Image
        png = out.with_name(out.stem + f"_still{a.still:g}.png")
        Image.fromarray(draw(int((a.still - a.start) * FPS))).save(png)
        print(f"✅ 单帧 {png}")
        return 0

    def render_chunk(args):
        lo, hi, path = args
        enc = subprocess.Popen(
            ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo",
             "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
             "-i", "pipe:0", "-c:v", "libx264", "-preset", "medium",
             "-crf", "19", "-g", str(FPS), "-keyint_min", str(FPS),
             "-sc_threshold", "0", "-pix_fmt", "yuv420p", path],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE)
        try:
            for f in range(lo, hi):
                enc.stdin.write(draw(f).tobytes())
        finally:
            enc.stdin.close()
        if enc.wait() != 0:
            raise RuntimeError(f"段 {path} 编码失败")
        return path

    with tempfile.TemporaryDirectory() as td:
        nproc = max(1, min(a.jobs or (os.cpu_count() or 4) - 2, 12))
        nchunk = nproc if (nproc > 1 and frames >= nproc * 8) else 1
        step = -(-frames // nchunk)
        jobs = [(i, min(i + step, frames), str(Path(td) / f"c{k:03d}.mp4"))
                for k, i in enumerate(range(0, frames, step))]
        print(f"    {len(jobs)} 段 × {nproc} 线程")
        if len(jobs) == 1:
            parts = [render_chunk(jobs[0])]
        else:
            with cf.ThreadPoolExecutor(max_workers=nproc) as ex:
                parts = list(ex.map(render_chunk, jobs))
        concat = Path(td) / "concat.txt"
        concat.write_text("".join(f"file '{p}'\n" for p in parts))
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
             "-i", str(concat), "-ss", f"{a.start:.3f}",
             "-t", f"{a.seconds:.3f}", "-i", str(mix),
             "-map", "0:v", "-map", "1:a", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "192k", "-shortest",
             "-movflags", "+faststart", str(out)],
            capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr[-500:])
            return 1
    got = probe_duration_or_die(out, "pendulum")
    print(f"✅ {out} · 时长 {got:.1f}s(期望 {frames/FPS:.1f}s)")
    return 0 if abs(got - frames / FPS) <= 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
