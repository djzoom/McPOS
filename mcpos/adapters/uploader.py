"""
Uploader Boundary

这是和 YouTube（或者任意平台）交互的唯一入口。
McPOS 的 pipeline 只知道"我叫你上传 / 验证"，不知道 HTTP 细节、OAuth、API 配额等。

实现策略：
- 通过 subprocess 调用旧世界上传脚本（Phase 1）
- 所有必需文件（video, title, description, tags）缺失时 hard fail
- 可选文件（subtitle, thumbnail）缺失时跳过，不影响上传
- 所有元数据从 AssetPaths 和 McPOSConfig 读取，符合 Truth Source Covenant
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional
from pathlib import Path
import subprocess
import asyncio
import os
import json
import re
import sys

from ..models import EpisodeSpec, AssetPaths
from ..config import McPOSConfig, get_config
from ..core.logging import log_info, log_warning, log_error
from .filesystem import move_image_to_used


UploadState = Literal["queued", "uploading", "uploaded", "failed"]
VerifyState = Literal["verifying", "verified", "failed"]


@dataclass
class UploadResult:
    """上传结果"""
    state: UploadState
    video_id: Optional[str]
    error: Optional[str] = None
    extra: dict[str, Any] | None = None


@dataclass
class VerifyResult:
    """验证结果"""
    state: VerifyState
    video_id: Optional[str]
    error: Optional[str] = None
    extra: dict[str, Any] | None = None


@dataclass
class _UploadParams:
    """
    内部上传参数（不对外暴露）
    
    封装所有上传所需的参数，从 EpisodeSpec, AssetPaths, McPOSConfig 构建。
    """
    # 必需参数
    video_file: Path
    episode_id: str
    channel_id: str
    
    # 元数据（从文件读取，必需）
    title: str
    description: str
    tags: list[str]
    
    # 可选文件
    subtitle_path: Optional[Path] = None
    thumbnail_path: Optional[Path] = None
    
    # YouTube 配置
    privacy_status: str = "unlisted"
    category_id: int = 10
    playlist_id: Optional[str] = None
    default_language: str = "en"
    max_retries: int = 5
    schedule: bool = False
    
    # OAuth 配置
    client_secrets_file: Optional[Path] = None
    token_file: Optional[Path] = None


def _probe_video_asset(video_path: Path, cfg: Optional[McPOSConfig] = None) -> tuple[bool, Optional[str]]:
    """
    使用 ffprobe 对视频文件进行严格检测。
    
    校验内容:
    - ffprobe 能正常读取
    - 存在 video 流和 audio 流
    - duration > 0.01 (允许极短测试资源，但拒绝空文件)
    - size > 0 (以 ffprobe format.size 为准)
    
    Args:
        video_path: 视频文件路径
        cfg: McPOS 配置（可选，用于调试输出）
    
    Returns:
        (是否通过, 错误信息)
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-hide_banner",
                "-show_streams",
                "-show_format",
                "-of", "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        error_msg = "ffprobe not found in PATH"
        log_warning(
            f"[upload] {error_msg}. Please install ffmpeg/ffprobe or add to PATH. "
            f"File: {video_path}"
        )
        return False, error_msg
    except subprocess.TimeoutExpired:
        return False, "ffprobe timed out"

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        return False, stderr or "ffprobe returned non zero exit code"

    try:
        info = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as e:
        return False, f"ffprobe returned invalid JSON: {e}"

    # 可选：保存 ffprobe JSON 到调试文件（如果配置了 debug 模式）
    if cfg and hasattr(cfg, 'debug_ffprobe') and cfg.debug_ffprobe:
        debug_file = video_path.parent / f"{video_path.stem}_ffprobe_debug.json"
        try:
            debug_file.write_text(
                json.dumps(info, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            log_info(f"[upload] Saved ffprobe debug output to: {debug_file}")
        except Exception as e:
            log_warning(f"[upload] Failed to save ffprobe debug output: {e}")

    streams = info.get("streams") or []
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    fmt = info.get("format") or {}
    try:
        duration = float(fmt.get("duration", 0) or 0)
    except (TypeError, ValueError):
        duration = 0.0
    try:
        size = int(fmt.get("size", 0) or 0)
    except (TypeError, ValueError):
        size = 0

    if not has_video:
        return False, "no video stream found in file"
    if not has_audio:
        return False, "no audio stream found in file"
    # 允许极短测试资源（>= 0.01 秒），但拒绝空文件或异常小的文件
    if duration <= 0.01:
        return False, f"duration too small or non-positive reported by ffprobe: {duration} seconds"
    if size <= 0:
        return False, "ffprobe reported zero sized file"

    return True, None


def _ensure_video_asset_ok(spec: EpisodeSpec, paths: AssetPaths, cfg: Optional[McPOSConfig] = None) -> Optional[str]:
    """
    严格前置检查: 确认渲染产物存在且通过 ffprobe 检测。
    
    返回:
        None: 通过检查
        str: 错误信息, 未通过检查
    """
    video_path = paths.youtube_mp4

    if not video_path.exists():
        msg = f"[upload] 渲染视频不存在: {video_path}"
        log_error(msg + f" (episode={spec.episode_id}, channel={spec.channel_id})")
        return msg

    fs_size = video_path.stat().st_size
    if fs_size <= 0:
        msg = f"[upload] 渲染视频大小为 0: {video_path}"
        log_error(msg + f" (episode={spec.episode_id}, channel={spec.channel_id})")
        return msg

    log_info(
        f"[upload] 文件系统检查通过, size={fs_size} bytes, "
        f"即将使用 ffprobe 进行深入校验 "
        f"(episode={spec.episode_id}, channel={spec.channel_id})"
    )

    ok, probe_error = _probe_video_asset(video_path, cfg)
    if not ok:
        msg = f"[upload] ffprobe 校验失败: {probe_error or 'unknown error'}"
        log_error(
            msg + f" (episode={spec.episode_id}, channel={spec.channel_id}, file={video_path})"
        )
        return msg

    log_info(
        f"[upload] ffprobe 校验通过: {video_path} "
        f"(episode={spec.episode_id}, channel={spec.channel_id})"
    )
    return None


def _finalize_cover_source_after_upload(spec: EpisodeSpec, paths: AssetPaths) -> None:
    """
    New workflow: only mark a cover as "used" AFTER a successful upload.

    Plan stage writes `cover_source_filename` in recipe.json to identify the original
    filename in images_pool/available. After upload, we move that file to images_pool/used.
    """
    recipe_path = paths.recipe_json
    if not recipe_path.exists():
        log_warning(f"[upload] recipe.json missing; cannot finalize cover usage (episode={spec.episode_id})")
        return

    try:
        payload = json.loads(recipe_path.read_text(encoding="utf-8"))
    except Exception as e:
        log_warning(f"[upload] Failed to read recipe.json; cannot finalize cover usage: {e} (episode={spec.episode_id})")
        return

    source_name = (
        payload.get("cover_source_filename")
        or payload.get("cover_image_source_filename")
        or payload.get("cover_image_original_filename")
    )
    if not source_name or not isinstance(source_name, str) or not source_name.strip():
        # Legacy episodes may not have this field; do nothing.
        return

    source_name = source_name.strip()
    cfg = get_config()

    # If already moved by older workflow, treat as success.
    if (cfg.images_pool_used / source_name).exists():
        log_info(f"[upload] Cover source already in used pool: {source_name} (episode={spec.episode_id})")
        return

    moved = move_image_to_used(source_name)
    if moved:
        log_info(f"[upload] Moved cover source to used pool: {source_name} (episode={spec.episode_id})")
        return

    if (cfg.images_pool_available / source_name).exists():
        log_warning(
            f"[upload] Failed to move cover source to used pool (still in available): {source_name} "
            f"(episode={spec.episode_id})"
        )
    else:
        log_warning(
            f"[upload] Cover source file not found in available/used; nothing moved: {source_name} "
            f"(episode={spec.episode_id})"
        )


def _build_upload_params(
    spec: EpisodeSpec,
    paths: AssetPaths,
    cfg: McPOSConfig,
) -> tuple[_UploadParams, Optional[str]]:
    """
    从 EpisodeSpec, AssetPaths, McPOSConfig 构建上传参数。
    
    参数读取规则：
    1. **必需文件**（TEXT_BASE 阶段承诺产出）：缺失时返回错误，不继续执行
    2. **可选文件**：缺失时设为 None，不影响上传
    3. **配置参数**：从 McPOSConfig 读取，有默认值
    
    Returns:
        (_UploadParams, error_message)
        - 如果成功：返回 (params, None)
        - 如果失败：返回 (None, error_message)
    """
    # 验证必需文件（TEXT_BASE 阶段承诺产出）
    if not paths.youtube_title_txt.exists():
        return None, f"Required asset missing: {paths.youtube_title_txt}. TEXT_BASE stage must complete before upload."
    
    title = paths.youtube_title_txt.read_text(encoding="utf-8").strip()
    if not title:
        return None, f"Title file is empty: {paths.youtube_title_txt}"
    
    if not paths.youtube_description_txt.exists():
        return None, f"Required asset missing: {paths.youtube_description_txt}. TEXT_BASE stage must complete before upload."
    
    description = paths.youtube_description_txt.read_text(encoding="utf-8").strip()
    # 注意：描述内容可以为空字符串（YouTube 允许），但如果文件不存在就是 TEXT_BASE 阶段不完整
    
    if not paths.youtube_tags_txt.exists():
        return None, f"Required asset missing: {paths.youtube_tags_txt}. TEXT_BASE stage must complete before upload."
    
    tags = [
        line.strip() 
        for line in paths.youtube_tags_txt.read_text(encoding="utf-8").splitlines() 
        if line.strip()
    ]
    if not tags:
        return None, f"Tags file is empty: {paths.youtube_tags_txt}"
    
    # 字幕文件是必需的（用于上传字幕）
    if not paths.youtube_srt.exists():
        return None, f"Required asset missing: {paths.youtube_srt}. TEXT_SRT stage must complete before upload."
    subtitle_path = paths.youtube_srt
    
    # 缩略图可选（缺失时跳过，旧世界脚本会自动处理大小）
    thumbnail_path = paths.cover_png if paths.cover_png.exists() else None
    
    # 从配置读取（配置可以有默认值）
    # 注意：默认 privacy_status 应该是 "private"（配合排播使用）
    privacy_status = cfg.youtube_privacy_status or "private"
    # 如果配置是 "unlisted"，但我们需要排播，强制改为 "private"
    if privacy_status == "unlisted":
        privacy_status = "private"
    
    category_id = cfg.youtube_category_id or 10
    playlist_id = cfg.youtube_playlist_id
    # 默认语言必须为 "en"，字幕上传需要（先设置视频默认语言为 English，再上传字幕）
    default_language = cfg.youtube_default_language or "en"
    if default_language != "en":
        log_warning(
            f"[upload] YouTube default language is set to '{default_language}', "
            f"but 'en' is required for subtitle upload. Overriding to 'en'."
        )
        default_language = "en"
    max_retries = cfg.youtube_max_retries or 5
    # 默认启用排播（因为默认 privacy_status 是 "private"）
    schedule = cfg.youtube_schedule if cfg.youtube_schedule is not None else True
    
    # OAuth 配置
    client_secrets_file = cfg.youtube_client_secrets_file
    token_file = cfg.youtube_token_file
    
    params = _UploadParams(
        video_file=paths.youtube_mp4,
        episode_id=spec.episode_id,
        channel_id=spec.channel_id,
        title=title,
        description=description,
        tags=tags,
        subtitle_path=subtitle_path,
        thumbnail_path=thumbnail_path,
        privacy_status=privacy_status,
        category_id=category_id,
        playlist_id=playlist_id,
        default_language=default_language,
        max_retries=max_retries,
        schedule=schedule,
        client_secrets_file=client_secrets_file,
        token_file=token_file,
    )
    
    return params, None


def _parse_upload_result_from_script_output(
    stdout: str,
    stderr: str,
    returncode: int,
    episode_id: str,
    repo_root: Path,
    channel_id: str,
) -> tuple[Optional[str], Optional[str]]:
    """
    从旧世界上传脚本的输出中解析 video_id 和错误信息。
    
    Args:
        stdout: 脚本的标准输出
        stderr: 脚本的标准错误
        returncode: 脚本的返回码
        episode_id: 期数 ID（用于日志）
        repo_root: 仓库根目录
        channel_id: 频道 ID
    
    Returns:
        (video_id, error_message)
        - 如果成功：返回 (video_id, None)
        - 如果失败：返回 (None, error_message)
    """
    if returncode != 0:
        error_msg = stderr.strip() or stdout.strip() or f"Upload script failed with return code {returncode}"
        log_error(f"[upload] Upload script failed: {error_msg} (episode={episode_id})")
        return None, error_msg
    
    # 尝试从 JSON 输出解析
    try:
        # 脚本可能输出 JSON 格式的结果
        json_match = re.search(r'\{[^{}]*"video_id"[^{}]*\}', stdout, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            video_id = result.get("video_id") or result.get("videoId")
            if video_id:
                return video_id, None
    except (json.JSONDecodeError, KeyError):
        pass
    
    # 尝试从文本输出解析 video_id（格式：Video ID: xxxxx）
    video_id_match = re.search(r'Video ID:\s*([a-zA-Z0-9_-]+)', stdout, re.IGNORECASE)
    if video_id_match:
        video_id = video_id_match.group(1)
        log_info(f"[upload] Parsed video_id from output: {video_id} (episode={episode_id})")
        return video_id, None
    
    # 尝试从 URL 解析 video_id
    url_match = re.search(r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)', stdout, re.IGNORECASE)
    if url_match:
        video_id = url_match.group(1)
        log_info(f"[upload] Parsed video_id from URL: {video_id} (episode={episode_id})")
        return video_id, None
    
    # 尝试查找上传结果 JSON 文件
    upload_result_file = repo_root / "channels" / channel_id / "output" / episode_id / f"{episode_id}_youtube_upload.json"
    if upload_result_file.exists():
        try:
            result_data = json.loads(upload_result_file.read_text(encoding="utf-8"))
            video_id = result_data.get("video_id")
            if video_id:
                log_info(f"[upload] Found video_id in upload result file: {video_id} (episode={episode_id})")
                return video_id, None
        except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
            log_warning(f"[upload] Failed to read upload result file: {e} (episode={episode_id})")
    
    # 如果无法解析，返回错误
    error_msg = f"Could not parse video_id from upload script output. stdout: {stdout[:200]}"
    log_error(f"[upload] {error_msg} (episode={episode_id})")
    return None, error_msg


async def upload_episode_video(
    spec: EpisodeSpec,
    paths: AssetPaths,
    cfg: McPOSConfig,
) -> UploadResult:
    """
    上传渲染后的视频边界函数。
    
    实现方式（Phase 1）：
    - 通过 subprocess 调用旧世界上传脚本
    - 所有必需文件（video, title, description, tags）缺失时 hard fail
    - 可选文件（subtitle, thumbnail）缺失时跳过，不影响上传
    
    必需文件：
    - video_file (paths.youtube_mp4): 必须存在且通过 ffprobe 校验
    - title (paths.youtube_title_txt): 必须存在且非空
    - description (paths.youtube_description_txt): 必须存在（内容可以为空）
    - tags (paths.youtube_tags_txt): 必须存在且非空
    - subtitle (paths.youtube_srt): 必须存在（用于上传字幕）
    
    可选文件：
    - thumbnail (paths.cover_png): 缺失时跳过缩略图上传（旧世界脚本会自动调整大小：最大 1280x720 像素，最大 2MB）
    
    配置要求：
    - default_language: 强制设置为 "en"（字幕上传需要，先设置视频默认语言为 English，再上传字幕）
    - playlist_id: 从 config.yaml 自动读取（默认：PLAn_Q-OQCpRLeHEWW4gf9EjZyTiwCfcaH）
    """
    log_info(
        f"[upload] Starting upload for episode={spec.episode_id}, "
        f"channel={spec.channel_id}, video={paths.youtube_mp4}"
    )
    
    # 1. 前置检查：视频文件存在且通过 ffprobe 校验
    precheck_error = _ensure_video_asset_ok(spec, paths, cfg)
    if precheck_error is not None:
        return UploadResult(
            state="failed",
            video_id=None,
            error=precheck_error,
            extra={
                "impl": "precheck",
                "note": "video missing, invalid, or ffprobe check failed; upload skipped",
            },
        )
    
    # 2. 构建上传参数（必需文件缺失时会返回错误）
    params, error = _build_upload_params(spec, paths, cfg)
    if error:
        log_error(f"[upload] Failed to build upload params: {error} (episode={spec.episode_id})")
        return UploadResult(state="failed", video_id=None, error=error)
    
    log_info(
        f"[upload] Upload params built successfully. "
        f"title={params.title[:50]}..., tags={len(params.tags)}, "
        f"subtitle={'yes' if params.subtitle_path else 'no'}, "
        f"thumbnail={'yes' if params.thumbnail_path else 'no'}, "
        f"playlist_id={params.playlist_id or 'none'}, "
        f"default_language={params.default_language} "
        f"(episode={spec.episode_id})"
    )
    
    # 3. 调用旧世界上传脚本
    upload_script = cfg.repo_root / "scripts" / "uploader" / "upload_to_youtube.py"
    if not upload_script.exists():
        error_msg = f"Upload script not found: {upload_script}"
        log_error(f"[upload] {error_msg} (episode={spec.episode_id})")
        return UploadResult(
            state="failed",
            video_id=None,
            error=error_msg,
            extra={"impl": "script_missing"},
        )
    
    # 构建命令行参数
    # 显式传入元数据文件路径，锁定 McPOS 控制权，跳过旧脚本的自动探测逻辑
    # 统一使用完整 episode_id（例如 kat_YYYYMMDD），避免日志/标记文件出现双格式
    episode_id_for_script = spec.episode_id
    
    cmd = [
        sys.executable,
        str(upload_script),
        "--episode", episode_id_for_script,
        "--video", str(params.video_file),
        "--title-file", str(paths.youtube_title_txt),
        "--desc-file", str(paths.youtube_description_txt),
    ]
    
    # 添加可选参数
    if params.subtitle_path:
        # 脚本会自动检测字幕文件，但我们可以显式指定
        pass  # 脚本会从 episode 目录自动查找
    
    if params.privacy_status:
        cmd.extend(["--privacy", params.privacy_status])
    
    if params.schedule:
        cmd.extend(["--schedule"])
    
    log_info(f"[upload] Executing upload script: {' '.join(cmd)} (episode={spec.episode_id})")
    
    try:
        # 设置环境变量，确保旧脚本能找到 src 模块
        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "")
        repo_root_str = str(cfg.repo_root)
        if pythonpath:
            env["PYTHONPATH"] = f"{repo_root_str}:{pythonpath}"
        else:
            env["PYTHONPATH"] = repo_root_str
        
        # 使用 async subprocess 执行上传脚本
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cfg.repo_root),
            env=env,
        )
        
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=3600,  # 1 小时超时（大文件上传可能需要较长时间）
        )
        
        raw_out = stdout_bytes.decode("utf-8", errors="replace").strip()
        raw_err = stderr_bytes.decode("utf-8", errors="replace").strip()
        
        if proc.returncode != 0:
            log_error(
                f"[upload] Upload script exited with code {proc.returncode} (episode={spec.episode_id})"
            )
            log_error(
                f"[upload] stderr: {raw_err[-2000:] if raw_err else '(empty)'} (episode={spec.episode_id})"
            )
            return UploadResult(
                state="failed",
                video_id=None,
                error=f"upload script failed with code {proc.returncode}",
                extra={
                    "impl": "subprocess",
                    "returncode": proc.returncode,
                    "stdout": raw_out[-2000:] if raw_out else None,
                    "stderr": raw_err[-2000:] if raw_err else None,
                },
            )
        
        # 解析脚本输出中的 JSON 结果
        # 旧脚本会在最后一行输出 JSON: {"event": "upload", "status": "completed", "video_id": "...", ...}
        video_id = None
        video_url = None
        duration_seconds = None
        uploaded_at = None
        
        try:
            # 尝试从最后一行解析 JSON（旧脚本输出格式）
            lines = raw_out.splitlines()
            for line in reversed(lines):
                line = line.strip()
                if line.startswith("{") and "video_id" in line:
                    try:
                        payload = json.loads(line)
                        video_id = payload.get("video_id")
                        video_url = payload.get("video_url") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else None)
                        duration_seconds = payload.get("duration_seconds") or payload.get("latency")
                        uploaded_at = payload.get("upload_time") or payload.get("uploaded_at")
                        break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            log_warning(f"[upload] Failed to parse JSON from stdout, trying fallback parser: {e} (episode={spec.episode_id})")
            # 如果直接解析失败，使用原有的解析函数作为后备
            video_id, parse_error = _parse_upload_result_from_script_output(
                raw_out,
                raw_err,
                proc.returncode,
                spec.episode_id,
                cfg.repo_root,
                spec.channel_id,
            )
            if video_id:
                video_url = f"https://www.youtube.com/watch?v={video_id}"
            else:
                error_msg = parse_error or "Failed to parse video_id from upload script output"
                log_error(f"[upload] Upload failed: {error_msg} (episode={spec.episode_id})")
                return UploadResult(
                    state="failed",
                    video_id=None,
                    error=error_msg,
                    extra={
                        "impl": "subprocess",
                        "returncode": proc.returncode,
                        "stdout": raw_out[-2000:] if raw_out else None,
                        "stderr": raw_err[-2000:] if raw_err else None,
                    },
                )

        if not video_id:
            error_msg = "upload script did not return video_id"
            log_error(f"[upload] {error_msg} (episode={spec.episode_id})")
            return UploadResult(
                state="failed",
                video_id=None,
                error=error_msg,
                extra={
                    "impl": "subprocess",
                    "returncode": proc.returncode,
                    "stdout": raw_out[-2000:] if raw_out else None,
                    "stderr": raw_err[-2000:] if raw_err else None,
                },
            )
        
        if not video_url:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        log_info(
            f"[upload] Upload successful. video_id={video_id}, "
            f"video_url={video_url} (episode={spec.episode_id})"
        )
        
        # McPOS v1 状态管理：写入 JSON 真相文件和 flag 文件
        # 1. 写入上传结果 JSON（McPOS 的单一真相源）
        upload_json_path = paths.episode_output_dir / f"{spec.episode_id}_youtube_upload.json"
        upload_result_data = {
            "episode_id": spec.episode_id,
            "channel_id": spec.channel_id,
            "video_id": video_id,
            "video_url": video_url,
            "status": "completed",
            "uploaded_at": uploaded_at,
            "duration_seconds": duration_seconds,
        }
        
        try:
            upload_json_path.parent.mkdir(parents=True, exist_ok=True)
            upload_json_path.write_text(
                json.dumps(upload_result_data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            log_info(f"[upload] Wrote upload result JSON to {upload_json_path} (episode={spec.episode_id})")
        except Exception as e:
            log_warning(f"[upload] Failed to write upload result JSON: {e} (episode={spec.episode_id})")
        
        # 2. Touch flag 文件（用于批处理脚本判断上传完成）
        try:
            paths.upload_complete_flag.parent.mkdir(parents=True, exist_ok=True)
            paths.upload_complete_flag.touch(exist_ok=True)
            log_info(f"[upload] Created upload complete flag: {paths.upload_complete_flag} (episode={spec.episode_id})")
        except Exception as e:
            log_warning(f"[upload] Failed to create upload flag: {e} (episode={spec.episode_id})")

        # 3) Plan-stage compatibility: only now mark the cover as used.
        _finalize_cover_source_after_upload(spec, paths)

        # 3. 结构化日志（包含 episode_id, video_id, duration, error）
        log_info(
            f"[upload] Upload completed: episode={spec.episode_id}, "
            f"video_id={video_id}, video_url={video_url}, "
            f"duration_seconds={duration_seconds or 'unknown'}, error=None"
        )
        
        return UploadResult(
            state="uploaded",
            video_id=video_id,
            error=None,
            extra={
                "impl": "subprocess",
                "video_url": video_url,
                "upload_json_path": str(upload_json_path),
                "upload_flag_path": str(paths.upload_complete_flag),
            },
        )
    
    except asyncio.TimeoutError:
        error_msg = "Upload script timed out after 1 hour"
        log_error(f"[upload] {error_msg} (episode={spec.episode_id})")
        return UploadResult(
            state="failed",
            video_id=None,
            error=error_msg,
            extra={"impl": "subprocess", "timeout": True},
        )
    
    except Exception as e:
        error_msg = f"Unexpected error during upload: {e}"
        log_error(f"[upload] {error_msg} (episode={spec.episode_id})")
        return UploadResult(
            state="failed",
            video_id=None,
            error=error_msg,
            extra={"impl": "subprocess", "exception_type": type(e).__name__},
        )


async def verify_episode_upload(
    spec: EpisodeSpec,
    cfg: McPOSConfig,
    video_id: Optional[str],
) -> VerifyResult:
    """
    验证已上传视频的边界函数。
    
    当前实现（Phase 1）：
    - 不调用任何外部 API
    - 始终返回 verified
    - 日志中清晰标注 stub 状态
    
    未来真实实现：
    - 在这里检查平台上的视频状态, 决定 verified / failed
    - 通过 YouTube API 查询视频状态
    """
    if video_id:
        log_info(
            f"[verify] Stub verifier: 收到 video_id={video_id}, "
            f"episode={spec.episode_id}, channel={spec.channel_id}"
        )
    else:
        log_warning(
            f"[verify] Stub verifier: 未提供 video_id, 仍将标记为 verified "
            f"(episode={spec.episode_id}, channel={spec.channel_id})"
        )

    log_warning(
        "[verify] Stub verifier active: 未配置真实验证实现, "
        "当前直接标记为 verified, 不会调用外部平台 API"
    )

    return VerifyResult(
        state="verified",
        video_id=video_id,
        error=None,
        extra={
            "impl": "stub",
            "note": "no real verification performed; assumed verified",
        },
    )
