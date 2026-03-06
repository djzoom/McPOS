#!/usr/bin/env python3
# coding: utf-8
"""
上传辅助函数

将 upload_video() 拆分为更小的、可测试的函数
"""
from __future__ import annotations

import time
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import subprocess

try:
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False


class UploadError(Exception):
    pass


class TransientError(Exception):
    pass


@dataclass
class UploadConfig:
    """YouTube 上传配置（精简版，独立于旧世界）"""
    video_file: Path
    title: str
    description: str
    privacy_status: str = "unlisted"
    category_id: int = 10
    tags: List[str] = field(default_factory=lambda: ["lofi", "music", "Kat Records", "chill"])
    subtitle_path: Optional[Path] = None
    thumbnail_path: Optional[Path] = None
    episode_id: Optional[str] = None
    max_retries: int = 5
    schedule: bool = False
    default_language: str = "en"
    playlist_id: Optional[str] = None
    publish_at: Optional[str] = None  # RFC3339

    def __post_init__(self) -> None:
        if not self.video_file.exists():
            raise UploadError(f"Video file not found: {self.video_file}")
        if not self.title:
            self.title = f"Kat Records Lo-Fi Mix - {self.episode_id or 'Unknown'}"
        if not self.description:
            self.description = "Kat Records - Lo-Fi Radio Mix"
        if self.category_id is None:
            self.category_id = 10
        if self.max_retries is None:
            self.max_retries = 5
        if not self.privacy_status:
            self.privacy_status = "unlisted"
        if self.publish_at and self.privacy_status != "private":
            self.privacy_status = "private"
        if not self.default_language:
            self.default_language = "en"
        if not self.tags:
            self.tags = ["lofi", "music", "Kat Records", "chill"]

