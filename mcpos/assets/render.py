"""
视频渲染

按照文档标准实现：使用 FFmpeg 将封面图片和预混音音频组合成 4K 视频。
参考旧世界的 Unified Pre-Mix Architecture：直接使用 final_mix.mp3，不再实时混音。
"""

from pathlib import Path
from datetime import datetime

from ..models import EpisodeSpec, AssetPaths, StageResult, StageName
from ..core.logging import log_info, log_error, log_warning
from ..adapters.render_engine import render_episode_video, RenderResult, probe_video_metadata
from ..config import get_config

# 频道特定的渲染函数（延迟导入，避免循环依赖）
# RBR 频道使用独立的渲染模块
try:
    from ..adapters.rbr_render_engine import render_rbr_episode_video
except ImportError:
    render_rbr_episode_video = None


def _validate_render_output(video_path: Path) -> None:
    """
    验证渲染输出是否符合 McPOS 全局技术标准
    
    - 视频文件完整性：可以正常读取和解析
    - 视频分辨率：3840×2160 (4K)
    - 音频采样率：48000 Hz
    - 音频比特率：256 kbps (256000 bps)
    
    Raises:
        RuntimeError: 如果输出不符合标准或文件损坏
    
    Note:
        使用边界函数 probe_video_metadata() 获取元数据，不直接调用 ffprobe。
    """
    metadata = probe_video_metadata(video_path)
    
    if metadata is None:
        # 如果无法获取元数据，可能是文件损坏
        log_error("Could not probe video metadata - file may be corrupted")
        raise RuntimeError(
            f"Video file appears to be corrupted or unreadable: {video_path}. "
            f"Please check the render logs and re-render if necessary."
        )
    
    errors = []
    
    # 检查视频分辨率
    width = metadata.get("width")
    height = metadata.get("height")
    if width != 3840 or height != 2160:
        errors.append(f"Video resolution mismatch: expected 3840×2160, got {width}×{height}")
    
    # 检查音频采样率（如果存在）
    sample_rate = metadata.get("sample_rate")
    if sample_rate:
        # ffprobe 可能返回字符串
        try:
            sample_rate_int = int(sample_rate)
            if sample_rate_int != 48000:
                errors.append(f"Audio sample rate mismatch: expected 48000 Hz, got {sample_rate_int} Hz")
        except (ValueError, TypeError):
            pass
    
    # 检查音频比特率（如果存在，允许一定误差）
    bit_rate = metadata.get("bit_rate")
    if bit_rate:
        try:
            bit_rate_int = int(bit_rate)
            # 256 kbps = 256000 bps，允许 ±5% 误差
            expected_min = 256000 * 0.95
            expected_max = 256000 * 1.05
            if not (expected_min <= bit_rate_int <= expected_max):
                errors.append(f"Audio bit rate mismatch: expected ~256000 bps, got {bit_rate_int} bps")
        except (ValueError, TypeError):
            pass
    
    if errors:
        error_msg = "; ".join(errors)
        log_error(f"Render output validation failed: {error_msg}")
        raise RuntimeError(f"Render output does not meet McPOS global standards: {error_msg}")


