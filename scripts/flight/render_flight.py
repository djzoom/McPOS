#!/usr/bin/env python3
"""空中名所 · 水墨淡彩风飞行动画 → 16:9 MP4。

flight.html 是渲染引擎（Three.js），本脚本用无头 Chromium 逐帧驱动它，
把每帧 JPEG 经管道喂给 ffmpeg。时间轴由帧号推导，同一组参数永远出同一部片。

    python scripts/flight/render_flight.py --res 4k --duration 10m --out flight.mp4
    python scripts/flight/render_flight.py --res 256 --duration 30 --out tiny.mp4
    python scripts/flight/render_flight.py --res 1080p --duration 3h --unique 20m --out long.mp4

分辨率：--res 接受 4k / 2160p / 1440p / 1080p / 720p / 480p / 360p / 240p / 144p，
或一个宽度数字（256–3840），高度按 16:9 推出并取偶数。

长片：每一景都从空白纸面淡入、淡出回纸面，所以 --unique 只渲染一段不重样的
片段，再由 ffmpeg 无缝循环铺满 --duration（不重编码，几乎不花时间）。
"""
from __future__ import annotations

import argparse
import base64
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "flight.html"
SCENES = ("niigata", "tuscany", "serengeti", "bruges", "pampa", "provence", "punjab", "krumlov")
FLYERS = ("auto", "spitfire", "biplane", "crane", "stork", "geese", "gull", "albatross")
FLOCKS = ("crane", "stork", "geese", "gull", "albatross")
PRESETS = {"4k": 3840, "2160p": 3840, "1440p": 2560, "1080p": 1920, "720p": 1280,
           "480p": 854, "360p": 640, "240p": 426, "144p": 256}


def parse_duration(text: str) -> float:
    """90 / 90s / 10m / 1h30m / 01:30:00 → 秒。"""
    text = text.strip().lower()
    if ":" in text:
        secs = 0.0
        for part in text.split(":"):
            secs = secs * 60 + float(part)
        return secs
    if re.fullmatch(r"[\d.]+", text):
        return float(text)
    m = re.fullmatch(r"(?:([\d.]+)h)?(?:([\d.]+)m)?(?:([\d.]+)s)?", text)
    if not m or not any(m.groups()):
        raise argparse.ArgumentTypeError(f"看不懂的时长: {text!r}")
    h, mi, s = (float(g) if g else 0.0 for g in m.groups())
    return h * 3600 + mi * 60 + s


def parse_res(text: str) -> tuple[int, int]:
    key = text.strip().lower()
    width = PRESETS.get(key) or (int(key) if key.isdigit() else None)
    if width is None:
        raise argparse.ArgumentTypeError(f"看不懂的分辨率: {text!r}（用 4k/1080p/... 或 256–3840 的宽度）")
    if not 256 <= width <= 3840:
        raise argparse.ArgumentTypeError(f"宽度须在 256–3840 之间，收到 {width}")
    width -= width % 2
    height = round(width * 9 / 16 / 2) * 2
    return width, height