# Import functions from upload_to_youtube (lazy import to avoid circular dependency)
def _get_build_metadata():
    import sys
    from pathlib import Path
    REPO_ROOT = Path(__file__).resolve().parent.parent.parent
    if str(REPO_ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from scripts.uploader.upload_to_youtube import build_youtube_metadata
    return build_youtube_metadata

def _get_resize_thumbnail():
    import sys
    from pathlib import Path
    REPO_ROOT = Path(__file__).resolve().parent.parent.parent
    if str(REPO_ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from scripts.uploader.upload_to_youtube import resize_thumbnail_if_needed
    return resize_thumbnail_if_needed

def _get_add_to_playlist():
    import sys
    from pathlib import Path
    REPO_ROOT = Path(__file__).resolve().parent.parent.parent
    if str(REPO_ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from scripts.uploader.upload_to_youtube import add_video_to_playlist
    return add_video_to_playlist

STATE_MANAGEMENT_AVAILABLE = False
get_logger = None


def prepare_body(upload_config: UploadConfig) -> Dict[str, Any]:
    """
    准备 YouTube 上传元数据
    
    Args:
        upload_config: 上传配置
        
    Returns:
        YouTube API 元数据字典
    """
    # 确保关键参数不是 None（最后一道防线）
    category_id = upload_config.category_id if upload_config.category_id is not None else 10
    privacy_status = upload_config.privacy_status or "private"
    default_language = upload_config.default_language or "en"
    tags = upload_config.tags or ["lofi", "music", "Kat Records", "chill"]
    
    build_youtube_metadata = _get_build_metadata()
    return build_youtube_metadata(
        episode_id=upload_config.episode_id or "",
        title=upload_config.title,
        description=upload_config.description,
        privacy=privacy_status,
        tags=tags,
        category_id=category_id,
        schedule=upload_config.schedule,
        default_language=default_language,
        publish_at=upload_config.publish_at,
    )


def _probe_video_duration(video_file: Path, timeout: int = 10) -> Tuple[bool, Optional[float], Optional[str]]:
    """
    Use ffprobe to validate video duration and basic readability.
    Returns (ok, duration_seconds, error_msg).
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-hide_banner",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_file),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return False, None, "ffprobe not found in PATH"
    except subprocess.TimeoutExpired:
        return False, None, "ffprobe timed out"

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        return False, None, stderr or "ffprobe returned non-zero exit code"

    raw = (result.stdout or "").strip()
    if not raw:
        return False, None, "ffprobe returned empty duration"

    try:
        duration = float(raw)
    except ValueError:
        return False, None, f"invalid duration value: {raw}"

    if duration <= 0:
        return False, duration, "duration is non-positive"

    return True, duration, None


def validate_video_asset(video_file: Path, episode_id: Optional[str] = None) -> None:
    """
    Strict preflight validation for upload video assets.
    Raises UploadError on failure.
    """
    if not video_file.exists():
        raise UploadError(f"Video file missing: {video_file}")
    if not video_file.is_file():
        raise UploadError(f"Video path is not a file: {video_file}")
    try:
        file_size = video_file.stat().st_size
    except OSError as e:
        raise UploadError(f"Failed to stat video file {video_file}: {e}")
    if file_size <= 0:
        raise UploadError(f"Video file size is 0 bytes: {video_file}")

    ok, duration, error = _probe_video_duration(video_file)
    if not ok:
        raise UploadError(
            f"Video duration validation failed: {error or 'unknown error'} "
            f"(file={video_file}, episode={episode_id or 'unknown'})"
        )
    _ = duration


def resumable_upload(
    youtube: Any,
    upload_config: UploadConfig,
    body: Dict[str, Any],
) -> str:
    """
    执行可恢复的视频上传
    
    Args:
        youtube: YouTube API 服务对象
        upload_config: 上传配置
        body: 元数据字典
        
    Returns:
        video_id: YouTube 视频 ID
        
    Raises:
        UploadError: 上传失败
        TransientError: 临时错误（可重试）
    """
    if not GOOGLE_API_AVAILABLE:
        raise UploadError("Google API libraries not installed")

    # 确保 max_retries 不是 None（最后一道防线）
    max_retries = upload_config.max_retries if upload_config.max_retries is not None else 5

    file_size = upload_config.video_file.stat().st_size
    # 确保 file_size 不是 None（防御性编程）
    if file_size is None:
        raise UploadError(f"Video file size is None: {upload_config.video_file}")
    
    # Create media upload (resumable for large files)
    # Google API 库不接受 chunksize=None，必须使用 -1（自动分块）或正整数
    # 对于大文件（>256MB）使用 -1 让库自动分块，对于小文件也使用 -1（库会自动处理）
    chunksize = -1  # 始终使用自动分块，让 Google API 库决定是否分块
    media = MediaFileUpload(str(upload_config.video_file), chunksize=chunksize, resumable=True)
    
    # Build part list
    parts: List[str] = ['snippet', 'status']
    if 'recordingDetails' in body:
        parts.append('recordingDetails')
    
    upload_request = youtube.videos().insert(
        part=','.join(parts),
        body=body,
        media_body=media
    )
    
    video_id: Optional[str] = None
    retry_count = 0
    start_time = time.time()
    
    while retry_count <= max_retries:
        try:
            status, response = upload_request.next_chunk()
            if response is not None:
                if 'id' in response:
                    video_id = response['id']
                    break
                else:
                    raise UploadError(f"Upload response missing video ID: {response}")
            
            # Progress feedback
            if status:
                progress = int(status.progress() * 100)
                if STATE_MANAGEMENT_AVAILABLE and get_logger:
                    logger = get_logger()
                    logger.debug(
                        "upload.progress",
                        f"Upload progress: {progress}%",
                        episode_id=upload_config.episode_id,
                        metadata={"progress": progress}
                    )
        
        except HttpError as e:
            error_content = e.content.decode('utf-8') if e.content else str(e)
            
            # Check quota exceeded
            if e.resp.status == 403 and 'quotaExceeded' in error_content:
                raise UploadError("API quota exceeded. Please try again tomorrow.")
            
            # Check authentication error
            if e.resp.status == 401:
                raise UploadError("Authentication failed. Please re-authorize.")
            
            # Retry on server errors
            if e.resp.status in [500, 502, 503, 504]:
                retry_count += 1
                if retry_count <= max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    time.sleep(wait_time)
                    continue
                else:
                    raise TransientError(f"Upload failed after {max_retries} retries: {error_content}")
            else:
                # Client errors, don't retry
                raise UploadError(f"Upload failed: {error_content}")
        
        except Exception as e:
            retry_count += 1
            if retry_count <= max_retries:
                wait_time = 2 ** retry_count
                time.sleep(wait_time)
                continue
            else:
                raise UploadError(f"Upload exception after {max_retries} retries: {e}")
    
    if not video_id:
        raise UploadError("Upload failed: No video ID returned")
    
    return video_id


def attach_subtitle(
    youtube: Any,
    video_id: str,
    subtitle_path: Optional[Path],
    episode_id: Optional[str] = None,
) -> None:
    """
    附加字幕到视频
    
    Args:
        youtube: YouTube API 服务对象
        video_id: YouTube 视频 ID
        subtitle_path: 字幕文件路径（可选）
        episode_id: 期数 ID（用于日志）
    """
    if not subtitle_path or not subtitle_path.exists():
        return
    
    try:
        # Detect language from file name or use default
        # 注意：由于视频默认语言是 'en'，字幕默认也应该是 'en'
        subtitle_lang = 'en'  # Default to English (matches video defaultLanguage)
        subtitle_name = 'English Subtitles'
        
        subtitle_str = str(subtitle_path)
        # 优先检测明确的语言标识
        if '_zh' in subtitle_str or '.zh' in subtitle_str:
            subtitle_lang = 'zh-CN'
            subtitle_name = 'Chinese Subtitles'
        elif '_ja' in subtitle_str or '.ja' in subtitle_str:
            subtitle_lang = 'ja'
            subtitle_name = 'Japanese Subtitles'
        elif '_en' in subtitle_str or '.en.' in subtitle_str:
            subtitle_lang = 'en'
            subtitle_name = 'English Subtitles'
        # 如果没有明确标识，默认使用英文（因为视频默认语言是 'en'）
        
        # ✅ 修复：先删除同语言的自动 caption（如果存在）
        # YouTube 会自动生成 caption，如果已存在同语言的 caption，上传会失败
        # 必须在上传前删除，否则会报错："A caption track with this language already exists"
        # 
        # 注意：删除 caption 需要 youtube.force-ssl scope（已在 SCOPES 中配置）
        deleted_count = 0
        deletion_errors = []
        
        try:
            print(f"[upload.subtitle] Checking for existing captions (lang={subtitle_lang})...", file=sys.stderr)
            # 获取所有现有的 caption
            captions_list = youtube.captions().list(part='snippet', videoId=video_id).execute()
            
            existing_captions = captions_list.get('items', [])
            print(f"[upload.subtitle] Found {len(existing_captions)} existing caption(s)", file=sys.stderr)
            
            # 查找同语言的 caption（包括自动生成的）
            for caption_item in existing_captions:
                caption_id = caption_item['id']
                caption_lang = caption_item['snippet'].get('language', '')
                caption_track_kind = caption_item['snippet'].get('trackKind', '')
                caption_name = caption_item['snippet'].get('name', '')
                
                print(f"[upload.subtitle] Found caption: id={caption_id}, lang={caption_lang}, kind={caption_track_kind}, name={caption_name}", file=sys.stderr)
                
                # 如果是同语言，删除它（包括自动生成的 'asr' 和手动上传的 'standard'）
                if caption_lang == subtitle_lang:
                    try:
                        print(f"[upload.subtitle] Deleting caption {caption_id} (lang={caption_lang}, kind={caption_track_kind})...", file=sys.stderr)
                        youtube.captions().delete(id=caption_id).execute()
                        deleted_count += 1
                        # 输出到 stderr（确保即使 logger 不可用也能看到）
                        print(f"[upload.subtitle] ✅ Deleted existing caption: {caption_id} (lang={caption_lang}, kind={caption_track_kind})", file=sys.stderr)
                        if STATE_MANAGEMENT_AVAILABLE and get_logger:
                            logger = get_logger()
                            logger.info(
                                "upload.subtitle.delete_existing",
                                f"Deleted existing caption: {caption_id} (lang={caption_lang}, kind={caption_track_kind})",
                                episode_id=episode_id,
                                metadata={"caption_id": caption_id, "language": caption_lang, "kind": caption_track_kind}
                            )
                    except HttpError as delete_error:
                        # HTTP 错误（权限、API 错误等）
                        error_details = delete_error.error_details if hasattr(delete_error, 'error_details') else []
                        error_reason = delete_error.reason if hasattr(delete_error, 'reason') else str(delete_error)
                        error_code = delete_error.resp.status if hasattr(delete_error, 'resp') else None
                        
                        error_msg = f"Failed to delete existing caption {caption_id}: HTTP {error_code} - {error_reason}"
                        if error_details:
                            error_msg += f" Details: {error_details}"
                        
                        print(f"[upload.subtitle] ❌ {error_msg}", file=sys.stderr)
                        deletion_errors.append(error_msg)
                        
                        if STATE_MANAGEMENT_AVAILABLE and get_logger:
                            logger = get_logger()
                            logger.warning(
                                "upload.subtitle.delete_failed",
                                error_msg,
                                episode_id=episode_id,
                                metadata={"caption_id": caption_id, "error_code": error_code, "error_reason": error_reason}
                            )
                    except Exception as delete_error:
                        # 其他错误（网络、超时等）
                        error_msg = f"Failed to delete existing caption {caption_id}: {type(delete_error).__name__}: {delete_error}"
                        print(f"[upload.subtitle] ⚠️  {error_msg}", file=sys.stderr)
                        deletion_errors.append(error_msg)
                        
                        if STATE_MANAGEMENT_AVAILABLE and get_logger:
                            logger = get_logger()
                            logger.warning(
                                "upload.subtitle.delete_failed",
                                error_msg,
                                episode_id=episode_id
                            )
        except HttpError as list_error:
            # HTTP 错误（权限、API 错误等）
            error_details = list_error.error_details if hasattr(list_error, 'error_details') else []
            error_reason = list_error.reason if hasattr(list_error, 'reason') else str(list_error)
            error_code = list_error.resp.status if hasattr(list_error, 'resp') else None
            
            error_msg = f"Failed to list existing captions: HTTP {error_code} - {error_reason}"
            if error_details:
                error_msg += f" Details: {error_details}"
            
            print(f"[upload.subtitle] ❌ {error_msg}", file=sys.stderr)
            print(f"[upload.subtitle] ⚠️  This may indicate missing OAuth scope 'youtube.force-ssl'", file=sys.stderr)
            
            if STATE_MANAGEMENT_AVAILABLE and get_logger:
                logger = get_logger()
                logger.warning(
                    "upload.subtitle.list_failed",
                    error_msg,
                    episode_id=episode_id,
                    metadata={"error_code": error_code, "error_reason": error_reason}
                )
        except Exception as list_error:
            # 其他错误（网络、超时等）
            error_msg = f"Failed to list existing captions: {type(list_error).__name__}: {list_error}"
            print(f"[upload.subtitle] ⚠️  {error_msg}", file=sys.stderr)
            
            if STATE_MANAGEMENT_AVAILABLE and get_logger:
                logger = get_logger()
                logger.warning(
                    "upload.subtitle.list_failed",
                    error_msg,
                    episode_id=episode_id
                )
        
        # 如果删除了 caption，等待一小段时间确保 YouTube API 同步
        if deleted_count > 0:
            print(f"[upload.subtitle] Deleted {deleted_count} existing caption(s), waiting 2s for API sync...", file=sys.stderr)
            time.sleep(2)  # 等待 2 秒，确保删除操作完成并同步
        elif deletion_errors:
            # 如果有删除错误，但仍然尝试上传（可能是权限问题，但上传可能仍然成功）
            print(f"[upload.subtitle] ⚠️  Had {len(deletion_errors)} deletion error(s), but will still attempt upload", file=sys.stderr)
        
        # Determine MIME type based on file extension
        mime_type = 'text/plain'  # Default for SRT
        if subtitle_path.suffix.lower() == '.srt':
            mime_type = 'text/srt'
        elif subtitle_path.suffix.lower() == '.vtt':
            mime_type = 'text/vtt'
        
        # 上传字幕，设置为默认语言（setAsDefaultLanguage=True）和非草稿（isDraftCaption=False）
        # 注意：YouTube API v3 的 captions().insert() 中，isDraftCaption 和 setAsDefaultLanguage 是查询参数
        caption_body = {
                'snippet': {
                    'videoId': video_id,
                    'language': subtitle_lang,
                    'name': subtitle_name
                }
        }
        
        # 上传字幕，设置为默认语言（setAsDefaultLanguage=True）和非草稿（isDraftCaption=False）
        # 注意：YouTube API v3 的 captions().insert() 中，isDraftCaption 和 setAsDefaultLanguage 是查询参数
        # 必须通过关键字参数传递，而不是设置属性
        if subtitle_lang == 'en':
            # 英文字幕：设置为默认语言和非草稿
            caption_response = youtube.captions().insert(
                part='snippet',
                body=caption_body,
                media_body=MediaFileUpload(str(subtitle_path), mimetype=mime_type),
                isDraftCaption=False,  # 非草稿，立即生效
                setAsDefaultLanguage=True  # 设置为默认语言
            ).execute()
        else:
            # 其他语言：只设置为非草稿
            caption_response = youtube.captions().insert(
                part='snippet',
                body=caption_body,
                media_body=MediaFileUpload(str(subtitle_path), mimetype=mime_type),
                isDraftCaption=False  # 非草稿，立即生效
        ).execute()
        
        # 如果上传的是英文字幕，还需要通过 videos().update() 确保视频的 defaultLanguage 设置为 'en'
        # 这在上传视频时已经通过 build_youtube_metadata() 设置了 defaultLanguage='en'
        # 但为了确保，我们可以在上传字幕后再次确认
        
        # Log success
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.info(
                "upload.subtitle.success",
                f"Subtitle uploaded: {subtitle_name} ({subtitle_lang})",
                episode_id=episode_id,
                metadata={"language": subtitle_lang, "name": subtitle_name}
            )
    except Exception as e:
        # ✅ 增强错误处理：检查是否是"已存在"错误
        error_str = str(e)
        error_type = type(e).__name__
        
        # 检查是否是"caption already exists"错误
        if "already exists" in error_str.lower() or "duplicate" in error_str.lower():
            # 这是关键错误：字幕已存在，但我们的删除逻辑可能失败了
            error_msg = f"Subtitle upload failed: Caption with language '{subtitle_lang}' already exists. " \
                       f"This may indicate that the delete operation failed or the caption was recreated. " \
                       f"Error: {error_str}"
            print(f"[upload.subtitle] ❌ {error_msg}", file=sys.stderr)
            if STATE_MANAGEMENT_AVAILABLE and get_logger:
                logger = get_logger()
                logger.error(
                    "upload.subtitle.failed.duplicate",
                    error_msg,
                    episode_id=episode_id,
                    metadata={"language": subtitle_lang, "error_type": error_type, "error": error_str}
                )
        else:
            # 其他错误（权限、网络等）
            error_msg = f"Subtitle upload failed: {e}"
            print(f"[upload.subtitle] ⚠️  {error_msg}", file=sys.stderr)
            if STATE_MANAGEMENT_AVAILABLE and get_logger:
                logger = get_logger()
                logger.warning(
                    "upload.subtitle.failed",
                    error_msg,
                    episode_id=episode_id,
                    metadata={"error_type": error_type, "error": error_str}
                )


def postprocess_thumbnail(
    youtube: Any,
    video_id: str,
    thumbnail_path: Optional[Path],
    episode_id: Optional[str] = None,
) -> None:
    """
    后处理缩略图（调整大小并上传）
    
    Args:
        youtube: YouTube API 服务对象
        video_id: YouTube 视频 ID
        thumbnail_path: 缩略图路径（可选）
        episode_id: 期数 ID（用于日志）
    """
    if not thumbnail_path or not thumbnail_path.exists():
        # 记录日志：缩略图不存在，跳过上传
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.debug(
                "upload.thumbnail.skipped",
                f"Thumbnail not found, skipping upload: {thumbnail_path}",
                episode_id=episode_id,
                metadata={"thumbnail_path": str(thumbnail_path) if thumbnail_path else None}
            )
        return
    
    try:
        # Resize thumbnail if it exceeds size/dimension limits
        resize_thumbnail_if_needed = _get_resize_thumbnail()
        resized_thumbnail = resize_thumbnail_if_needed(thumbnail_path)
        
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(resized_thumbnail))
        ).execute()
        
        # Clean up temporary resized file if created
        if resized_thumbnail != thumbnail_path and resized_thumbnail.exists():
            try:
                resized_thumbnail.unlink()
            except (OSError, PermissionError) as cleanup_error:
                # Log cleanup errors but don't fail
                if STATE_MANAGEMENT_AVAILABLE and get_logger:
                    logger = get_logger()
                    logger.warning(
                        "upload.thumbnail.cleanup.failed",
                        f"Failed to cleanup resized thumbnail: {cleanup_error}",
                        episode_id=episode_id
                    )
    except Exception as e:
        # Log but don't fail
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.warning(
                "upload.thumbnail.failed",
                f"Thumbnail upload failed: {e}",
                episode_id=episode_id
            )


def attach_to_playlist(
    youtube: Any,
    video_id: str,
    playlist_id: Optional[str],
    episode_id: Optional[str] = None,
) -> None:
    """
    将视频添加到播放列表
    
    Args:
        youtube: YouTube API 服务对象
        video_id: YouTube 视频 ID
        playlist_id: 播放列表 ID（可选）
        episode_id: 期数 ID（用于日志）
    """
    if not playlist_id:
        # 记录日志：播放列表 ID 不存在，跳过添加
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.debug(
                "upload.playlist.skipped",
                f"Playlist ID not provided, skipping playlist addition",
                episode_id=episode_id,
                metadata={"playlist_id": None}
            )
        return
    
    try:
        add_video_to_playlist = _get_add_to_playlist()
        add_video_to_playlist(youtube, video_id, playlist_id, episode_id)
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.info(
                "upload.playlist.added",
                f"Video added to playlist: {playlist_id}",
                episode_id=episode_id,
                metadata={"playlist_id": playlist_id}
            )
    except Exception as e:
        # Log but don't fail
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.warning(
                "upload.playlist.failed",
                f"Failed to add video to playlist: {e}",
                episode_id=episode_id,
                metadata={"playlist_id": playlist_id}
            )
