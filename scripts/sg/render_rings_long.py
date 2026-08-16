#!/usr/bin/env python3
# coding: utf-8
"""长视频金环层 —— 从既有音频导出事件,而不是让画面追音频。

借鉴 TOYTUNE 的 S1「金线轨道」。读那边的代码才发现关键点和直觉相反:

    几何事件表 events ──┬──→ make_audio()   每个事件敲一次钟
                       └──→ strike_map()   同一时刻点亮金环

**声音和光是同一个因的两个果**,不是谁跟随谁 —— 这才是它看起来「有因果」
而不是「音乐可视化」的原因。

但 SiG 的音频**已经存在**(原子 VO + CHL500 音乐床),不是由事件合成的。
所以要反过来:从既有音频里导出事件表,再喂给同一套视觉。

两段不同的事件源(VO 大约 17 分钟就结束,后面四十多分钟只有音乐):

    前段  语音起点 = 一次击打        直接从 VO 波形取,不依赖时间轴换算
    后段  音乐节拍 = 一次击打        (待接:曲目 BPM 缓存)
    全程  音乐 RMS = 慢变量          环半径呼吸 + 基础亮度,不做击打

渲染方式也换了。TOYTUNE 每帧调 600 次 PIL arc(),1080×1920 单帧 187ms,
60 分钟要 5.6 小时。这里改为**只在环带内的像素上算**:像素索引、角度、
径向权重全部预处理一次,之后每帧只是几次 numpy 运算 —— 单帧 49ms。
顺带画质更好:原版靠 width=2 的硬边圆弧,改成高斯径向权重后天然抗锯齿。

  ./.venv/bin/python scripts/sg/render_rings_long.py --session qc05 --seconds 40
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

SESSIONS = Path.home() / "Studio/Workspace/outputs/sg/sessions"
# 字幕字体:Cochin 是法国旧体,笔画细、衬线优雅,和金线是同一种气质;
# Baskerville / Hoefler Text 作退路。避开 Times 与无衬线 —— 太世俗。
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Cochin.ttc",
    "/System/Library/Fonts/Supplemental/Baskerville.ttc",
    "/System/Library/Fonts/Supplemental/Hoefler Text.ttc",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
]
SUB_SIZE = 40
SUB_FADE = 0.7        # 淡入淡出秒数。字不能「跳」出来,要浮出来
SUB_Y = 0.86          # 基线位置(占画高比例),压在环外、画面下方
SUB_MAXW = 0.62       # 单行最大宽度(占画宽),超出则折行
BG_DIM = 0.28         # 背景压暗系数
BG_DIR = Path.home() / "Projects/TOYTUNE/assets/backgrounds"
W, H, FPS = 1920, 1080, 30

# 三环:半径按**黄金比例**间隔(1 : 1.618 : 2.618),与 TOYTUNE 一致 ——
# 这是它看着和谐的原因之一。外环取到半高的 87%,几乎顶到画幅上下缘:
# 竖屏里外环占半宽 85% 才有包裹感,横屏若照搬绝对半径就只占半宽 43%,
# 左右全是空的,那股「被环住」的感觉就没了。
# 周期取互质的秒数,三环不会很快回到同一相位。
_R = 180.0
RINGS = [
    dict(radius=_R,           period=23.0, dir=1),
    dict(radius=_R * 1.618,   period=31.0, dir=-1),
    dict(radius=_R * 2.618,   period=41.0, dir=1),
]
# —— 以下三组数值是**实测竖屏成片**反推的,不是调出来的 ——
# 从 ep010 抽帧沿半径切剖面:线宽 1–3px(主要 2px);环的暗部只比背景亮
# 13–43,金冠却是 254 饱和 —— 同一根环内动态范围极大,大部分几乎看不见。
# 我第一版整环都在发光(暗部高出背景 116),所以显得又粗又亮。
#
# 关键是它用 **alpha 合成**而不是加法叠加:PIL 的 arc(width=2, fill=(*warm, a)),
# 颜色底是暗青铜 (108,84,36),alpha 从 14 起步、随亮度爬到 255。
# 加法叠加没有这个「暗部压到近乎透明」的特性,所以怎么调都偏胖。
# 线宽/强度（2026-08-06 用户令：金线要更细更弱，向竖版看齐）。
# 竖版 S1 用 PIL width=2 的硬边弧，颜色与 alpha 公式两版本来就一致
# （14+330·vis、108+147v 系列），所以"看齐"要调的只有宽度。
# 原值 HALFW=1.0 + EDGE=0.6 ≈ 3.2px 总宽，比竖版粗六成。
HALFW = 0.5          # 线的半宽(像素)；+EDGE 后总宽 ≈ 2.2px，对齐竖版的 2px
EDGE = 0.6           # 边缘过渡宽度（抗锯齿，别再调小，否则回到硬边锯齿）
WARM_LO = (108.0, 84.0, 36.0)     # vis→0 时的暗青铜
WARM_HI = (147.0, 150.0, 118.0)   # 随 vis 加上去的增量
ALPHA_BASE, ALPHA_GAIN = 14.0, 330.0   # 与竖版同式；--ring-gain 可整体压弱
CREST = 1.8          # 与参考一致
DECAY = 0.55        # 击打拖尾时间常数(秒)
STRIKE_LEN = 2.4    # 拖尾总长(秒)


from sg_media import probe_duration, probe_duration_or_die  # noqa: E402


def speech_onsets(vo: Path, floor_db: int = -45, min_sil: float = 0.45) -> list[float]:
    """VO 里每一句话的起点。

    用静音检测的**补集**,不做起音检测:这条线的静音是刻意设计的大间隔,
    句子之间界限清楚,静音边界比能量峰值可靠得多。
    """
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(vo), "-af",
         f"silencedetect=noise={floor_db}dB:d={min_sil}", "-f", "null", "-"],
        capture_output=True, text=True)
    ends = [float(v) for k, v in
            re.findall(r"silence_(start|end): ([-\d.]+)", r.stderr) if k == "end"]
    starts = [float(v) for k, v in
              re.findall(r"silence_(start|end): ([-\d.]+)", r.stderr) if k == "start"]
    onsets = list(ends)
    if not starts or starts[0] > 0.05:
        onsets.insert(0, 0.0)          # 开头就有声音
    return sorted(onsets)


def rms_envelope(path: Path, hop: float, n: int) -> np.ndarray:
    """整轨 RMS 包络,每 hop 秒一格,归一到 0–1。给慢变量用。"""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "8000",
         "-f", "s16le", "-"], capture_output=True)
    a = np.frombuffer(r.stdout[: len(r.stdout) // 2 * 2], dtype=np.int16)
    if a.size == 0:
        return np.zeros(n, dtype=np.float32)
    w = max(1, int(8000 * hop))
    m = a[: a.size // w * w].reshape(-1, w).astype(np.float32)
    env = np.sqrt((m ** 2).mean(axis=1)) / 32768.0
    env = env / max(1e-6, float(np.percentile(env, 98)))
    out = np.zeros(n, dtype=np.float32)
    out[: min(n, env.size)] = np.clip(env[:n], 0, 1)
    return out


def _bar(x, y, cx, cy, half_len, half_wid, vertical):
    along = np.abs((y if vertical else x) - (cy if vertical else cx)) - half_len
    across = np.abs((x if vertical else y) - (cx if vertical else cy)) - half_wid
    return np.hypot(np.maximum(along, 0), np.maximum(across, 0))


def build_cross(cx: float, cy: float, arm: float = 82.0, down: float = 164.0,
                hw: float = 3.0) -> np.ndarray:
    """中心的十字。三环是绕着它转的 —— 没有它,画面就没有锚点。

    做法照搬 TOYTUNE:三层高斯(芯/内晕/外晕)按**概率并集**合成,
    交叉处既不会因叠加而过亮,也不会因取最大值而发暗。
    """
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    mid = cy + (down - arm) / 2
    dv = _bar(xx, yy, cx, mid, (arm + down) / 2, hw, True)
    dh = _bar(xx, yy, cx, cy, arm, hw, False)

    def union(a, b):
        return 1.0 - (1.0 - a) * (1.0 - b)

    core = union(np.exp(-(dv / 1.9) ** 2), np.exp(-(dh / 1.9) ** 2))
    inner = union(np.exp(-(dv / 6.5) ** 2), np.exp(-(dh / 6.5) ** 2))
    halo = union(np.exp(-(dv / 22.0) ** 2), np.exp(-(dh / 22.0) ** 2))
    layer = (core[..., None] * np.float32([255, 246, 214])
             + .34 * inner[..., None] * np.float32([255, 226, 158])
             + .13 * halo[..., None] * np.float32([214, 160, 74]))
    # 落在十字脚下的一道长而淡的光柱,让下半幅不至于空。
    below = np.clip((yy - cy) / 70.0, 0, 1)
    column = (below
              * np.exp(-((xx - cx) / (150 + np.maximum(yy - cy, 0) * .40)) ** 2)
              * np.exp(-(np.maximum(yy - cy, 0) / 780.0) ** 1.7))
    # 泛光必须**很淡**。第一版给到 [120,96,46],整幅被冲成一片金雾,
    # 三道细金线反而被压住 —— 十字是锚点,不是光源。
    glow = np.exp(-(np.hypot((xx - cx) / 1.05, yy - cy) / 420) ** 1.7)
    layer += (glow + .45 * column)[..., None] * np.float32([22, 17, 8])
    return layer.astype(np.float32)


def build_masks(cx: float, cy: float):
    """预处理:每个环只保留环带内的像素,记下角度与径向权重。

    全画幅 numpy 试过 —— 反而更慢(679ms/帧),因为对 200 万像素逐环计算,
    而金线只占极窄一圈。
    """
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rad = np.hypot(xx - cx, yy - cy)
    ang = np.arctan2(yy - cy, xx - cx)
    masks = []
    for ring in RINGS:
        R = ring["radius"]
        sel = np.abs(rad - R) < HALFW + EDGE + 0.5
        idx = np.flatnonzero(sel.ravel())
        masks.append((idx,
                      ang.ravel()[idx].astype(np.float32).copy(),
                      np.clip((HALFW + EDGE - np.abs(rad.ravel()[idx] - R)) / EDGE,
                              0.0, 1.0).astype(np.float32),
                      (rad.ravel()[idx] - R).astype(np.float32)))
    return masks


def load_font(size: int):
    from PIL import ImageFont
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    from PIL import ImageFont as F
    return F.load_default()


def wrap(text: str, font, max_px: int) -> list[str]:
    words_, lines, cur = text.split(), [], ""
    for w in words_:
        trial = (cur + " " + w).strip()
        if font.getlength(trial) <= max_px or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3]


def draw_subtitle(img: np.ndarray, text: str, alpha: float, font) -> np.ndarray:
    """把一句字幕浮在画面下方。

    不描边、不加底框 —— 那是新闻字幕的做法。这里靠**一层极淡的暗晕**把
    文字从背景里托出来,笔画本身保持细,和金线同一种气质。
    """
    if alpha <= 0.01 or not text:
        return img
    from PIL import Image, ImageDraw, ImageFilter
    lines = wrap(text, font, int(W * SUB_MAXW))
    lh = int(SUB_SIZE * 1.42)
    box = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(box)
    y = int(H * SUB_Y) - (len(lines) - 1) * lh // 2
    for i, ln in enumerate(lines):
        d.text((W / 2, y + i * lh), ln, font=font, fill=255, anchor="mm")
    mask = np.asarray(box, dtype=np.float32) / 255.0
    halo = np.asarray(box.filter(ImageFilter.GaussianBlur(11)), dtype=np.float32) / 255.0
    out = img.astype(np.float32)
    out *= (1.0 - 0.55 * halo[..., None] * alpha)          # 先把底压暗
    warm = np.float32([250, 242, 224])
    out = out * (1.0 - (mask * alpha)[..., None]) + warm * (mask * alpha)[..., None]
    return np.clip(out, 0, 255)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=None)
    ap.add_argument("--seconds", type=float, default=40.0,
                    help="渲多长;0 = 整期(由 final_mix 时长减去 --start 推出)")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--jobs", type=int, default=0,
                    help="并行块数;0 = 自动(核数−2)")
    ap.add_argument("--bg", default=None,
                    help="背景图：图名片段或序号；缺省沿用原来的第 1/3 张")
    ap.add_argument("--list-bg", action="store_true", help="列出可用背景图后退出")
    ap.add_argument("--ring-halfw", type=float, default=None,
                    help=f"金线半宽（默认 {0.5}）；越小越细")
    ap.add_argument("--ring-gain", type=float, default=None,
                    help="金线 alpha 增益（默认 330）；越小越弱")
    ap.add_argument("--bg-dim", type=float, default=None,
                    help="背景压暗系数（默认 0.28）")
    ap.add_argument("--still", type=float, default=None,
                    help="只出这一秒的单帧 PNG,用于快速调线宽")
    a = ap.parse_args()

    if a.list_bg:
        for i, b in enumerate(sorted(BG_DIR.glob("*.png"))):
            print(f"{i:3d}  {b.stem}")
        return 0
    if not a.session:
        raise SystemExit("--session 必填（除 --list-bg 外）")

    # 覆盖模块级常量：build_masks 与 draw 都读它们，必须在建 mask 之前改。
    global HALFW, ALPHA_GAIN, BG_DIM
    if a.ring_halfw is not None:
        HALFW = float(a.ring_halfw)
    if a.ring_gain is not None:
        ALPHA_GAIN = float(a.ring_gain)
    if a.bg_dim is not None:
        BG_DIM = float(a.bg_dim)

    D = SESSIONS / a.session
    meta = json.loads((D / f"{a.session}_session.json").read_text())
    plan = meta.get("plan") or []
    vo = D / f"{a.session}_vo.mp3"
    bed = D / f"{a.session}_bed.mp3"
    mix = D / f"{a.session}_final_mix.mp3"
    out = a.out or (D / f"{a.session}_rings_sample.mp4")

    # --seconds 0 = 整期。长度取自 final_mix 而不是 session.json 的
    # total_duration_sec:成品轨才是要配的那条,元数据是编排时的估算(两者曾差近两分钟)。
    if a.seconds <= 0:
        # 读不出成品时长就**停下来**:按 0 秒渲出来的是一个空文件,
        # 而空文件在 release_gate 的 R1/R7 之前不会有人发现。
        a.seconds = max(0.0, probe_duration_or_die(mix, "final_mix") - a.start)
        print(f"整期模式:{a.seconds/60:.1f} min（{mix.name}）")
        if a.out is None:
            out = D / f"{a.session}_rings.mp4"

    print(f"事件源:{vo.name}")
    onsets = [t for t in speech_onsets(vo)
              if a.start <= t < a.start + a.seconds]
    print(f"  语音起点 {len(onsets)} 处(本段 {a.seconds:.0f}s)")
    print(f"  VO 结束于 {meta.get('vo_ends_sec', 0)/60:.1f} min,"
          f"之后 {(meta.get('total_duration_sec',0)-meta.get('vo_ends_sec',0))/60:.1f} min 只有音乐")

    frames = int(a.seconds * FPS)
    env = rms_envelope(bed, 1.0 / FPS, frames + int(a.start * FPS))[int(a.start * FPS):]

    # 背景:取一张暗调的,压暗后作底。--bg 可指名或给序号；缺省仍是原来的 1/3 处，
    # 这样不带参数重跑旧期次画面不变。
    bgs = sorted(p for p in BG_DIR.glob("*.png"))
    plate = np.zeros((H, W, 3), dtype=np.float32)
    if bgs:
        from PIL import Image
        pick = bgs[len(bgs) // 3]
        if a.bg:
            if a.bg.isdigit():
                pick = bgs[int(a.bg) % len(bgs)]
            else:
                hit = [b for b in bgs if a.bg in b.stem]
                if not hit:
                    raise SystemExit(f"找不到背景 '{a.bg}'（共 {len(bgs)} 张，"
                                     f"用 --list-bg 看）")
                pick = hit[0]
        im = Image.open(pick).convert("RGB").resize((W, H))
        plate = np.asarray(im, dtype=np.float32) * BG_DIM
        print(f"  背景 {pick.stem[:52]}")

    # 字幕:用 plan 里的 vo_start_sec / vo_end_sec —— 那是成品轨上的真实位置。
    # plan 的 start_sec 是编排估算,与成品差近两分钟,拿去打字幕会整体错位。
    # 排版修正必须与 .srt 用**同一个函数**:烧进画面的字与外挂字幕是同一句话,
    # 两处各自处理必然分头演化,观众就会看到片里写 "Tonight"、字幕文件写 "tonight"。
    from build_session import subtitle_typography
    plan_atoms = [p for p in plan if p.get("type") == "atom"]
    subs = []
    for i, p in enumerate(plan_atoms):
        if p.get("vo_start_sec") is None:
            continue
        prev = plan_atoms[i - 1] if i else None
        cont = bool(prev
                    and prev.get("source_master") == p.get("source_master")
                    and int(p.get("source_sequence_index", -1))
                    == int(prev.get("source_sequence_index", -2)) + 1)
        subs.append((float(p["vo_start_sec"]), float(p["vo_end_sec"]),
                     subtitle_typography(p.get("text") or "", continues_prev=cont)))
    font = load_font(SUB_SIZE)
    print(f"  字幕 {len(subs)} 条" + ("" if subs else "  ⚠️ plan 里没有 vo_start_sec,请用新版 build_session 重出"))

    cx, cy = W / 2.0, H * 0.46
    masks = build_masks(cx, cy)
    cross = build_cross(cx, cy)
    plate = plate + cross          # 十字是常亮的锚点,不参与击打

    # 每帧的击打强度:起点处为 1,按指数拖尾
    strike = np.zeros(frames, dtype=np.float32)
    for t in onsets:
        s = int((t - a.start) * FPS)
        for off in range(int(STRIKE_LEN * FPS)):
            f = s + off
            if 0 <= f < frames:
                strike[f] = max(strike[f], math.exp(-off / (FPS * DECAY)))

    def draw(f: int) -> np.ndarray:
        t = a.start + f / FPS
        img = plate.copy()
        breathe = 1.0 + 0.035 * (env[f] if f < env.size else 0.0)
        for i, ring in enumerate(RINGS):
            pix, ang, band, dr = masks[i]
            phase = ring["dir"] * 2 * math.pi * t / ring["period"] - math.pi / 2
            lum = (.5 + .5 * np.cos(3.0 * (ang - phase))) ** CREST
            un = ang - phase * .65 + 2 * math.pi * t / 90.0 * ring["dir"]
            grain = ((.5 + .5 * np.sin(un * 37.0 + i * 5.1))
                     * (.5 + .5 * np.sin(un * 13.0 + 2.3 + i * 1.7))) ** .9
            vis = lum * (.30 + .70 * grain) * breathe
            s = float(strike[f]) if f < strike.size else 0.0
            if s > .02:
                arm = round((phase + math.pi / 2) / (math.pi / 2)) * (math.pi / 2) - math.pi / 2
                gap = np.abs((ang - arm + math.pi) % (2 * math.pi) - math.pi)
                spread = .30 + 2.2 * (1.0 - s)
                vis = vis + np.exp(-(gap / spread) ** 2) * s * (.55 + .45 * lum)
            # alpha 合成,照搬参考的模型。band 在这里当抗锯齿覆盖率用,
            # 不参与亮度 —— 亮度只由 vis 决定,这样线宽与亮度才互相独立。
            v = np.clip(vis, 0.0, 4.0).astype(np.float32)
            vv = np.minimum(1.0, v * 1.45)
            al = np.clip(ALPHA_BASE + ALPHA_GAIN * v, 0.0, 255.0) / 255.0 * band
            flat = img.reshape(-1, 3)
            for c in range(3):
                warm = WARM_LO[c] + WARM_HI[c] * vv
                flat[pix, c] = flat[pix, c] * (1.0 - al) + warm * al
        # 字幕:淡入淡出,不「跳」出来
        for s0, s1, txt in subs:
            if s0 - SUB_FADE <= t <= s1 + SUB_FADE:
                if t < s0:
                    al2 = (t - (s0 - SUB_FADE)) / SUB_FADE
                elif t > s1:
                    al2 = 1.0 - (t - s1) / SUB_FADE
                else:
                    al2 = 1.0
                img = draw_subtitle(img, txt, max(0.0, min(1.0, al2)), font)
                break
        return np.clip(img, 0, 255).astype(np.uint8)

    if a.still is not None:
        from PIL import Image
        f = int((a.still - a.start) * FPS)
        png = out.with_name(out.stem + f"_still{a.still:g}.png")
        Image.fromarray(draw(max(0, f))).save(png)
        print(f"\n✅ 单帧 {png}")
        return 0

    # ⚠ 2026-08-06:此处原先把整段裸帧先写成一个 v.raw 再交给 ffmpeg。40s 的
    # 样片只占 7GB 所以从没露馅,但 rgb24 1920×1080 一帧就是 6.22MB —— 一期
    # 21 分钟的成品是 **236GB**,60 分钟是 673GB。样片能跑不等于长片能跑,而这
    # 个脚本的名字就叫 long。改为每块自带一个 ffmpeg:帧直接灌进它的 stdin,
    # 各自编出一个段成品,最后 `-c copy` 拼接再统一 mux 音频(与 RBR
    # render_white_parallel 同一套办法)。峰值磁盘 = 成品大小,峰值内存 = 每块一帧。
    def render_chunk(args):
        """渲一块并就地编码成段成品。返回段文件路径。"""
        lo, hi, path = args
        # -g 固定关键帧间隔:段边界必须落在 IDR 上,否则 concat -c copy 接不上。
        # 段自身不带音频,音频在最后一次 mux 里一次性对上,免得每段各自 -ss 漂移。
        enc = subprocess.Popen(
            ["ffmpeg", "-y", "-v", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
             "-r", str(FPS), "-i", "pipe:0",
             "-c:v", "libx264", "-preset", "medium", "-crf", "19",
             "-g", str(FPS), "-keyint_min", str(FPS), "-sc_threshold", "0",
             "-pix_fmt", "yuv420p", path],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE)
        try:
            for f in range(lo, hi):
                enc.stdin.write(draw(f).tobytes())
        finally:
            enc.stdin.close()
        err = enc.stderr.read().decode(errors="replace")
        if enc.wait() != 0:
            raise RuntimeError(f"段 {path} 编码失败:{err[-400:]}")
        return path

    with tempfile.TemporaryDirectory() as td:
        # 帧与帧之间没有依赖(相位只由 t 决定),所以可以按块并行。
        # 用线程而不是进程:draw() 闭包捕获了 plate/masks/subs 这些大对象,
        # 送进子进程要先 pickle,代价比省下的 GIL 还高。真正吃时间的是 numpy
        # 逐元素运算与 x264 编码 —— 前者在 C 层放开 GIL,后者本就在独立进程里。
        nproc = max(1, min(a.jobs or (os.cpu_count() or 4) - 2, 12))
        nchunk = nproc if (nproc > 1 and frames >= nproc * 8) else 1
        step = -(-frames // nchunk)
        jobs = [(i, min(i + step, frames), str(Path(td) / f"c{k:03d}.mp4"))
                for k, i in enumerate(range(0, frames, step))]
        print(f"    {len(jobs)} 段 × {nproc} 线程 · 每段 ~{step/FPS:.0f}s")
        if len(jobs) == 1:
            parts = [render_chunk(jobs[0])]
        else:
            with cf.ThreadPoolExecutor(max_workers=nproc) as ex:
                parts = list(ex.map(render_chunk, jobs))   # map 保序,拼接才对得上

        concat = Path(td) / "concat.txt"
        concat.write_text("".join(f"file '{p}'\n" for p in parts))
        cmd = ["ffmpeg", "-y", "-v", "error",
               "-f", "concat", "-safe", "0", "-i", str(concat),
               "-ss", f"{a.start:.3f}", "-t", f"{a.seconds:.3f}", "-i", str(mix),
               "-map", "0:v", "-map", "1:a", "-c:v", "copy",
               "-c:a", "aac", "-b:a", "192k",
               "-shortest", "-movflags", "+faststart", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr[-600:])
            return 1

    # 时长自检:段丢了一块、或某段提前收尾,只看 rc 是看不出来的。
    got = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(out)],
        capture_output=True, text=True).stdout.strip() or 0)
    want = frames / FPS
    print(f"\n✅ {out} · 时长 {got:.1f}s(期望 {want:.1f}s)")
    if abs(got - want) > 1.0:
        print(f"⚠️ 时长偏差 {got - want:+.1f}s —— 段可能有缺失,勿直接发布")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
