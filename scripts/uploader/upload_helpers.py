#!/usr/bin/env python3
# coding: utf-8
"""
上传辅助函数

将 upload_video() 拆分为更小的、可测试的函数
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

from src.models.upload_config import UploadConfig
from src.core.errors import UploadError, TransientError

# Import functions from upload_to_youtube (lazy import to avoid circular dependency)
def _get_build_metadata():
    from scripts.uploader.upload_to_youtube import build_youtube_metadata
    return build_youtube_metadata

def _get_resize_thumbnail():
    from scripts.uploader.upload_to_youtube import resize_thumbnail_if_needed
    return resize_thumbnail_if_needed

def _get_add_to_playlist():
    from scripts.uploader.upload_to_youtube import add_video_to_playlist
    return add_video_to_playlist

try:
    from src.core.logger import get_logger
    STATE_MANAGEMENT_AVAILABLE = True
except ImportError:
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
    build_youtube_metadata = _get_build_metadata()
    return build_youtube_metadata(
        episode_id=upload_config.episode_id or "",
        title=upload_config.title,
        description=upload_config.description,
        privacy=upload_config.privacy_status,
        tags=upload_config.tags,
        category_id=upload_config.category_id,
        schedule=upload_config.schedule,
        default_language=upload_config.default_language,
    )


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

    file_size = upload_config.video_file.stat().st_size
    
    # Create media upload (resumable for large files)
    chunksize = -1 if file_size > 256 * 1024 * 1024 else None  # Auto-chunk for >256MB
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
    
    while retry_count <= upload_config.max_retries:
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
                if retry_count <= upload_config.max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    time.sleep(wait_time)
                    continue
                else:
                    raise TransientError(f"Upload failed after {upload_config.max_retries} retries: {error_content}")
            else:
                # Client errors, don't retry
                raise UploadError(f"Upload failed: {error_content}")
        
        except Exception as e:
            retry_count += 1
            if retry_count <= upload_config.max_retries:
                wait_time = 2 ** retry_count
                time.sleep(wait_time)
                continue
            else:
                raise UploadError(f"Upload exception after {upload_config.max_retries} retries: {e}")
    
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
        subtitle_lang = 'zh-CN'  # Default to Chinese
        subtitle_name = 'Chinese Subtitles'
        
        subtitle_str = str(subtitle_path)
        if '_en' in subtitle_str or '.en.' in subtitle_str:
            subtitle_lang = 'en'
            subtitle_name = 'English Subtitles'
        elif '_zh' in subtitle_str or '.zh' in subtitle_str:
            subtitle_lang = 'zh-CN'
            subtitle_name = 'Chinese Subtitles'
        elif '_ja' in subtitle_str or '.ja' in subtitle_str:
            subtitle_lang = 'ja'
            subtitle_name = 'Japanese Subtitles'
        
        # Determine MIME type based on file extension
        mime_type = 'text/plain'  # Default for SRT
        if subtitle_path.suffix.lower() == '.srt':
            mime_type = 'text/srt'
        elif subtitle_path.suffix.lower() == '.vtt':
            mime_type = 'text/vtt'
        
        youtube.captions().insert(
            part='snippet',
            body={
                'snippet': {
                    'videoId': video_id,
                    'language': subtitle_lang,
                    'name': subtitle_name
                }
            },
            media_body=MediaFileUpload(str(subtitle_path), mimetype=mime_type)
        ).execute()
        
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
        # Log but don't fail
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.warning(
                "upload.subtitle.failed",
                f"Subtitle upload failed: {e}",
                episode_id=episode_id
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