async def run_render_for_episode(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    """
    运行视频渲染
    
    Interface Contract: async def run_render_for_episode(spec: EpisodeSpec, paths: AssetPaths) -> StageResult
    
    按照文档标准实现：
    - 使用 Unified Pre-Mix Architecture：直接使用 final_mix.mp3（256kbps CBR, 48kHz, 16-bit）
    - 使用封面图片和预混音音频生成 4K 视频（3840×2160）
    - 使用与旧世界相同的视频编码参数和滤镜
    - 完全依赖 Premix：不触碰 playlist、Timeline、SFX 或混音参数
    
    输出文件：
    - paths.youtube_mp4 (<episode_id>_youtube.mp4, 4K)
    - paths.render_complete_flag (<episode_id>_render_complete.flag)
    
    参考旧世界实现：
    - kat_rec_web/backend/t2r/utils/direct_video_render.py
    - kat_rec_web/backend/t2r/utils/video_render_config.py
    """
    started_at = datetime.now()
    
    try:
        # 幂等性检查：如果两个文件都已存在，跳过生成
        if paths.youtube_mp4.exists() and paths.render_complete_flag.exists():
            log_info(f"Render already complete for {spec.episode_id}, skipping")
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            
            return StageResult(
                stage=StageName.RENDER,
                success=True,
                duration_seconds=duration,
                key_asset_paths=[paths.youtube_mp4, paths.render_complete_flag],
                started_at=started_at,
                finished_at=finished_at,
            )
        
        # 确保输出目录存在
        paths.episode_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查必需输入文件
        if not paths.cover_png.exists():
            raise FileNotFoundError(
                f"cover.png not found at {paths.cover_png}. Run COVER stage first."
            )
        if not paths.final_mix_mp3.exists():
            raise FileNotFoundError(
                f"final_mix.mp3 not found at {paths.final_mix_mp3}. Run MIX stage first."
            )
        
        # 改进的日志：输出核心输入输出信息
        log_info(
            f"Render episode {spec.episode_id} with "
            f"cover={paths.cover_png.name} "
            f"audio={paths.final_mix_mp3.name} -> "
            f"video={paths.youtube_mp4.name}"
        )
        
        # 根据频道选择渲染函数
        config = get_config()
        
        if spec.channel_id == "rbr":
            # RBR 频道使用独立的渲染引擎
            if render_rbr_episode_video is None:
                raise RuntimeError(
                    f"RBR render engine not available. "
                    f"Please implement mcpos/adapters/rbr_render_engine.py"
                )
            log_info(f"Using RBR-specific render engine for {spec.episode_id}")
            render_result = await render_rbr_episode_video(
                spec=spec,
                paths=paths,
                cfg=config,
                dry_run=False,
            )
        else:
            # Kat 频道使用默认渲染引擎（静态图片循环）
            log_info(f"Using Kat render engine for {spec.episode_id}")
            render_result = await render_episode_video(
                spec=spec,
                paths=paths,
                cfg=config,
                dry_run=False,
            )
        
        # 第一层检查：render_result 的返回状态（软判断）
        if isinstance(render_result, RenderResult):
            # RenderResult 没有 success 字段，但可以通过检查是否有 error_message 来判断
            # 如果 render_episode_video 抛出异常，这里不会执行到这里
            # 所以这里主要检查返回的对象是否有效
            if not hasattr(render_result, "video_path") or not render_result.video_path:
                raise RuntimeError("render_episode_video returned invalid result: missing video_path")
        
        # 第二层检查：文件存在性（硬判断）
        mp4_exists = paths.youtube_mp4.exists()
        flag_exists = paths.render_complete_flag.exists()
        
        if not mp4_exists and not flag_exists:
            raise FileNotFoundError(
                f"Render failed: neither video file nor flag file was generated. "
                f"video={paths.youtube_mp4}, flag={paths.render_complete_flag}"
            )
        elif not mp4_exists:
            raise FileNotFoundError(
                f"Render incomplete: flag file exists but video file missing: {paths.youtube_mp4}"
            )
        elif not flag_exists:
            log_warning(
                f"Render partial: video file exists but flag file missing: {paths.render_complete_flag}. "
                f"Treating as failure."
            )
            raise FileNotFoundError(
                f"Render incomplete: video file exists but flag file missing: {paths.render_complete_flag}"
            )
        
        # 第三层检查：输出质量验证（契约断言）
        log_info(f"Validating render output: {paths.youtube_mp4}")
        _validate_render_output(paths.youtube_mp4)
        
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        
        log_info(f"✅ Render complete for {spec.episode_id} (duration: {duration:.1f}s)")
        
        return StageResult(
            stage=StageName.RENDER,
            success=True,
            duration_seconds=duration,
            key_asset_paths=[paths.youtube_mp4, paths.render_complete_flag],
            started_at=started_at,
            finished_at=finished_at,
        )
        
    except Exception as e:
        import traceback
        log_error(f"run_render_for_episode exception for {spec.episode_id}: {e}\n{traceback.format_exc()}")
        
        # 异常处理改进：对部分产物做说明式清理或日志
        mp4_exists = paths.youtube_mp4.exists()
        flag_exists = paths.render_complete_flag.exists()
        
        if mp4_exists and not flag_exists:
            log_warning(
                f"Partial render detected: MP4 exists but flag missing. "
                f"MP4 may be incomplete or corrupted. Manual cleanup may be required."
            )
        elif flag_exists and not mp4_exists:
            log_warning(
                f"Partial render detected: Flag exists but MP4 missing. "
                f"This is unusual. Manual cleanup may be required."
            )
        
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        
        return StageResult(
            stage=StageName.RENDER,
            success=False,
            duration_seconds=duration,
            key_asset_paths=[],
            error_message=str(e),
            started_at=started_at,
            finished_at=finished_at,
        )
