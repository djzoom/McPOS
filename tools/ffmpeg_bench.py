#!/usr/bin/env python3
# coding: utf-8
"""
FFmpeg 4K 静帧+MP3 合成视频横评基准

仅使用标准库；跨平台（macOS/Windows/Linux）。

产出：
 - output/bench/*.log（每种方法的命令与 stdout/stderr）
 - output/bench/*.mp4|*.mov（产出视频）
 - output/bench/summary.json / summary.csv / summary.md（结构化与横评表）

方法：
 - x264（libx264 软件编码，通用最稳）
 - vtb（h264_videotoolbox，macOS 硬编；条件可用时）
 - nvenc（h264_nvenc，NVIDIA 硬编；条件可用时）
 - mjpeg（MJPEG+音频 copy，极快但体积大；容器更稳为 .mov）
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import shutil
import statistics
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass
class ProbeInfo:
    width: Optional[int]
    height: Optional[int]
    vcodec: Optional[str]
    acodec: Optional[str]
    fps: Optional[str]
    container: Optional[str]


@dataclass
class RunResult:
    method: str
    encoder: str
    cmd: List[str]
    out_path: Path
    status: str  # success|failed|skipped
    elapsed_sec: Optional[float]
    filesize_mb: Optional[float]
    probe: Optional[ProbeInfo]
    error_summary: Optional[str]
    skipped_reason: Optional[str]


def ensure_tool(name: str) -> bool:
    return shutil.which(name) is not None


def check_env_or_fail() -> None:
    if not ensure_tool("ffmpeg"):
        raise SystemExit("未找到 ffmpeg，请先安装（macOS: brew install ffmpeg；Ubuntu: sudo apt install ffmpeg；Windows: choco install ffmpeg）")
    if not ensure_tool("ffprobe"):
        raise SystemExit("未找到 ffprobe，请先安装（同 ffmpeg 套件）")


def list_encoders() -> str:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
    return proc.stdout + proc.stderr


def has_encoder(encoders_text: str, key: str) -> bool:
    return key in encoders_text


def build_common_inputs(image: Path, audio: Path, scale_wh: str, fps: int, duration_fix: str = "none", audio_duration: Optional[float] = None) -> List[str]:
    # 解析例如 "3840x2160" 为 3840:2160（scale/pad 需用冒号分隔）
    try:
        sw, sh = scale_wh.lower().split("x", 1)
        sw = str(int(sw))
        sh = str(int(sh))
    except Exception:
        sw, sh = "3840", "2160"
    
    # duration_fix 模式：
    # - "none": 原逻辑（-shortest，可能有时长偏差）
    # - "30fps": 方案A - 用30fps固定帧率，避免输出端-r（更准确的时间戳，但文件大）
    # - "explicit": 方案B - 用-t显式裁剪到音频时长（最强一致性）
    # - "1fps-precise": 方案C - 保持1fps但用精确时间戳控制（round=down + timescale优化）
    
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
    ]
    
    # 方案B：显式时长裁剪
    if duration_fix == "explicit" and audio_duration is not None:
        cmd.extend(["-loop", "1", "-t", str(audio_duration), "-i", str(image)])
    else:
        cmd.extend(["-loop", "1", "-i", str(image)])
    
    cmd.append("-i")
    cmd.append(str(audio))
    
    # 帧率控制策略
    if duration_fix == "30fps":
        # 方案A：用30fps固定帧率（更细时间颗粒度，减少四舍五入误差）
        filter_fps = 30
        if fps == 1:
            # 使用 round=down 确保向下取整
            vf = f"scale={sw}:{sh}:force_original_aspect_ratio=decrease,pad={sw}:{sh}:(ow-iw)/2:(oh-ih)/2,fps=30:round=down"
        else:
            vf = f"scale={sw}:{sh}:force_original_aspect_ratio=decrease,pad={sw}:{sh}:(ow-iw)/2:(oh-ih)/2,fps={filter_fps}"
    elif duration_fix == "1fps-precise":
        # 方案C：保持1fps但用向下取整 + 精确时间基
        vf = f"scale={sw}:{sh}:force_original_aspect_ratio=decrease,pad={sw}:{sh}:(ow-iw)/2:(oh-ih)/2,fps=1:round=down"
    else:
        # 原逻辑或explicit：使用原始fps
        filter_fps = fps
        vf = f"scale={sw}:{sh}:force_original_aspect_ratio=decrease,pad={sw}:{sh}:(ow-iw)/2:(oh-ih)/2,fps={filter_fps}"
    
    cmd.extend(["-vf", vf])
    cmd.extend(["-pix_fmt", "yuv420p"])
    
    # 方案C：添加精确时间基控制
    if duration_fix == "1fps-precise":
        # 使用高精度时间基和VFR模式
        cmd.extend(["-vsync", "vfr", "-fps_mode", "passthrough"])
    
    # 方案B已经有-t限制，方案A和原逻辑都用-shortest
    if duration_fix != "explicit":
        cmd.append("-shortest")
    
    cmd.append("-movflags")
    cmd.append("+faststart")
    
    return cmd


def build_x264(image: Path, audio: Path, scale_wh: str, fps: int, container: str, outdir: Path, run_idx: int, duration_fix: str = "none", audio_duration: Optional[float] = None) -> Tuple[List[str], Path, str]:
    out_path = outdir / f"x264_r{run_idx}.{container}"
    cmd = [
        *build_common_inputs(image, audio, scale_wh, fps, duration_fix, audio_duration),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
    ]
    # 方案A和C：不在输出端设-r，让filter主导（避免时间戳冲突）
    if duration_fix not in ["30fps", "1fps-precise"]:
        cmd.extend(["-r", str(fps)])
    cmd.extend([
        "-c:a", "aac", "-b:a", "192k",
        str(out_path),
    ])
    return cmd, out_path, "libx264"


def build_vtb(image: Path, audio: Path, scale_wh: str, fps: int, container: str, outdir: Path, run_idx: int, duration_fix: str = "none", audio_duration: Optional[float] = None) -> Tuple[List[str], Path, str]:
    out_path = outdir / f"vtb_r{run_idx}.{container}"
    cmd = [
        *build_common_inputs(image, audio, scale_wh, fps, duration_fix, audio_duration),
        "-c:v", "h264_videotoolbox",
    ]
    # 码率设置：30fps需要更高，1fps-precise保持原码率
    if duration_fix == "30fps":
        cmd.extend(["-b:v", "10M", "-maxrate", "12M", "-bufsize", "18M"])
    else:
        cmd.extend(["-b:v", "6M", "-maxrate", "8M", "-bufsize", "12M"])
    
    # 方案A和C：不在输出端设-r
    if duration_fix not in ["30fps", "1fps-precise"]:
        cmd.extend(["-r", str(fps)])
    cmd.extend([
        "-c:a", "aac", "-b:a", "192k",
        str(out_path),
    ])
    return cmd, out_path, "h264_videotoolbox"


def build_nvenc(image: Path, audio: Path, scale_wh: str, fps: int, container: str, outdir: Path, run_idx: int, duration_fix: str = "none", audio_duration: Optional[float] = None) -> Tuple[List[str], Path, str]:
    out_path = outdir / f"nvenc_r{run_idx}.{container}"
    cmd = [
        *build_common_inputs(image, audio, scale_wh, fps, duration_fix, audio_duration),
        "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "23",
    ]
    # 方案A和C：不在输出端设-r
    if duration_fix not in ["30fps", "1fps-precise"]:
        cmd.extend(["-r", str(fps)])
    cmd.extend([
        "-c:a", "aac", "-b:a", "192k",
        str(out_path),
    ])
    return cmd, out_path, "h264_nvenc"


def build_mjpeg(image: Path, audio: Path, scale_wh: str, fps: int, container: str, outdir: Path, run_idx: int, duration_fix: str = "none", audio_duration: Optional[float] = None) -> Tuple[List[str], Path, str]:
    # 容器更稳建议 mov
    ext = "mov" if container == "mp4" else container
    out_path = outdir / f"mjpeg_r{run_idx}.{ext}"
    cmd = [
        *build_common_inputs(image, audio, scale_wh, fps, duration_fix, audio_duration),
        "-c:v", "mjpeg", "-q:v", "3",
    ]
    # 方案A和C：不在输出端设-r
    if duration_fix not in ["30fps", "1fps-precise"]:
        cmd.extend(["-r", str(fps)])
    cmd.extend([
        "-c:a", "copy",
        str(out_path),
    ])
    return cmd, out_path, "mjpeg"


def ffprobe_gather(path: Path) -> ProbeInfo:
    # container
    fmt = subprocess.run([
        "ffprobe", "-v", "error", "-print_format", "json", "-show_format", str(path)
    ], capture_output=True, text=True)
    fmt_json = {}
    try:
        fmt_json = json.loads(fmt.stdout or "{}")
    except Exception:
        fmt_json = {}
    container = None
    if isinstance(fmt_json, dict):
        tags = fmt_json.get("format") or {}
        container = (tags.get("format_name") or "").split(",")[0] or None

    # streams
    st = subprocess.run([
        "ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(path)
    ], capture_output=True, text=True)
    st_json = {}
    try:
        st_json = json.loads(st.stdout or "{}")
    except Exception:
        st_json = {}
    width = height = None
    vcodec = acodec = fps = None
    for s in st_json.get("streams", []):
        if s.get("codec_type") == "video":
            vcodec = s.get("codec_name")
            width = s.get("width")
            height = s.get("height")
            fps = s.get("r_frame_rate")
        elif s.get("codec_type") == "audio":
            acodec = s.get("codec_name")
    return ProbeInfo(width=width, height=height, vcodec=vcodec, acodec=acodec, fps=fps, container=container)


def _ffprobe_duration_seconds(path: Path) -> Optional[float]:
    try:
        p = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path)
        ], capture_output=True, text=True, timeout=10)
        txt = (p.stdout or "").strip()
        return float(txt) if txt else None
    except Exception:
        return None


def _render_progress(percent: float, width: int = 28) -> str:
    p = max(0, min(100, int(percent)))
    done = int(width * p / 100)
    return f"[{'#'*done}{'-'*(width-done)}] {p:3d}%"


def run_once(method: str, encoder_label: str, cmd: List[str], out_path: Path, log_path: Path, timeout: int, try_aac_fallback: bool = False, audio_path: Optional[Path] = None) -> RunResult:
    start = time.perf_counter()
    # 为进度插入 -progress pipe:1
    cmd_with_progress = cmd[:]
    try:
        cmd_with_progress.insert(1, "-progress")
        cmd_with_progress.insert(2, "pipe:1")
    except Exception:
        pass

    # 估算总时长（用于显示百分比）
    total_sec = _ffprobe_duration_seconds(audio_path) if audio_path else None

    try:
        proc = subprocess.Popen(cmd_with_progress, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        # 回退不用进度
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    stdout_buf: List[str] = []
    stderr_buf: List[str] = []
    last_percent = -1
    try:
        assert proc.stdout is not None
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            stdout_buf.append(line)
            if line.startswith("out_time_ms=") and total_sec:
                try:
                    ms = int(line.split("=",1)[1].strip())
                    percent = min(99.0, (ms/1000000.0)/total_sec*100.0)
                    if int(percent) != last_percent:
                        last_percent = int(percent)
                        print(_render_progress(percent), end="\r", flush=True)
                except Exception:
                    pass
        # 读尽 stderr
        assert proc.stderr is not None
        stderr_buf.append(proc.stderr.read() or "")
    except Exception:
        pass
    code = proc.wait(timeout=timeout)
    elapsed = time.perf_counter() - start
    if code == 0 and last_percent >= 0:
        print(_render_progress(100.0))

    log_path.write_text(
        "CMD:\n" + " ".join(cmd) + "\n\nSTDOUT:\n" + ("".join(stdout_buf)) + "\n\nSTDERR:\n" + ("".join(stderr_buf)),
        encoding="utf-8",
    )
    if code != 0:
        # 对 MJPEG + copy 失败，回退到 aac
        if try_aac_fallback:
            fallback_cmd = cmd[:]
            # 将 -c:a copy 改为 aac -b:a 192k
            if "-c:a" in fallback_cmd:
                idx = fallback_cmd.index("-c:a")
                fallback_cmd[idx:idx+2] = ["-c:a", "aac"]
                # 如果后面紧跟 "copy"，替换它
                if idx + 1 < len(fallback_cmd) and fallback_cmd[idx+1] == "copy":
                    fallback_cmd[idx+1] = "aac"
            else:
                fallback_cmd += ["-c:a", "aac"]
            # 设置码率
            if "-b:a" in fallback_cmd:
                bidx = fallback_cmd.index("-b:a")
                if bidx + 1 < len(fallback_cmd):
                    fallback_cmd[bidx+1] = "192k"
            else:
                fallback_cmd += ["-b:a", "192k"]
            start2 = time.perf_counter()
            proc2 = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=timeout)
            elapsed2 = time.perf_counter() - start2
            log_path.write_text(log_path.read_text(encoding="utf-8") + "\n\n[Fallback aac CMD]\n" + " ".join(fallback_cmd) + "\n\nSTDOUT:\n" + (proc2.stdout or "") + "\n\nSTDERR:\n" + (proc2.stderr or ""), encoding="utf-8")
            if proc2.returncode == 0 and out_path.exists():
                size = out_path.stat().st_size / (1024 * 1024)
                return RunResult(method, encoder_label, fallback_cmd, out_path, "success", elapsed2, size, ffprobe_gather(out_path), None, None)
            err2 = (proc2.stderr or "").splitlines()[:10]
            return RunResult(method, encoder_label, fallback_cmd, out_path, "failed", elapsed2, None, None, "\n".join(err2), None)
        err = ("".join(stderr_buf) or "").splitlines()[:10]
        return RunResult(method, encoder_label, cmd, out_path, "failed", elapsed, None, None, "\n".join(err), None)
    if not out_path.exists():
        return RunResult(method, encoder_label, cmd, out_path, "failed", elapsed, None, None, "无产物", None)
    size = out_path.stat().st_size / (1024 * 1024)
    return RunResult(method, encoder_label, cmd, out_path, "success", elapsed, size, ffprobe_gather(out_path), None, None)


def median(values: Sequence[float]) -> float:
    return statistics.median(values) if values else math.nan


def _generate_diagnostics(outdir: Path, results: List[RunResult]) -> None:
    """生成诊断报告：分析每个视频文件的时长、时间戳、帧数等信息"""
    report_file = outdir / "duration_diagnostics.txt"
    
    with report_file.open("w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("时长诊断报告\n")
        f.write("=" * 80 + "\n\n")
        
        for r in results:
            if r.status != "success" or not r.out_path.exists():
                continue
            
            f.write(f"\n{'=' * 80}\n")
            f.write(f"文件: {r.out_path.name}\n")
            f.write(f"编码器: {r.encoder}\n")
            f.write(f"{'=' * 80}\n\n")
            
            # 视频流信息
            f.write("【视频流】\n")
            try:
                v_probe = subprocess.run([
                    "ffprobe", "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=time_base,avg_frame_rate,r_frame_rate,nb_frames,start_time,duration,duration_ts",
                    "-of", "default=nw=1:nk=1",
                    str(r.out_path)
                ], capture_output=True, text=True, timeout=10)
                f.write(v_probe.stdout)
                f.write("\n")
            except Exception as e:
                f.write(f"错误: {e}\n\n")
            
            # 音频流信息
            f.write("【音频流】\n")
            try:
                a_probe = subprocess.run([
                    "ffprobe", "-v", "error",
                    "-select_streams", "a:0",
                    "-show_entries", "stream=time_base,start_time,duration,duration_ts",
                    "-of", "default=nw=1:nk=1",
                    str(r.out_path)
                ], capture_output=True, text=True, timeout=10)
                f.write(a_probe.stdout)
                f.write("\n")
            except Exception as e:
                f.write(f"错误: {e}\n\n")
            
            # 容器总时长
            f.write("【容器总时长】\n")
            try:
                format_probe = subprocess.run([
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=nw=1:nk=1",
                    str(r.out_path)
                ], capture_output=True, text=True, timeout=10)
                duration_str = format_probe.stdout.strip()
                if duration_str:
                    duration_val = float(duration_str)
                    f.write(f"duration = {duration_val:.6f} 秒\n")
                    f.write(f"duration = {duration_val/60:.2f} 分钟\n")
                    f.write(f"duration = {int(duration_val//3600)}:{(duration_val%3600)//60:02d}:{duration_val%60:05.2f}\n")
                f.write("\n")
            except Exception as e:
                f.write(f"错误: {e}\n\n")
    
    print(f"✅ 诊断报告已保存: {report_file}")


def write_summary(outdir: Path, results: List[RunResult], runs: int) -> None:
    # 结构化
    rows: List[Dict[str, object]] = []
    for r in results:
        probe = r.probe or ProbeInfo(None, None, None, None, None, None)
        rows.append({
            "method": r.method,
            "encoder": r.encoder,
            "cmd": " ".join(r.cmd),
            "runs": runs,
            "elapsed_sec": round(r.elapsed_sec or 0.0, 3) if r.elapsed_sec is not None else None,
            "filesize_mb": round(r.filesize_mb or 0.0, 3) if r.filesize_mb is not None else None,
            "fps": probe.fps,
            "width": probe.width,
            "height": probe.height,
            "vcodec": probe.vcodec,
            "acodec": probe.acodec,
            "container": probe.container,
            "status": r.status,
            "skipped_reason": r.skipped_reason,
            "error_summary": r.error_summary,
            "output": str(r.out_path),
        })
    (outdir / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    # CSV（按 method 聚合统计 avg/p50）
    agg: Dict[str, Dict[str, List[RunResult]]] = {}
    for r in results:
        agg.setdefault(r.method, {}).setdefault(r.status, []).append(r)
    with (outdir / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["method", "encoder", "avg_sec", "p50_sec", "filesize_mb", "vcodec", "acodec", "container", "status", "skipped_reason"])
        for method in ["x264", "vtb", "nvenc", "mjpeg"]:
            group = [r for r in results if r.method == method and r.status == "success"]
            if group:
                secs = [r.elapsed_sec for r in group if r.elapsed_sec is not None]
                sizes = [r.filesize_mb for r in group if r.filesize_mb is not None]
                avg_sec = round(sum(secs) / len(secs), 3) if secs else None
                p50_sec = round(median([s for s in secs if s is not None]), 3) if secs else None
                size = round(sum(sizes) / len(sizes), 3) if sizes else None
                g0 = group[0]
                w.writerow([method, g0.encoder, avg_sec, p50_sec, size, g0.probe.vcodec if g0.probe else None, g0.probe.acodec if g0.probe else None, g0.probe.container if g0.probe else None, "success", ""])
            else:
                # 失败或跳过概述
                anyr = next((r for r in results if r.method == method), None)
                if anyr:
                    w.writerow([method, anyr.encoder, None, None, None, None, None, None, anyr.status, anyr.skipped_reason or anyr.error_summary or ""])

    # Markdown 表
    table_rows: List[Tuple[str, float, str]] = []  # method, avg_sec, md_line
    for method in ["x264", "vtb", "nvenc", "mjpeg"]:
        group = [r for r in results if r.method == method and r.status == "success"]
        if group:
            secs = [r.elapsed_sec for r in group if r.elapsed_sec is not None]
            avg_sec = sum(secs) / len(secs) if secs else float("inf")
            g0 = group[0]
            size_mb = round(sum([(r.filesize_mb or 0) for r in group]) / len(group), 3)
            md = f"| {method} | {g0.encoder} | {avg_sec:.3f} | {median([s for s in secs if s is not None]):.3f} | {size_mb:.3f} | {g0.probe.vcodec if g0.probe else ''} | {g0.probe.acodec if g0.probe else ''} | {g0.probe.container if g0.probe else ''} | success |"
            table_rows.append((method, avg_sec, md))
        else:
            anyr = next((r for r in results if r.method == method), None)
            note = anyr.skipped_reason or anyr.error_summary or anyr.status if anyr else "no data"
            md = f"| {method} | {anyr.encoder if anyr else ''} | - | - | - | - | - | - | {note} |"
            table_rows.append((method, float("inf"), md))
    table_rows.sort(key=lambda x: x[1])
    md_lines = [
        "| Method | Encoder | Avg(s) | p50(s) | Size(MB) | vcodec | acodec | Container | Notes |",
        "|---|---|---:|---:|---:|---|---|---|---|",
    ] + [r[2] for r in table_rows]
    (outdir / "summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    # 控制台推荐
    baseline = next((r for r in results if r.method == "x264" and r.status == "success"), None)
    fastest = None
    best_avg = float("inf")
    for method in ["x264", "vtb", "nvenc", "mjpeg"]:
        group = [r for r in results if r.method == method and r.status == "success"]
        if group:
            avg = sum([r.elapsed_sec or 0 for r in group]) / len(group)
            if avg < best_avg:
                best_avg = avg
                fastest = (method, avg, group)
    print("横评推荐：")
    if fastest:
        print(f"1) 最快方案：{fastest[0]}（avg={fastest[1]:.3f}s）")
        if baseline and fastest[0] != "x264":
            fsize = sum([(r.filesize_mb or 0) for r in fastest[2]]) / len(fastest[2])
            bsize = baseline.filesize_mb or fsize
            if bsize > 0 and fsize / bsize > 2.0:
                print("2) 提示：最快方案体积大于基线 x264 的 2 倍，谨慎选择。")
    else:
        print("无成功方案，请检查日志。")
    # 跳过原因
    for m in ["vtb", "nvenc"]:
        anyr = next((r for r in results if r.method == m), None)
        if anyr and anyr.status == "skipped":
            print(f"跳过 {m}：{anyr.skipped_reason}")


def run_method(
    label: str,
    builder,
    enabled: bool,
    image: Path,
    audio: Path,
    scale_wh: str,
    fps: int,
    container: str,
    outdir: Path,
    runs: int,
    timeout: int,
    duration_fix: str = "none",
    audio_duration: Optional[float] = None,
) -> List[RunResult]:
    results: List[RunResult] = []
    if not enabled:
        # 记录跳过
        out_path = outdir / f"{label}_r1.{container}"
        results.append(RunResult(label, label, [], out_path, "skipped", None, None, None, None, "encoder not available or platform unsupported"))
        return results
    for i in range(1, runs + 1):
        cmd, out_path, encoder_label = builder(image, audio, scale_wh, fps, container, outdir, i, duration_fix, audio_duration)
        log_path = outdir / f"{label}_r{i}.log"
        try:
            try_aac_fallback = (label == "mjpeg")
            r = run_once(label, encoder_label, cmd, out_path, log_path, timeout, try_aac_fallback=try_aac_fallback, audio_path=audio)
        except subprocess.TimeoutExpired:
            r = RunResult(label, encoder_label, cmd, out_path, "failed", None, None, None, "timeout", None)
        results.append(r)
    return results


def main() -> None:
    p = argparse.ArgumentParser(description="FFmpeg 4K 静帧+MP3 合成视频横评")
    p.add_argument("--image", type=Path, required=True, help="封面图（任意尺寸，将适配到目标分辨率）")
    p.add_argument("--audio", type=Path, required=True, help="MP3 音频")
    p.add_argument("--outdir", type=Path, default=Path("output/bench"))
    p.add_argument("--fps", type=int, default=1)
    p.add_argument("--container", choices=["mp4", "mov"], default="mp4")
    p.add_argument("--scale", default="3840x2160", help="目标分辨率，例 3840x2160")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--keep-failed", action="store_true")
    p.add_argument("--duration-fix", choices=["none", "30fps", "explicit", "1fps-precise"], default="none",
                   help="时长修复方案: none=原逻辑, 30fps=方案A(30fps固定帧率), explicit=方案B(显式裁剪), 1fps-precise=方案C(1fps精确时间戳)")
    p.add_argument("--gen-diagnostics", action="store_true",
                   help="生成诊断报告（ffprobe时长分析）")
    args = p.parse_args()

    check_env_or_fail()
    outdir: Path = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    if not args.image.exists() or not args.audio.exists():
        raise SystemExit(f"找不到输入：image={args.image} audio={args.audio}。请准备封面与 mp3 后重试。")

    # 方案B需要音频时长
    audio_duration = None
    if args.duration_fix == "explicit":
        audio_duration = _ffprobe_duration_seconds(args.audio)
        if audio_duration is None:
            raise SystemExit(f"无法获取音频时长，方案B需要此信息")
        print(f"[时长修复] 方案B：音频时长 = {audio_duration:.3f}秒 ({audio_duration/60:.1f}分钟)")

    encs = list_encoders()
    is_macos = platform.system().lower() == "darwin"
    enabled_map = {
        "x264": True,
        "vtb": (is_macos and has_encoder(encs, "h264_videotoolbox")),
        "nvenc": has_encoder(encs, "h264_nvenc"),
        "mjpeg": True,
    }
    builders = {
        "x264": build_x264,
        "vtb": build_vtb,
        "nvenc": build_nvenc,
        "mjpeg": build_mjpeg,
    }

    all_results: List[RunResult] = []
    order = ["x264", "vtb", "nvenc", "mjpeg"]
    for label in order:
        res = run_method(
            label,
            builders[label],
            enabled_map[label],
            args.image,
            args.audio,
            args.scale,
            args.fps,
            args.container,
            outdir,
            args.runs,
            args.timeout,
            args.duration_fix,
            audio_duration,
        )
        all_results.extend(res)

    # 清理失败产物（除非 keep-failed）
    if not args.keep_failed:
        for r in all_results:
            if r.status != "success" and r.out_path.exists():
                try:
                    r.out_path.unlink()
                except Exception:
                    pass

    write_summary(outdir, all_results, args.runs)
    
    # 生成诊断报告
    if args.gen_diagnostics:
        print("\n🔍 生成诊断报告...")
        _generate_diagnostics(outdir, all_results)


if __name__ == "__main__":
    main()


