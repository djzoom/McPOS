#!/usr/bin/env python3
# coding: utf-8
"""
依据结构化歌单 CSV 生成 Side A/B 混音，插入 Needle Start / Vinyl Noise，
并通过交叉淡入淡出串接，满足 ffmpeg remix 的需求。

用法示例：
    python scripts/local_picker/remix_mixtape.py \
        --playlist output/playlists/20251029_0526_mixtape_playlist.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

# Ensure project root is importable when running as a standalone script.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.configuration import AppConfig, ConfigError  # type: ignore

# 延迟导入：仅在 engine=pydub 时导入，避免 Python 3.14 缺少 audioop 导致整脚本崩溃
try:
    from pydub import AudioSegment  # type: ignore
except Exception:
    AudioSegment = None  # type: ignore
    # mypy: ignore[assignment]

CONFIG_PATH = AppConfig.DEFAULT_PATH
OUTPUT_DIR = Path("output")  # 运行时由配置覆盖
SFX_DIR = Path("assets/sfx")

TRACK_SAMPLE_RATE = 44_100
TRACK_CHANNELS = 2
TRACK_CROSSFADE_MS = 2000
SFX_CROSSFADE_MS = 800
SFX_GAIN_DB = -18.0  # 约12.6% 音量


class MissingAssetError(RuntimeError):
    """缺少必要素材时抛出。"""


def parse_playlist(csv_path: Path) -> Dict[str, List[Dict[str, str]]]:
    with csv_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("歌单 CSV 缺少表头")
        timeline: Dict[str, List[Dict[str, str]]] = {"A": [], "B": []}
        for row in reader:
            if (row.get("Section") or "").strip() != "Timeline":
                continue
            if (row.get("Timeline") or "").strip() != "Needle":
                continue
            side = (row.get("Side") or "").strip().upper()
            if side not in timeline:
                continue
            timeline[side].append(
                {
                    "timestamp": (row.get("Timestamp") or "").strip(),
                    "description": (row.get("Description") or "").strip(),
                }
            )
    return timeline


def normalize_name(name: str) -> str:
    return (
        name.lower()
        .replace("’", "")
        .replace("'", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
    )


def resolve_track_path(title: str, library_root: Path, extensions: Sequence[str]) -> Path:
    for ext in extensions:
        exact = library_root / f"{title}{ext}"
        if exact.exists():
            return exact

    normalized_target = normalize_name(title)
    for ext in extensions:
        for path in library_root.glob(f"*{ext}"):
            if normalize_name(path.stem) == normalized_target:
                return path

    raise MissingAssetError(f"未找到歌曲文件：{title}")


def prepare_segment(
    description: str,
    library_root: Path,
    extensions: Sequence[str],
    needle_start: Path,
    vinyl_noise: Path,
) -> Tuple[AudioSegment, str, Path]:
    """将描述转换为音频片段并返回 (segment, kind, path)。"""
    if description == "Needle On Vinyl Record":
        kind = "sfx"
        path = needle_start
    elif description == "Needle Noise":
        kind = "sfx"
        path = vinyl_noise
    elif description:
        kind = "track"
        path = resolve_track_path(description, library_root, extensions)
    else:
        raise ValueError("空的描述无法转换音频片段")

    segment = AudioSegment.from_file(path)
    segment = segment.set_frame_rate(TRACK_SAMPLE_RATE).set_channels(TRACK_CHANNELS)

    if kind == "sfx":
        segment = segment + SFX_GAIN_DB
        # 具体淡入淡出时长在 pydub 引擎阶段可再次覆盖
        segment = segment.fade_in(80).fade_out(200)
    else:
        segment = segment.fade_in(120).fade_out(200)

    return segment, kind, path


def compute_crossfade(prev_kind: str, curr_kind: str, prev_len: int, curr_len: int) -> int:
    """根据前后片段类型选择合适的交叉淡入淡出时长（毫秒）。"""
    base = TRACK_CROSSFADE_MS
    if prev_kind == "sfx" or curr_kind == "sfx":
        base = SFX_CROSSFADE_MS
    # crossfade 不应超过片段长度的一半，避免剪切过渡
    max_allowed = min(prev_len // 2, curr_len // 2)
    return max(0, min(base, max_allowed))



# 新增：严格时间轴多轨混音
def parse_timestamp(ts: str) -> int:
    # "2:39" -> 毫秒
    if not ts or ":" not in ts:
        return 0
    parts = ts.strip().split(":")
    if len(parts) == 2:
        m, s = parts
        return (int(m) * 60 + int(s)) * 1000
    elif len(parts) == 3:
        h, m, s = parts
        return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000
    return 0

def build_mix_timeline(
    events: Sequence[Dict[str, str]],
    library_root: Path,
    extensions: Sequence[str],
    needle_start: Path,
    vinyl_noise: Path,
) -> AudioSegment:
    # 1. 解析所有事件，收集 (start_ms, segment, kind)
    timeline = []
    max_end = 0
    for event in events:
        desc = event["description"]
        ts = event["timestamp"]
        if not desc or not ts:
            continue
        start_ms = parse_timestamp(ts)
        segment, kind, _ = prepare_segment(desc, library_root, extensions, needle_start, vinyl_noise)
        # SFX音量约12.6%（-18 dB）
        if kind == "sfx":
            segment = segment - 18.0  # 约12.6%音量
        end_ms = start_ms + len(segment)
        max_end = max(max_end, end_ms)
        timeline.append((start_ms, segment, kind))
    if not timeline:
        raise ValueError("没有可用的音频片段")
    # 2. 创建全长静音轨
    base = AudioSegment.silent(duration=max_end + 1000, frame_rate=TRACK_SAMPLE_RATE)
    # 3. 叠加所有片段
    for start_ms, segment, _ in timeline:
        base = base.overlay(segment, position=start_ms)
    return base.fade_out(800)


def export_mix(mix: AudioSegment, target: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # 使用CBR 320k，标准ID3v2.3，避免降采样，最大兼容性
    mix.export(
        target,
        format="mp3",
        bitrate="320k",
        parameters=[
            "-write_id3v1", "1",  # 写入ID3v1标签
            "-id3v2_version", "3",  # 强制ID3v2.3
            "-codec:a", "libmp3lame",
            "-b:a", "320k",
            "-map_metadata", "-1"  # 不写入多余元数据
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="根据结构化歌单 CSV 生成 Side A/B 混音（ffmpeg 引擎默认，支持音量/响度/淡入淡出/跨衔接）")
    parser.add_argument(
        "--playlist",
        type=Path,
        required=True,
        help="结构化歌单 CSV 路径（由 create_mixtape.py 生成）",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help="配置文件路径，默认 config/config.yaml（兼容 legacy library_settings.yml）",
    )
    parser.add_argument(
        "--engine",
        type=str,
        choices=["ffmpeg", "pydub"],
        default="ffmpeg",
        help="混音引擎，默认 ffmpeg；可选 pydub",
    )
    parser.add_argument(
        "--audio_bitrate",
        type=str,
        default="320k",
        help="导出 MP3 比特率，默认 320k（>=256k）",
    )
    parser.add_argument("--lufs", type=float, default=-14.0, help="目标响度（LUFS），默认 -14")
    parser.add_argument("--tp", type=float, default=-1.0, help="最大真峰值（dBTP），默认 -1.0")
    parser.add_argument("--vinyl_noise_db", type=float, default=-18.0, help="Vinyl Noise 增益（dB），默认 -18（约12.6%音量）")
    parser.add_argument("--needle_gain_db", type=float, default=-18.0, help="Needle Start 增益（dB），默认 -18（约12.6%音量）")
    parser.add_argument("--xfade_ms", type=int, default=1500, help="曲目间跨衔接时长（毫秒，pydub 引擎）")
    parser.add_argument("--track_fade_in_ms", type=int, default=120, help="曲目淡入时长（毫秒，pydub 引擎）")
    parser.add_argument("--track_fade_out_ms", type=int, default=200, help="曲目淡出时长（毫秒，pydub 引擎）")
    parser.add_argument("--sfx_fade_in_ms", type=int, default=80, help="SFX 淡入（毫秒，pydub 引擎）")
    parser.add_argument("--sfx_fade_out_ms", type=int, default=200, help="SFX 淡出（毫秒，pydub 引擎）")
    parser.add_argument("--mix_mode", type=str, choices=["timeline","sequential"], default="timeline", help="pydub 引擎混音模式：timeline/顺序拼接（带跨衔接）")
    args = parser.parse_args()

    playlist_path = args.playlist
    if not playlist_path.exists():
        raise FileNotFoundError(f"未找到歌单文件：{playlist_path}")

    try:
        app_config = AppConfig.load(config_path=args.config, fallback_legacy=True)
    except ConfigError as exc:
        raise SystemExit(f"[配置错误] {exc}") from exc

    global OUTPUT_DIR, SFX_DIR
    OUTPUT_DIR = app_config.paths.output_dir.expanduser()
    SFX_DIR = app_config.paths.sfx_dir.expanduser()

    library_root = app_config.library.song_library_root.expanduser()
    if not library_root.exists():
        raise FileNotFoundError(f"歌库目录不存在：{library_root}")

    extensions = list(app_config.library.audio_extensions) or [".mp3", ".wav", ".flac", ".m4a", ".aac"]

    needle_start = (SFX_DIR / "Needle_Start.mp3").resolve()
    vinyl_noise = (SFX_DIR / "Vinyl_Noise.mp3").resolve()
    if not needle_start.exists():
        raise MissingAssetError(f"缺少 Needle Start 音效：{needle_start}")
    if not vinyl_noise.exists():
        raise MissingAssetError(f"缺少 Vinyl Noise 音效：{vinyl_noise}")


    # 只生成full mix，严格按timeline顺序拼接
    # 解析timeline为顺序事件
    def parse_full_timeline(csv_path: Path):
        events = []
        with csv_path.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if (row.get("Section") or "").strip() != "Timeline":
                    continue
                if (row.get("Timeline") or "").strip() != "Needle":
                    continue
                events.append({
                    "side": (row.get("Side") or "").strip(),
                    "timestamp": (row.get("Timestamp") or "").strip(),
                    "description": (row.get("Description") or "").strip(),
                })
        return events

    stem = playlist_path.stem.replace("_mixtape_playlist", "")
    events = parse_full_timeline(playlist_path)
    print(f"▶ 正在生成 full_mix（引擎: {args.engine}）")

    if args.engine == "pydub":
        if AudioSegment is None:
            print("[ERROR] pydub 引擎不可用（可能因 Python 3.14 缺少 audioop）。请改用 --engine ffmpeg。")
            return
        # pydub 引擎：两种模式
        if args.mix_mode == "timeline":
            timeline = []
            max_end = 0
            def parse_ts(ts):
                if not ts or ":" not in ts:
                    return 0
                parts = ts.strip().split(":")
                if len(parts) == 2:
                    m, s = parts
                    return (int(m) * 60 + int(s)) * 1000
                elif len(parts) == 3:
                    h, m, s = parts
                    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000
                return 0
            for event in events:
                desc = event["description"]
                ts = event["timestamp"]
                start_ms = parse_ts(ts)
                seg = None
                if desc == "Silence":
                    seg = AudioSegment.silent(duration=3000, frame_rate=TRACK_SAMPLE_RATE)
                elif desc == "Needle On Vinyl Record":
                    seg = AudioSegment.from_file(needle_start).set_frame_rate(TRACK_SAMPLE_RATE).set_channels(TRACK_CHANNELS)
                    seg = seg + args.needle_gain_db
                    seg = seg.fade_in(args.sfx_fade_in_ms).fade_out(args.sfx_fade_out_ms)
                elif desc == "Vinyl Noise":
                    seg = AudioSegment.from_file(vinyl_noise).set_frame_rate(TRACK_SAMPLE_RATE).set_channels(TRACK_CHANNELS)
                    seg = seg + args.vinyl_noise_db
                    seg = seg.fade_in(args.sfx_fade_in_ms).fade_out(args.sfx_fade_out_ms)
                elif desc:
                    try:
                        seg_path = resolve_track_path(desc, library_root, extensions)
                        seg = AudioSegment.from_file(seg_path).set_frame_rate(TRACK_SAMPLE_RATE).set_channels(TRACK_CHANNELS)
                        seg = seg.fade_in(args.track_fade_in_ms).fade_out(args.track_fade_out_ms)
                    except Exception as e:
                        print(f"[WARN] 曲目 {desc} 加载失败: {e}")
                if seg is not None:
                    end_ms = start_ms + len(seg)
                    max_end = max(max_end, end_ms)
                    timeline.append((start_ms, seg))
            if not timeline:
                print("❌ 无法生成full mix，timeline无有效片段。")
                return
            base = AudioSegment.silent(duration=max_end + 1000, frame_rate=TRACK_SAMPLE_RATE)
            for start_ms, seg in timeline:
                base = base.overlay(seg, position=start_ms)
            full_mix = base.fade_out(800)
        else:
            # sequential：按出现顺序拼接，曲目间 acrossfade
            chain: AudioSegment | None = None
            prev_was_track = False
            for event in events:
                desc = (event.get("description") or "").strip()
                if not desc:
                    continue
                if desc == "Silence":
                    seg = AudioSegment.silent(duration=3000, frame_rate=TRACK_SAMPLE_RATE)
                    is_track = False
                elif desc == "Needle On Vinyl Record":
                    seg = AudioSegment.from_file(needle_start).set_frame_rate(TRACK_SAMPLE_RATE).set_channels(TRACK_CHANNELS)
                    seg = seg + args.needle_gain_db
                    seg = seg.fade_in(args.sfx_fade_in_ms).fade_out(args.sfx_fade_out_ms)
                    is_track = False
                elif desc == "Vinyl Noise":
                    seg = AudioSegment.from_file(vinyl_noise).set_frame_rate(TRACK_SAMPLE_RATE).set_channels(TRACK_CHANNELS)
                    seg = seg + args.vinyl_noise_db
                    seg = seg.fade_in(args.sfx_fade_in_ms).fade_out(args.sfx_fade_out_ms)
                    is_track = False
                else:
                    try:
                        seg_path = resolve_track_path(desc, library_root, extensions)
                        seg = AudioSegment.from_file(seg_path).set_frame_rate(TRACK_SAMPLE_RATE).set_channels(TRACK_CHANNELS)
                        seg = seg.fade_in(args.track_fade_in_ms).fade_out(args.track_fade_out_ms)
                        is_track = True
                    except Exception as e:
                        print(f"[WARN] 曲目 {desc} 加载失败: {e}")
                        continue
                if chain is None:
                    chain = seg
                else:
                    if prev_was_track and is_track and args.xfade_ms > 0:
                        chain = chain.append(seg, crossfade=args.xfade_ms)
                    else:
                        chain = chain + seg
                prev_was_track = is_track
            if chain is None:
                print("❌ 无可拼接片段。")
                return
            full_mix = chain.fade_out(800)

        target = OUTPUT_DIR / f"{stem}_full_mix.mp3"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        full_mix.export(str(target), format="mp3", bitrate=args.audio_bitrate)
        print(f"✅ full_mix 混音完成：{target}")
        return

    # === ffmpeg 引擎 ===
    # 为每个事件准备一个输入，并用 adelay 定位到时间轴，再用 amix 叠加
    input_paths: List[Path] = []
    filters: List[str] = []
    labels: List[str] = []
    idx = 0

    def ms_of(ts: str) -> int:
        if not ts or ":" not in ts:
            return 0
        parts = ts.strip().split(":")
        if len(parts) == 2:
            m, s = parts
            return (int(m) * 60 + int(s)) * 1000
        if len(parts) == 3:
            h, m, s = parts
            return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000
        return 0

    for ev in events:
        desc = ev.get("description", "")
        ts = ev.get("timestamp", "")
        delay = ms_of(ts)
        if not desc:
            continue
        if desc == "Silence":
            # 用 anullsrc 生成 3s 静音，务必 atrim 限定长度，避免无限长导致总时长被拉长
            lbl = f"a{idx}"
            filters.append(f"anullsrc=r={TRACK_SAMPLE_RATE}:cl=stereo,atrim=0:3,adelay={delay}|{delay}[{lbl}]")
            labels.append(lbl)
            idx += 1
            continue
        if desc == "Needle On Vinyl Record":
            path = needle_start
            vol = 10 ** (args.needle_gain_db / 20.0)
        elif desc == "Vinyl Noise":
            path = vinyl_noise
            vol = 10 ** (args.vinyl_noise_db / 20.0)
        else:
            try:
                path = resolve_track_path(desc, library_root, extensions)
            except Exception as e:
                print(f"[WARN] 未找到曲目 {desc}: {e}")
                continue
            vol = 1.0
        input_paths.append(path)
        in_idx = len(input_paths) - 1
        lbl = f"a{idx}"
        # aformat 统一采样率/声道；volume；adelay 定位
        filters.append(
            f"[{in_idx}:a]aformat=sample_fmts=fltp:sample_rates={TRACK_SAMPLE_RATE}:channel_layouts=stereo,volume={vol},adelay={delay}|{delay}[{lbl}]"
        )
        labels.append(lbl)
        idx += 1

    if not labels and not filters:
        print("❌ 无可混音事件。")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / f"{stem}_full_mix.mp3"

    # 拼接 amix 叠加所有标签
    label_concat = "".join(f"[{l}]" for l in labels)
    if len(labels) > 1:
        post = f"{label_concat}amix=inputs={len(labels)}:normalize=0,loudnorm=I={args.lufs}:TP={args.tp}:LRA=11:print_format=summary[mix]"
    else:
        post = f"[{labels[0]}]loudnorm=I={args.lufs}:TP={args.tp}:LRA=11:print_format=summary[mix]"
    filter_complex = filters + [post]

    # 构造命令
    cmd: List[str] = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    # 独立的合成静音源（如果 filters 中使用了 anullsrc，它不需要 -i）
    for p in input_paths:
        cmd += ["-i", str(p)]
    cmd += [
        "-filter_complex",
        ";".join(filter_complex),
        "-map", "[mix]",
        "-c:a", "libmp3lame",
        "-b:a", args.audio_bitrate,
        str(target),
    ]

    try:
        import subprocess
        print("▶ ffmpeg 混音命令:", " ".join(cmd))
        subprocess.run(cmd, check=True)
        print(f"✅ full_mix 混音完成：{target}")
    except Exception as e:
        print(f"[ERROR] ffmpeg 混音失败: {e}")


if __name__ == "__main__":
    main()