def fmt_secs(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def render_clip(args, width: int, height: int, duration: float, out: Path) -> None:
    from playwright.sync_api import sync_playwright

    frames = max(1, round(duration * args.fps))
    ffmpeg = [args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
              "-f", "image2pipe", "-framerate", str(args.fps), "-c:v", "mjpeg", "-i", "-",
              "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
              "-pix_fmt", "yuv420p", "-r", str(args.fps), "-movflags", "+faststart", str(out)]
    html = ENGINE.read_text(encoding="utf-8")
    page_src = "<!doctype html><html><head><meta charset='utf-8'></head><body>" + html + "</body></html>"

    with sync_playwright() as pw:
        launch = {"args": ["--ignore-gpu-blocklist", "--enable-gpu-rasterization",
                           "--enable-unsafe-swiftshader"]}
        if args.chromium:
            launch["executable_path"] = args.chromium
        browser = pw.chromium.launch(**launch)
        page = browser.new_page(viewport={"width": 800, "height": 450}, device_scale_factor=1)
        page.add_init_script("window.FLIGHT_RENDER = true;")
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        if args.three:
            three = Path(args.three).read_bytes()
            page.route("**/three.min.js", lambda r: r.fulfill(body=three, content_type="application/javascript"))
        page.set_content(page_src, wait_until="load", timeout=120_000)
        if not page.evaluate("typeof window.FLIGHT === 'object'"):
            raise SystemExit("引擎没起来（three.js 加载失败？可用 --three 指定本地 three.min.js）\n" + "\n".join(errors))
        info = page.evaluate("o => FLIGHT.init(o)", {
            "width": width, "height": height, "duration": duration, "fps": args.fps,
            "segment": args.segment, "seed": args.seed, "labels": args.labels, "scenes": args.scenes,
            "flyer": args.flyer})
        print(f"  引擎: {info['gl']} · {info['scenes']} 景 × {info['segment']:.1f}s · {width}×{height} · {frames} 帧", flush=True)

        proc = subprocess.Popen(ffmpeg, stdin=subprocess.PIPE)
        t0 = time.time()
        try:
            for i in range(frames):
                url = page.evaluate("([i, q]) => FLIGHT.frameJPEG(i, q)", [i, args.jpeg_quality])
                proc.stdin.write(base64.b64decode(url.split(",", 1)[1]))
                if i % max(1, args.fps * 5) == 0 or i == frames - 1:
                    done = i + 1
                    rate = done / max(1e-6, time.time() - t0)
                    eta = (frames - done) / max(1e-6, rate)
                    print(f"\r  {done}/{frames} 帧 · {rate:.1f} fps · 剩余 {fmt_secs(eta)}   ", end="", flush=True)
        finally:
            proc.stdin.close()
            code = proc.wait()
            browser.close()
        print()
        if errors:
            print("  页面报错:\n    " + "\n    ".join(errors[:10]), file=sys.stderr)
        if code != 0:
            raise SystemExit(f"ffmpeg 退出码 {code}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path, help="输出 .mp4")
    ap.add_argument("--duration", required=True, type=parse_duration, help="总时长：90 / 10m / 1h30m / 01:30:00")
    ap.add_argument("--res", default="1080p", type=parse_res, help="4k/1440p/1080p/720p/... 或宽度 256–3840（默认 1080p）")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--segment", type=float, default=45, help="每一景大约多少秒（会微调到整除总时长，默认 45）")
    ap.add_argument("--scenes", default=",".join(SCENES), help=f"景序，逗号分隔，可选 {', '.join(SCENES)}")
    ap.add_argument("--seed", type=int, default=1, help="换种子＝换一套地形、牛群与云")
    ap.add_argument("--flyer", default="auto",
                    help="飞行物，逗号分隔则逐景轮换；鸟可带数量，如 geese:21,gull:7。"
                         "auto 按景配（新潟丹顶鹤×3、潘帕斯信天翁×2、旁遮普雁×13、布鲁日海鸥×6……）。可选："
                         + " / ".join(FLYERS[1:]))
    ap.add_argument("--labels", choices=("zh", "en", "none"), default="zh", help="题签：中文竖排 / 英文 / 不要")
    ap.add_argument("--unique", type=parse_duration, default=None,
                    help="只渲染这么长的不重样片段，再无缝循环铺满总时长（长片用）")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--jpeg-quality", type=float, default=0.94, help="帧传输的 JPEG 质量（0–1）")
    ap.add_argument("--three", help="本地 three.min.js（r128），离线时用")
    ap.add_argument("--chromium", help="指定 Chromium 可执行文件")
    ap.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    args = ap.parse_args()

    args.scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    bad = [s for s in args.scenes if s not in SCENES]
    if bad:
        ap.error(f"未知景名: {', '.join(bad)}")
    args.flyer = [s.strip() for s in args.flyer.split(",") if s.strip()]
    for spec in args.flyer:
        kind, _, n = spec.partition(":")
        if kind not in FLYERS:
            ap.error(f"未知飞行物: {kind}（可选 {', '.join(FLYERS)}）")
        if n and (kind not in FLOCKS or not n.isdigit() or not 1 <= int(n) <= 31):
            ap.error(f"数量只能给鸟用，且在 1–31 之间: {spec}")
    width, height = args.res
    args.out = args.out.expanduser()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    total = args.duration
    if args.unique and args.unique < total:
        loops = math.ceil(total / args.unique)
        clip_len = total / loops
        print(f"渲染 {fmt_secs(clip_len)} 不重样片段，循环 {loops} 次铺满 {fmt_secs(total)}")
        with tempfile.TemporaryDirectory() as tmp:
            clip = Path(tmp) / "clip.mp4"
            render_clip(args, width, height, clip_len, clip)
            subprocess.run([args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                            "-stream_loop", str(loops - 1), "-i", str(clip), "-t", f"{total:.3f}",
                            "-c", "copy", "-movflags", "+faststart", str(args.out)], check=True)
    else:
        print(f"渲染 {fmt_secs(total)}")
        render_clip(args, width, height, total, args.out)
    print(f"完成 → {args.out}")


if __name__ == "__main__":
    main()
