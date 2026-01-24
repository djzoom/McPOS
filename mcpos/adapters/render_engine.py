"""
Render Engine Boundary

这里是唯一可以直接调用 ffmpeg、图像合成等"重型外部工具"的地方。
assets/render.py 只知道"我调用一个渲染接口拿到结果"，不知道 ffmpeg 的命令行细节。

未来要改 CRF、preset、甚至换整套渲染引擎，全都只动这个文件。

参考旧世界实现：
- kat_rec_web/backend/t2r/utils/direct_video_render.py
- kat_rec_web/backend/t2r/utils/video_render_config.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import subprocess
import json
import asyncio
from datetime import datetime
import os
import time

from ..models import EpisodeSpec, AssetPaths
from ..config import McPOSConfig
from ..core.logging import log_info, log_error, log_warning

# ✅ McPOS Kat 频道视频渲染标准参数（与旧世界一致）
# 经过测试验证的最优参数组合，实现最佳文件大小和质量平衡
# 注意：此模块仅用于 Kat 频道（静态图片循环视频）
# RBR 频道应使用独立的渲染模块（mcpos/adapters/rbr_render_engine.py）

# 视频编码参数
VIDEO_CODEC = "libx264"
VIDEO_PRESET = "veryfast"  # 编码速度预设
VIDEO_CRF = "35"  # 质量因子（Constant Rate Factor）
VIDEO_TUNE = "stillimage"  # 针对静态图片优化，码率降低20-30倍（最关键）
VIDEO_GOP_SIZE = "3600"  # 关键帧间隔：每3600秒（1小时）一个I帧（fps=1时）
VIDEO_PIX_FMT = "yuv420p"  # 像素格式：标准格式，文件更小，兼容性更好

# x264参数
X264_KEYINT = "3600"  # 关键帧间隔（与-g 3600配合）
X264_MIN_KEYINT = "3600"  # 最小关键帧间隔

# 视频滤镜参数
VIDEO_FPS = "1"  # 帧率：静态图片只需要1帧/秒
VIDEO_FPS_ROUND = "near"  # 帧率舍入模式：最近舍入（修复 round=down 导致的时长截断问题）
VIDEO_SCALE_WIDTH = "3840"  # 4K宽度
VIDEO_SCALE_HEIGHT = "2160"  # 4K高度

# 音频编码参数
# 注意：MP4 容器必须使用 AAC 编码，不能直接复制 MP3（兼容性问题）
# 即使输入是 MP3，也必须转码为 AAC 以确保播放器兼容性

# 时间戳模式
VSYNC_MODE = "vfr"  # 可变帧率（与 fps=1:round=down 配合使用）

# 容器参数
MOVFLAGS = "+faststart"  # 快速启动：将 moov atom 移到文件开头，便于流式播放


def _get_video_filter() -> str:
    """
    获取视频滤镜字符串（强制输出 4K 分辨率）
    
    滤镜链：
    1. scale: 缩放到 4K，保持宽高比（不拉伸）
    2. pad: 填充到精确的 3840×2160，居中（黑边）
    3. fps: 设置为 1 FPS（静态图片）
    
    Returns:
        视频滤镜字符串，用于FFmpeg的-vf参数，确保输出严格为 4K (3840×2160)
    """
    return (
        f"scale={VIDEO_SCALE_WIDTH}:{VIDEO_SCALE_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_SCALE_WIDTH}:{VIDEO_SCALE_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={VIDEO_FPS}:round={VIDEO_FPS_ROUND}"
    )


def _get_x264_params() -> str:
    """
    获取x264参数字符串
    
    Returns:
        x264参数字符串，用于FFmpeg的-x264-params参数
    """
    return f"keyint={X264_KEYINT}:min-keyint={X264_MIN_KEYINT}"


def _build_video_encoding_args() -> list[str]:
    """
    构建视频编码参数列表
    
    Returns:
        FFmpeg视频编码参数列表
    """
    return [
        "-c:v", VIDEO_CODEC,
        "-preset", VIDEO_PRESET,
        "-crf", VIDEO_CRF,
        "-tune", VIDEO_TUNE,  # 关键：针对静态图片优化，大幅降低码率
        "-g", VIDEO_GOP_SIZE,  # 关键帧间隔：每3600秒（1小时）一个I帧（fps=1时）
        "-x264-params", _get_x264_params(),  # 与-g 3600配合
    ]


def _build_audio_encoding_args(audio_path: Path) -> list[str]:
    """
    构建音频编码参数列表
    
    Args:
        audio_path: 音频文件路径，用于判断是否需要转码
    
    Returns:
        FFmpeg音频编码参数列表
    
    Note:
        - 如果输入是 AAC 格式（.m4a/.aac），可以直接复制（-c:a copy），无需转码
        - 如果输入是其他格式（如 MP3），需要转码为 AAC
        - 使用 256 kbps 比特率，与 McPOS 全局音频标准一致
        - 采样率保持 48 kHz
    """
    audio_ext = audio_path.suffix.lower()
    
    if audio_ext in [".m4a", ".aac"]:
        # 输入已经是 AAC 格式，可以直接复制（无需转码，更快）
        log_info(
            f"Input audio is already AAC format ({audio_path.suffix}), "
            f"using copy mode (no transcoding needed)"
        )
        return ["-c:a", "copy"]
    else:
        # 输入是其他格式（如 MP3），需要转码为 AAC
        log_info(
            f"Transcoding audio to AAC for MP4 compatibility "
            f"(input: {audio_path.suffix}, output: AAC 256kbps)"
        )
        return [
            "-c:a", "aac",  # 使用 AAC 编码（MP4 标准）
            "-b:a", "256k",  # 256 kbps 比特率（与 McPOS 全局音频标准一致）
            "-ar", "48000",  # 48 kHz 采样率
        ]


def _build_common_args() -> list[str]:
    """
    构建通用参数列表（像素格式、时间戳模式等）
    
    Returns:
        FFmpeg通用参数列表
    
    Note:
        - 移除了 -fps_mode passthrough，因为已在 -vf 中强制 fps=1:round=near
        - -shortest 作为回退方案（如果无法获取音频时长）
        - 优先使用 -t 参数显式指定音频时长（修复 round=down 导致的时长截断问题）
    """
    return [
        "-pix_fmt", VIDEO_PIX_FMT,  # 像素格式：yuv420p
        "-vsync", VSYNC_MODE,  # 可变帧率（与 fps=1:round=down 配合使用）
        "-shortest",  # 时长控制：确保视频长度匹配音频（Unified Pre-Mix 架构）
        "-movflags", MOVFLAGS,  # 快速启动
    ]


def _get_render_config_summary() -> str:
    """
    获取渲染配置摘要（用于日志）
    
    Returns:
        配置摘要字符串
    """
    return (
        f"4K ({VIDEO_SCALE_WIDTH}×{VIDEO_SCALE_HEIGHT}), {VIDEO_FPS}FPS, CRF {VIDEO_CRF}, "
        f"{VIDEO_PRESET} preset, g={VIDEO_GOP_SIZE}, tune={VIDEO_TUNE}, {VIDEO_PIX_FMT}, "
        f"audio=AAC (copy if input is AAC, transcode otherwise)"
    )


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


def _check_ffprobe_available() -> bool:
    """
    检查 ffprobe 是否可用（同步函数，用于快速检查）
    
    注意：这是一个轻量级的同步检查，不会阻塞事件循环。
    """
    try:
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def probe_video_metadata(video_path: Path) -> dict[str, Any] | None:
    """
    使用 ffprobe 检查视频元数据（边界函数）
    
    这是所有视频元数据检查的唯一入口。
    无论是 render 阶段的输出验证，还是 upload 阶段的前置检查，都通过此函数。
    
    Args:
        video_path: 视频文件路径
    
    Returns:
        dict 包含 width, height, audio_sample_rate, audio_bit_rate 等信息
        如果检查失败返回 None
    """
    if not _check_ffprobe_available():
        log_warning("ffprobe not available, skipping video metadata check")
        return None
    
    try:
        # 分别获取视频流和音频流信息
        cmd_video = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            str(video_path),
        ]
        
        cmd_audio = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate,bit_rate",
            "-of", "json",
            str(video_path),
        ]
        
        result_video = subprocess.run(
            cmd_video,
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        result_audio = subprocess.run(
            cmd_audio,
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # 如果视频流检查失败，记录错误信息
        if result_video.returncode != 0:
            error_msg = result_video.stderr or "Unknown error"
            log_error(f"Failed to probe video stream: {error_msg}")
            # 如果视频流无法读取，文件可能损坏
            return None
        
        # 如果音频流检查失败，记录警告（某些视频可能没有音频）
        if result_audio.returncode != 0:
            log_warning(f"Failed to probe audio stream (video may have no audio): {result_audio.stderr}")
        
        metadata = {}
        
        if result_video.returncode == 0:
            try:
                data_video = json.loads(result_video.stdout)
                for stream in data_video.get("streams", []):
                    if "width" in stream:
                        metadata["width"] = stream.get("width")
                    if "height" in stream:
                        metadata["height"] = stream.get("height")
            except json.JSONDecodeError as e:
                log_error(f"Failed to parse video stream metadata JSON: {e}")
                return None
        
        if result_audio.returncode == 0:
            try:
                data_audio = json.loads(result_audio.stdout)
                for stream in data_audio.get("streams", []):
                    if "sample_rate" in stream:
                        metadata["sample_rate"] = stream.get("sample_rate")
                    if "bit_rate" in stream:
                        metadata["bit_rate"] = stream.get("bit_rate")
            except json.JSONDecodeError as e:
                log_warning(f"Failed to parse audio stream metadata JSON: {e}")
        
        # 如果无法获取任何元数据，返回 None（可能文件损坏）
        return metadata if metadata else None
        
    except subprocess.TimeoutExpired:
        log_error("Video metadata probe timeout - file may be corrupted or too large")
        return None
    except Exception as e:
        log_error(f"Failed to probe video metadata: {e}")
        return None


@dataclass
class RenderResult:
    """渲染结果"""
    video_path: Path
    render_flag_path: Path
    metadata: dict[str, Any] | None = None


async def render_episode_video(
    spec: EpisodeSpec,
    paths: AssetPaths,
    cfg: McPOSConfig,
    *,
    dry_run: bool = False,
) -> RenderResult:
    """
    Kat 频道视频渲染边界函数。
    
    这是 Kat 频道视频渲染的唯一入口。
    
    - Called only from mcpos/assets/render.py (Kat 频道)
    - Uses Unified Pre-Mix Architecture: directly uses final_mix.mp3, no real-time mixing
    - Video length is determined by audio length (-shortest flag)
    - 仅支持静态图片循环视频（1 FPS, tune=stillimage）
    
    Args:
        spec: Episode specification (channel_id 应为 "kat")
        paths: Asset paths
        cfg: McPOS configuration
        dry_run: If True, only log the command without executing
    
    Returns:
        RenderResult with video_path, render_flag_path, and metadata
    
    Note:
        - 此函数仅用于 Kat 频道（静态图片循环视频）
        - RBR 频道应使用独立的渲染模块（mcpos/adapters/rbr_render_engine.py）
        - 如果 channel_id 不是 "kat"，会记录警告但继续执行（向后兼容）
    """
    if spec.channel_id != "kat":
        log_warning(
            f"render_episode_video is designed for Kat channel only. "
            f"Channel '{spec.channel_id}' should use channel-specific render engine. "
            f"Continuing with Kat parameters for backward compatibility."
        )
    video_path = paths.youtube_mp4
    flag_path = paths.render_complete_flag
    temp_video_path = video_path.with_suffix(video_path.suffix + ".part")
    lock_path = video_path.with_suffix(video_path.suffix + ".lock")

    # 防止并发渲染互相踩文件
    if lock_path.exists():
        age_seconds = time.time() - lock_path.stat().st_mtime
        # 6 小时以内通常认为仍在渲染中，但如果锁文件记录的 pid 已不存在，
        # 则视为“崩溃残留锁”，自动归档并继续（避免人工介入）。
        if age_seconds < 6 * 3600:
            pid = None
            try:
                payload = json.loads(lock_path.read_text(encoding="utf-8"))
                pid_val = payload.get("pid")
                if pid_val is not None:
                    pid = int(pid_val)
            except Exception:
                pid = None

            stale = False
            if pid and pid > 0:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    stale = True
                except PermissionError:
                    stale = False

            if not stale:
                raise RuntimeError(
                    f"Render lock exists (in-progress): {lock_path} "
                    f"(age={age_seconds/3600:.2f}h)."
                )

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                lock_path.rename(lock_path.with_name(lock_path.name + f".aborted_{ts}"))
            except Exception:
                pass
            if temp_video_path.exists():
                try:
                    temp_video_path.rename(temp_video_path.with_name(temp_video_path.name + f".aborted_{ts}"))
                except Exception:
                    pass
            log_warning(f"[render] Stale render lock cleared: {lock_path} (pid={pid})")
        else:
            # 锁过期，清理
            try:
                lock_path.unlink()
            except Exception:
                pass
    
    if dry_run:
        # 测试模式：只创建空文件
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.touch()
        flag_path.touch()
        return RenderResult(
            video_path=video_path,
            render_flag_path=flag_path,
            metadata={"dry_run": True}
        )
    
    # 检查必需输入文件
    cover_path = paths.cover_png
    audio_path = paths.final_mix_mp3  # 使用 MP3 格式（渲染时会转码为 AAC）
    
    if not cover_path.exists():
        raise FileNotFoundError(f"Cover image not found: {cover_path}")
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # 清理残留的临时文件
    if temp_video_path.exists():
        try:
            temp_video_path.unlink()
        except Exception:
            pass
    
    # 检查 ffmpeg 是否可用
    if not _check_ffmpeg_available():
        raise RuntimeError("ffmpeg is not available. Please install ffmpeg.")
    
    # 构建 FFmpeg 命令（参考旧世界的 direct_video_render.py）
    # 使用统一的全频道渲染标准配置
    cmd: list[str] = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        # Input 0: 封面图片（静态）
        "-loop", "1", "-i", str(cover_path),
        # Input 1: 预混音音频（final_mix.mp3, MP3 格式, 256kbps CBR, 48kHz，渲染时转码为 AAC）
        "-i", str(audio_path),
    ]
    
    # 显式指定流映射（防止未来多输入时选错流）
    cmd += ["-map", "0:v:0"]  # 选择输入 0 的第一个视频流
    cmd += ["-map", "1:a:0"]  # 选择输入 1 的第一个音频流
    
    # 视频滤镜：强制缩放到 4K (3840×2160)，fps=1（静态图片只需要1帧/秒）
    # 使用 scale 和 pad 确保输出分辨率严格为 4K
    cmd += ["-vf", _get_video_filter()]
    
    # 获取音频时长，用于显式指定视频时长（修复 -shortest 可能选择错误流的问题）
    try:
        audio_duration_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)
        ]
        audio_duration_result = subprocess.run(
            audio_duration_cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if audio_duration_result.returncode == 0:
            audio_duration = float(audio_duration_result.stdout.strip())
            # 使用 -t 参数显式指定视频时长，确保匹配音频时长
            cmd += ["-t", str(int(audio_duration) + 1)]  # +1 秒确保完整覆盖
            log_info(f"[render] 使用音频时长显式指定视频时长: {audio_duration:.1f}秒")
        else:
            # 如果无法获取音频时长，回退到 -shortest
            log_warning(f"[render] 无法获取音频时长，使用 -shortest 参数")
            cmd.extend(_build_common_args())
    except Exception as e:
        # 如果获取音频时长失败，回退到 -shortest
        log_warning(f"[render] 获取音频时长失败: {e}, 使用 -shortest 参数")
        cmd.extend(_build_common_args())
    
    # 如果没有使用 -t 参数，则使用通用参数（包含 -shortest）
    if "-t" not in cmd:
        cmd.extend(_build_common_args())
    
    # 添加视频编码参数（全频道标准：CRF 35, veryfast, g=3600, tune=stillimage）
    cmd.extend(_build_video_encoding_args())
    
    # 添加音频编码参数（根据音频文件格式决定是否转码）
    cmd.extend(_build_audio_encoding_args(audio_path))
    
    # 输出文件路径（使用临时后缀时需显式指定容器格式）
    cmd += ["-f", "mp4"]
    cmd.append(str(temp_video_path))
    
    log_info(f"[render] 开始渲染 4K 视频 ({_get_render_config_summary()}): {video_path}")
    log_info(f"[render] 输入: 封面={cover_path.name}, 音频={audio_path.name}")
    log_info(f"[render] 输出分辨率: {VIDEO_SCALE_WIDTH}×{VIDEO_SCALE_HEIGHT} (4K)")
    log_info(f"[render] FFmpeg 命令: {' '.join(cmd)}")
    
    # 使用 asyncio.run_in_executor 避免阻塞事件循环
    # 超时时间：对于65分钟音频，渲染时间可能需要更长时间（特别是4K渲染）
    # 设置为4小时以确保完整渲染
    loop = asyncio.get_running_loop()
    
    # 先检查音频长度，估算所需时间
    try:
        audio_duration_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)
        ]
        audio_duration_result = subprocess.run(
            audio_duration_cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if audio_duration_result.returncode == 0:
            audio_duration = float(audio_duration_result.stdout.strip())
            # 估算渲染时间：音频长度 * 2（保守估计，实际可能更快）
            estimated_render_time = int(audio_duration * 2)
            # 最少2小时，最多6小时
            timeout_seconds = max(7200, min(estimated_render_time, 21600))
            log_info(f"[render] 音频长度: {audio_duration:.1f}秒 ({audio_duration/60:.1f}分钟), 设置超时: {timeout_seconds}秒 ({timeout_seconds/3600:.1f}小时)")
        else:
            timeout_seconds = 14400  # 默认4小时
            log_warning(f"[render] 无法获取音频长度，使用默认超时: {timeout_seconds}秒")
    except Exception as e:
        timeout_seconds = 14400  # 默认4小时
        log_warning(f"[render] 获取音频长度失败: {e}, 使用默认超时: {timeout_seconds}秒")
    
    # 写入渲染锁（避免并发渲染）
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_payload = {
        "episode_id": spec.episode_id,
        "channel_id": spec.channel_id,
        "started_at": datetime.now().isoformat(),
        "pid": os.getpid(),
        "temp_video_path": str(temp_video_path),
    }
    lock_path.write_text(json.dumps(lock_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            ),
        )
    finally:
        # 如果发生异常，尽量清理锁（成功路径会在后面再次删除）
        try:
            if lock_path.exists():
                lock_path.unlink()
        except Exception:
            pass
    
    if result.returncode != 0:
        error_msg = result.stderr or "Unknown error"
        log_error(f"[render] FFmpeg video generation failed: {error_msg}")
        raise RuntimeError(f"Video render failed: {error_msg}")
    
    if not temp_video_path.exists() or temp_video_path.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg produced empty or missing output: {temp_video_path}")
    
    # 验证视频文件完整性（使用 ffprobe 检查是否可以正常读取）
    log_info(f"[render] Verifying video file integrity: {temp_video_path}")
    try:
        verify_cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(temp_video_path),
        ]
        verify_result = subprocess.run(
            verify_cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if verify_result.returncode != 0:
            error_msg = verify_result.stderr or "Unknown error"
            log_error(f"[render] Video file verification failed: {error_msg}")
            # 删除损坏的视频文件
            if temp_video_path.exists():
                temp_video_path.unlink()
                log_warning(f"[render] Removed corrupted video file: {temp_video_path}")
            raise RuntimeError(f"Video file is corrupted or incomplete: {error_msg}")
        log_info(f"[render] Video file integrity check passed")
    except subprocess.TimeoutExpired:
        log_error(f"[render] Video verification timeout (file may be corrupted)")
        if temp_video_path.exists():
            temp_video_path.unlink()
            log_warning(f"[render] Removed potentially corrupted video file: {temp_video_path}")
        raise RuntimeError("Video file verification timeout")
    except Exception as e:
        log_error(f"[render] Video verification error: {e}")
        if temp_video_path.exists():
            temp_video_path.unlink()
            log_warning(f"[render] Removed potentially corrupted video file: {temp_video_path}")
        raise RuntimeError(f"Video file verification failed: {e}")

    # 验证通过后原子替换为最终文件
    os.replace(temp_video_path, video_path)
    
    # 创建完成标志
    flag_data = {
        "episode_id": spec.episode_id,
        "channel_id": spec.channel_id,
        "rendered_at": datetime.now().isoformat(),
        "video_path": str(video_path),
        "video_size_bytes": video_path.stat().st_size,
        "config_summary": _get_render_config_summary(),
    }
    log_info(f"[render] Writing render flag to {flag_path}")
    flag_path.parent.mkdir(parents=True, exist_ok=True)
    flag_path.write_text(
        json.dumps(flag_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 清理锁
    try:
        if lock_path.exists():
            lock_path.unlink()
    except Exception:
        pass
    
    log_info(f"[render] ✅ 视频生成完成（{_get_render_config_summary()}）：{video_path}")
    
    return RenderResult(
        video_path=video_path,
        render_flag_path=flag_path,
        metadata={
            "rendered_at": flag_data["rendered_at"],
            "video_size_bytes": flag_data["video_size_bytes"],
            "config_summary": flag_data["config_summary"],
        }
    )
