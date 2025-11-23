"""
Mix Engine Boundary

这里是唯一可以直接调用 ffmpeg 进行音频混音的地方。
assets/mix.py 只知道"我调用一个混音接口拿到结果"，不知道 ffmpeg 的命令行细节。

未来要改 filtergraph、甚至换整套混音引擎，全都只动这个文件。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from dataclasses import dataclass
import subprocess
import asyncio

from ..models import EpisodeSpec, AssetPaths
from ..config import McPOSConfig
from ..core.logging import log_info, log_error, log_warning


def _check_ffmpeg_available() -> bool:
    """
    检查 ffmpeg 是否可用（同步函数，用于快速检查）
    
    注意：这是一个轻量级的同步检查，不会阻塞事件循环。
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@dataclass
class MixResult:
    """混音结果"""
    output_path: Path
    size_bytes: int
    metadata: dict[str, Any] | None = None


async def mix_episode_audio(
    spec: EpisodeSpec,
    paths: AssetPaths,
    cfg: McPOSConfig,
    filtergraph: str,
    input_paths: list[Path],
    output_path: Path,
) -> MixResult:
    """
    音频混音边界函数
    
    这是所有音频混音的唯一入口。
    
    Args:
        spec: Episode specification
        paths: Asset paths
        cfg: McPOS configuration
        filtergraph: FFmpeg filtergraph 字符串（由 assets/mix.py 构建）
        input_paths: 输入音频文件路径列表（包括 tracks 和 SFX）
        output_path: 输出音频文件路径（根据扩展名决定编码格式：.mp3 或 .m4a/.aac）
    
    Returns:
        MixResult with output_path and metadata
    
    Raises:
        RuntimeError: 如果混音失败
    
    Note:
        - 使用 McPOS 全局音频标准：256 kbps CBR, 48 kHz
        - 输出格式由 output_path 扩展名决定：
          - .mp3 → libmp3lame 编码（用于 full_mix.mp3 归档）
          - .m4a/.aac → aac 编码（用于 final_mix.m4a 渲染，MP4 标准）
        - 所有 ffmpeg 命令细节都在此函数内，assets 层不关心
    """
    if not _check_ffmpeg_available():
        raise RuntimeError("ffmpeg is not available. Please install ffmpeg.")
    
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
    ]
    
    # 添加输入文件
    for p in input_paths:
        cmd += ["-i", str(p)]
    
    # 根据输出文件扩展名决定编码格式
    output_ext = output_path.suffix.lower()
    if output_ext in [".m4a", ".aac"]:
        # AAC 编码（用于 final_mix.m4a，MP4 标准，可直接复制到视频）
        audio_codec = "aac"
        log_info(f"[mix] Using AAC encoding for {output_path.name} (MP4 standard)")
    elif output_ext == ".mp3":
        # MP3 编码（用于 full_mix.mp3 归档）
        audio_codec = "libmp3lame"
        log_info(f"[mix] Using MP3 encoding for {output_path.name} (archival)")
    else:
        # 默认使用 AAC（推荐）
        audio_codec = "aac"
        log_warning(f"[mix] Unknown extension {output_ext}, defaulting to AAC encoding")
    
    # 添加 filtergraph
    cmd += [
        "-filter_complex",
        filtergraph,
        "-map", "[mix]",
        "-c:a", audio_codec,
        "-b:a", "256k",  # CBR (恒定比特率) 256 kbps - McPOS 全局标准
        "-ar", "48000",  # 采样率 48 kHz - McPOS 全局标准
        str(output_path),
    ]
    
    log_info(f"[mix] Executing FFmpeg filtergraph for {spec.episode_id}")
    log_info(f"[mix] FFmpeg command: {' '.join(cmd)}")
    
    # 使用 asyncio.run_in_executor 避免阻塞事件循环
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1小时超时
        ),
    )
    
    if result.returncode != 0:
        error_msg = result.stderr or "Unknown error"
        log_error(f"[mix] FFmpeg audio mixing failed: {error_msg}")
        raise RuntimeError(f"Audio mix failed: {error_msg}")
    
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg produced empty or missing output: {output_path}")
    
    log_info(f"[mix] ✅ Audio mix complete: {output_path} ({output_path.stat().st_size} bytes)")
    
    return MixResult(
        output_path=output_path,
        size_bytes=output_path.stat().st_size,
        metadata={
            "filtergraph_inputs": len(input_paths),
            "output_bitrate": "256k",
            "output_sample_rate": "48000",
        },
    )

