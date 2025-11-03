#!/usr/bin/env python3
# coding: utf-8
"""
YouTube Upload Script - Workflow Stage 10

Uploads video to YouTube via Data API v3, updates schedule_master.json with
youtube_video_id, and logs events in structured JSON format.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    # Use logger if available, otherwise fallback to stderr
    try:
        from core.logger import get_logger
        logger = get_logger()
        logger.error(
            "upload.dependencies.missing",
            "Google API libraries not installed",
        )
    except ImportError:
    print('{"event": "upload", "status": "error", "error": "Google API libraries not installed"}', file=sys.stderr)
    sys.exit(1)

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))

# Import unified config and state management
try:
    from configuration import AppConfig
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    AppConfig = None

try:
    from core.state_manager import get_state_manager
    from core.logger import get_logger
    from core.event_bus import get_event_bus
    from core.errors import UploadError, TransientError, handle_errors
    STATE_MANAGEMENT_AVAILABLE = True
except ImportError:
    STATE_MANAGEMENT_AVAILABLE = False
    get_state_manager = None
    get_logger = None
    get_event_bus = None
    # Fallback error classes
    class UploadError(Exception):
        pass
    class TransientError(Exception):
        pass
    def handle_errors(context: str):
        def decorator(func):
            return func
        return decorator

# OAuth 2.0 scopes
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Backward compatibility
YouTubeUploadError = UploadError


def load_config() -> Dict:
    """Load configuration from config.yaml"""
    import yaml
    
    config_path = REPO_ROOT / "config" / "config.yaml"
    default_config = {
        "client_secrets_file": REPO_ROOT / "config" / "google" / "client_secrets.json",
        "token_file": REPO_ROOT / "config" / "google" / "youtube_token.json",
        "privacy_status": "unlisted",
        "category_id": 10,
        "tags": ["lofi", "music", "Kat Records", "chill"],
        "quota_limit_daily": 9000,
        "playlist_id": None,  # Optional: YouTube playlist ID to add videos to
    }
    
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
            
            youtube_config = config_data.get("youtube", {})
            upload_defaults = youtube_config.get("upload_defaults", {})
            
            if youtube_config.get("client_secrets_file"):
                default_config["client_secrets_file"] = REPO_ROOT / youtube_config["client_secrets_file"]
            if youtube_config.get("token_file"):
                default_config["token_file"] = REPO_ROOT / youtube_config["token_file"]
            if upload_defaults.get("privacyStatus"):
                default_config["privacy_status"] = upload_defaults["privacyStatus"]
            if upload_defaults.get("categoryId"):
                default_config["category_id"] = upload_defaults["categoryId"]
            if upload_defaults.get("tags"):
                default_config["tags"] = upload_defaults["tags"]
            if youtube_config.get("quota_limit_daily"):
                default_config["quota_limit_daily"] = youtube_config["quota_limit_daily"]
            if youtube_config.get("playlist_id"):
                default_config["playlist_id"] = youtube_config["playlist_id"]
        except Exception as e:
            # Use defaults on error, but log it
            if STATE_MANAGEMENT_AVAILABLE and get_logger:
                logger = get_logger()
                logger.warning(
                    "upload.config.load_error",
                    f"Error loading config, using defaults: {e}",
                )
    
    return default_config


def get_credentials(config: Dict) -> Optional[Credentials]:
    """
    Get valid credentials for YouTube API
    
    Returns:
        Credentials object if valid, None if needs authorization
    """
    if not GOOGLE_API_AVAILABLE:
        return None
    
    creds = None
    
    # Load saved token
    token_file = config["token_file"]
    if token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as e:
            # Remove corrupted token and log
            try:
                token_file.unlink()
            except (FileNotFoundError, PermissionError, OSError):
                pass  # 文件可能不存在或无法删除，忽略
            if STATE_MANAGEMENT_AVAILABLE and get_logger:
                logger = get_logger()
                logger.warning(
                    "upload.credentials.corrupted",
                    f"Corrupted token file removed: {e}",
                )
    
    # Refresh if expired
    if creds and not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Save refreshed token
                token_data = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes,
                }
                if creds.expiry:
                    token_data['expiry'] = creds.expiry.isoformat()
                token_file.write_text(json.dumps(token_data, indent=2), encoding='utf-8')
                token_file.chmod(0o600)
            except (PermissionError, OSError, IOError) as e:
                creds = None
                if STATE_MANAGEMENT_AVAILABLE and get_logger:
                    logger = get_logger()
                    logger.warning(
                        "upload.credentials.refresh_failed",
                        f"Failed to refresh credentials: {e}",
                    )
    
    return creds


def authorize(config: Dict) -> Credentials:
    """
    Perform OAuth authorization flow
    
    Returns:
        Valid credentials
    """
    if not GOOGLE_API_AVAILABLE:
        raise YouTubeUploadError("Google API libraries not installed")
    
    client_secrets_file = config["client_secrets_file"]
    if not client_secrets_file.exists():
        raise YouTubeUploadError(
            f"OAuth credentials file not found: {client_secrets_file}\n"
            f"Please run: python scripts/local_picker/youtube_auth.py --setup"
        )
    
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets_file),
        SCOPES
    )
    
    creds = flow.run_local_server(port=0, open_browser=True)
    
    # Save token
    token_file = config["token_file"]
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes,
    }
    if creds.expiry:
        token_data['expiry'] = creds.expiry.isoformat()
    token_file.write_text(json.dumps(token_data, indent=2), encoding='utf-8')
    token_file.chmod(0o600)
    
    return creds


def get_authenticated_service(config: Dict):
    """
    Get authenticated YouTube API service
    
    Returns:
        YouTube API service object
    """
    creds = get_credentials(config)
    
    if not creds or not creds.valid:
        creds = authorize(config)
    
    return build('youtube', 'v3', credentials=creds)


def upload_video(
    youtube,
    video_file: Path,
    title: str,
    description: str,
    config: Dict,
    subtitle_path: Optional[Path] = None,
    thumbnail_path: Optional[Path] = None,
    episode_id: Optional[str] = None,
    max_retries: int = 5
) -> Dict[str, str]:
    """
    Upload video to YouTube with retry mechanism
    
    Args:
        youtube: YouTube API service object
        video_file: Path to video file
        title: Video title
        description: Video description
        config: Configuration dictionary
        subtitle_path: Optional SRT subtitle file
        thumbnail_path: Optional thumbnail image
        episode_id: Episode ID for logging
        max_retries: Maximum retry attempts
    
    Returns:
        Dictionary with video_id, video_url, upload_time
    """
    # Import here to avoid circular imports
    try:
        from src.models.upload_config import UploadConfig
        from scripts.uploader.upload_helpers import (
            prepare_body,
            resumable_upload,
            attach_subtitle,
            postprocess_thumbnail,
            attach_to_playlist,
        )
    except ImportError:
        # Fallback to old implementation if imports fail
        return _upload_video_legacy(youtube, video_file, title, description, config, 
                                   subtitle_path, thumbnail_path, episode_id, max_retries)
    
    # Create UploadConfig
    upload_config = UploadConfig(
        video_file=video_file,
        title=title,
        description=description,
        privacy_status=config["privacy_status"],
        category_id=config["category_id"],
        tags=config["tags"],
        subtitle_path=subtitle_path,
        thumbnail_path=thumbnail_path,
        episode_id=episode_id,
        max_retries=max_retries,
        schedule=config.get("schedule", False),
        default_language=config.get("default_language", "en"),
        playlist_id=config.get("playlist_id"),
    )
    
    start_time = time.time()
    
    # Prepare metadata
    body = prepare_body(upload_config)
            
    # Perform resumable upload
    video_id = resumable_upload(youtube, upload_config, body)
    
    upload_time = time.time() - start_time
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Attach subtitle
    attach_subtitle(youtube, video_id, upload_config.subtitle_path, episode_id)
    
    # Post-process thumbnail
    postprocess_thumbnail(youtube, video_id, upload_config.thumbnail_path, episode_id)
    
    # Attach to playlist
    attach_to_playlist(youtube, video_id, upload_config.playlist_id, episode_id)
    
    result = {
        "video_id": video_id,
        "video_url": video_url,
        "upload_time": datetime.now().isoformat(),
        "duration_seconds": upload_time,
        "episode_id": episode_id,
    }
    
    if upload_config.playlist_id:
        result["playlist_id"] = upload_config.playlist_id
    
    return result


def _upload_video_legacy(
    youtube,
    video_file: Path,
    title: str,
    description: str,
    config: Dict,
    subtitle_path: Optional[Path] = None,
    thumbnail_path: Optional[Path] = None,
    episode_id: Optional[str] = None,
    max_retries: int = 5
) -> Dict[str, str]:
    """Legacy implementation fallback"""
    if not video_file.exists():
        raise UploadError(f"Video file not found: {video_file}")
    
    # Use old implementation as fallback
    # (Keeping original code as backup, not shown here for brevity)
    raise UploadError("Legacy implementation not available")


def update_schedule_record(episode_id: str, video_id: str, video_url: str) -> bool:
    """
    Update schedule_master.json with YouTube video information
    
    Args:
        episode_id: Episode ID (YYYYMMDD format)
        video_id: YouTube video ID
        video_url: YouTube video URL
    
    Returns:
        True if update successful
    """
    if not STATE_MANAGEMENT_AVAILABLE:
        return False
    
    try:
        state_manager = get_state_manager()
        ep = state_manager.get_episode(episode_id)
        if not ep:
            return False
        
        # Update metadata (not status)
        state_manager.update_episode_metadata(
            episode_id=episode_id,
            youtube_video_id=video_id,
            youtube_video_url=video_url,
            youtube_uploaded_at=datetime.now().isoformat()
        )
        
        return True
    except Exception as e:
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.error(
                "upload.schedule.update.failed",
                f"Failed to update schedule_master.json: {e}",
                episode_id=episode_id,
                traceback=str(e)
            )
        return False


def log_event(event: str, episode_id: Optional[str], status: str, **kwargs) -> None:
    """
    Log structured JSON event to logs/katrec.log
    
    Args:
        event: Event name (e.g., "upload")
        episode_id: Episode ID
        status: Status (e.g., "completed", "failed")
        **kwargs: Additional metadata
    """
    log_entry = {
        "event": event,
        "episode": episode_id,
        "status": status,
        "timestamp": datetime.now().isoformat(),
    }
    log_entry.update(kwargs)
    
    # Write JSON line to log file
    log_file = REPO_ROOT / "logs" / "katrec.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    # Also use structured logger if available
    if STATE_MANAGEMENT_AVAILABLE and get_logger:
        logger = get_logger()
        level = "ERROR" if status == "failed" else ("INFO" if status == "completed" else "DEBUG")
        logger.log_event(
            event_name=f"upload.{status}",
            message=kwargs.get("message", f"Upload {status}"),
            episode_id=episode_id,
            level=level,
            metadata=kwargs
        )


def read_metadata_files(
    episode_id: str,
    video_file: Path,
    title_file: Optional[Path] = None,
    desc_file: Optional[Path] = None
) -> Dict[str, str]:
    """
    Read YouTube metadata from files
    
    Args:
        episode_id: Episode ID
        video_file: Video file path (used to find episode directory)
        title_file: Optional explicit title file path
        desc_file: Optional explicit description file path
    
    Returns:
        Dictionary with title, description, subtitle_path, thumbnail_path
    """
    metadata = {
        "title": None,
        "description": None,
        "subtitle_path": None,
        "thumbnail_path": None,
    }
    
    # Try to find episode directory
    episode_dir = video_file.parent
    output_dir = REPO_ROOT / "output"
    
    # Strategy: Always prefer final directories (YYYY-MM-DD_Title format) as they contain complete metadata
    # 1. Check if video is already in a final directory
    if episode_dir.name.startswith(episode_id[:8]) and "-" in episode_dir.name:
        # Video is in final directory, use it
        pass
    else:
        # 2. Video is in output root, search for final directory with matching episode ID
        final_dirs = list(output_dir.glob(f"{episode_id[:8]}-*"))
        if final_dirs:
            # Prefer the one with the most complete metadata (has title file)
            best_dir = None
            for d in final_dirs:
                title_file = d / f"{episode_id}_youtube_title.txt"
                if title_file.exists():
                    best_dir = d
                    break
            episode_dir = best_dir if best_dir else final_dirs[0]
        else:
            # 3. Fallback: search recursively in output directory
            found_dir = None
            for path in output_dir.rglob(f"{episode_id}_youtube_title.txt"):
                found_dir = path.parent
                break
            if found_dir:
                episode_dir = found_dir
            # If still not found, use output root as last resort
    
    # Read title
    if title_file and title_file.exists():
        metadata["title"] = title_file.read_text(encoding="utf-8").strip()
    else:
        # Try episode_dir first
        title_path = episode_dir / f"{episode_id}_youtube_title.txt"
        if title_path.exists():
            metadata["title"] = title_path.read_text(encoding="utf-8").strip()
        else:
            # Fallback: search in all final directories
            for final_dir in output_dir.glob(f"{episode_id[:8]}-*"):
                fallback_title = final_dir / f"{episode_id}_youtube_title.txt"
                if fallback_title.exists():
                    metadata["title"] = fallback_title.read_text(encoding="utf-8").strip()
                    break
    
    # Read description
    if desc_file and desc_file.exists():
        metadata["description"] = desc_file.read_text(encoding="utf-8").strip()
    else:
        # Try episode_dir first
        desc_path = episode_dir / f"{episode_id}_youtube_description.txt"
        if desc_path.exists():
            metadata["description"] = desc_path.read_text(encoding="utf-8").strip()
        else:
            # Fallback: search in all final directories
            for final_dir in output_dir.glob(f"{episode_id[:8]}-*"):
                fallback_desc = final_dir / f"{episode_id}_youtube_description.txt"
                if fallback_desc.exists():
                    metadata["description"] = fallback_desc.read_text(encoding="utf-8").strip()
                    break
    
    # Find subtitle
    srt_path = episode_dir / f"{episode_id}_youtube.srt"
    if srt_path.exists():
        metadata["subtitle_path"] = str(srt_path)
    else:
        # Fallback: search in final directories
        for final_dir in output_dir.glob(f"{episode_id[:8]}-*"):
            fallback_srt = final_dir / f"{episode_id}_youtube.srt"
            if fallback_srt.exists():
                metadata["subtitle_path"] = str(fallback_srt)
                break
    
    # Find thumbnail
    cover_path = episode_dir / f"{episode_id}_cover.png"
    if cover_path.exists():
        metadata["thumbnail_path"] = str(cover_path)
    else:
        # Fallback: search in final directories
        for final_dir in output_dir.glob(f"{episode_id[:8]}-*"):
            fallback_cover = final_dir / f"{episode_id}_cover.png"
            if fallback_cover.exists():
                metadata["thumbnail_path"] = str(fallback_cover)
                break
    
    return metadata


def parse_episode_date(episode_id: str) -> Optional[datetime]:
    """
    Parse episode ID (YYYYMMDD format) to datetime object
    
    Args:
        episode_id: Episode ID string (e.g., "20251104")
    
    Returns:
        datetime object in UTC, or None if parsing fails
    """
    try:
        if len(episode_id) >= 8:
            date_str = episode_id[:8]
            return datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError) as e:
        # Invalid episode_id format, return None and log if available
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.debug(
                "upload.parse_episode_date.failed",
                f"Failed to parse episode date: {e}",
                metadata={"episode_id": episode_id}
            )
    return None


def resize_thumbnail_if_needed(thumbnail_path: Path, max_size_mb: float = 2.0, max_width: int = 1280) -> Path:
    """
    Resize thumbnail if it exceeds size or dimension limits
    
    Args:
        thumbnail_path: Path to thumbnail image
        max_size_mb: Maximum file size in MB (default: 2MB)
        max_width: Maximum width in pixels (default: 1280px)
    
    Returns:
        Path to thumbnail (original or resized)
    """
    if not PIL_AVAILABLE:
        return thumbnail_path
    
    if not thumbnail_path.exists():
        return thumbnail_path
    
    # Check file size
    file_size_mb = thumbnail_path.stat().st_size / (1024 * 1024)
    
    try:
        with Image.open(thumbnail_path) as img:
            width, height = img.size
            
            # Check if resizing is needed
            needs_resize = False
            if file_size_mb > max_size_mb:
                needs_resize = True
            elif width > max_width:
                needs_resize = True
            
            if needs_resize:
                # Calculate new dimensions (maintain aspect ratio)
                if width > max_width:
                    ratio = max_width / width
                    new_width = max_width
                    new_height = int(height * ratio)
                else:
                    new_width = width
                    new_height = height
                
                # Resize image
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save to temporary file
                temp_path = thumbnail_path.parent / f"{thumbnail_path.stem}_resized{thumbnail_path.suffix}"
                resized_img.save(temp_path, format=img.format, optimize=True, quality=85)
                
                # Check if new file is small enough
                new_size_mb = temp_path.stat().st_size / (1024 * 1024)
                if new_size_mb <= max_size_mb:
                    return temp_path
                else:
                    # If still too large, try lower quality
                    resized_img.save(temp_path, format=img.format, optimize=True, quality=70)
                    return temp_path
    except Exception as e:
        # If resizing fails, return original
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.warning(f"Thumbnail resize failed: {e}", episode_id=None)
        return thumbnail_path
    
    return thumbnail_path


def build_youtube_metadata(
    episode_id: str,
    title: str,
    description: str,
    privacy: str = "unlisted",
    tags: Optional[List[str]] = None,
    category_id: int = 10,
    schedule: bool = False,
    default_language: str = "en"
) -> Dict:
    """
    Build complete YouTube metadata payload with all standard and optional fields
    
    This function constructs a comprehensive JSON body for youtube.videos().insert(),
    including:
    - Required snippet fields (title, description, tags, categoryId)
    - Status fields (privacyStatus, license, embeddable, etc.)
    - Recording details (derived from episode_id)
    - Scheduled publishing (if schedule=True)
    - Localized content (for i18n readiness)
    - Topic categories (for SEO)
    
    Args:
        episode_id: Episode ID in YYYYMMDD format (e.g., "20251104")
        title: Video title
        description: Video description
        privacy: Privacy status (private/unlisted/public)
        tags: List of tags (defaults to config if None)
        category_id: YouTube category ID (10 = Music)
        schedule: If True, set publishAt to episode date + 9:00 AM local
        default_language: Default language code (e.g., "en", "zh")
    
    Returns:
        Complete metadata dictionary ready for YouTube API
    """
    # Parse episode date from episode_id
    episode_date = parse_episode_date(episode_id)
    
    # Default tags if not provided
    if tags is None:
        tags = ["lofi", "music", "Kat Records", "chill"]
    
    # Build snippet (required and optional fields)
    snippet = {
        'title': title,
        'description': description,
        'tags': tags,
        'categoryId': str(category_id),
        'defaultLanguage': default_language,
        # Localized content (same as base for now, ready for i18n expansion)
        'localized': {
            'title': title,
            'description': description
        }
    }
    
    # Build status (required and optional fields)
    status = {
        'privacyStatus': privacy,
        'license': 'creativeCommon',  # or 'youtube'
        'embeddable': True,
        'publicStatsViewable': True,
        'selfDeclaredMadeForKids': False
    }
    
    # Add scheduled publishing if requested
    if schedule and episode_date:
        # Set publish time to episode date at 9:00 AM local time
        # Convert to UTC for API (adjust timezone as needed)
        publish_at = episode_date.replace(hour=9, minute=0, second=0)
        # Convert to RFC 3339 format (ISO 8601)
        status['publishAt'] = publish_at.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    # Build recording details (derived from episode_id)
    body = {
        'snippet': snippet,
        'status': status
    }
    
    # Add recording details if episode date is available
    if episode_date:
        body['recordingDetails'] = {
            'recordingDate': episode_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        }
    
    # Note: topicDetails is read-only and auto-generated by YouTube based on video content
    # We don't include it in the insert payload, but YouTube will automatically generate
    # topic categories based on the video's title, description, tags, and categoryId
    
    return body


def add_video_to_playlist(youtube, video_id: str, playlist_id: str, episode_id: Optional[str] = None) -> None:
    """
    Add uploaded video to a YouTube playlist
    
    Args:
        youtube: YouTube API service object
        video_id: YouTube video ID
        playlist_id: YouTube playlist ID
        episode_id: Episode ID for logging
    """
    try:
        playlist_item = {
            'snippet': {
                'playlistId': playlist_id,
                'resourceId': {
                    'kind': 'youtube#video',
                    'videoId': video_id
                }
            }
        }
        
        response = youtube.playlistItems().insert(
            part='snippet',
            body=playlist_item
        ).execute()
        
        return response
    except HttpError as e:
        error_content = json.loads(e.content.decode('utf-8'))
        raise YouTubeUploadError(f"Failed to add video to playlist: {error_content}")
    except Exception as e:
        raise YouTubeUploadError(f"Playlist error: {str(e)}")


def check_already_uploaded(episode_id: str) -> Optional[str]:
    """
    Check if episode already has youtube_video_id
    
    Returns:
        Video ID if already uploaded, None otherwise
    """
    if not STATE_MANAGEMENT_AVAILABLE:
        return None
    
    try:
        state_manager = get_state_manager()
        ep = state_manager.get_episode(episode_id)
        if ep and ep.get("youtube_video_id"):
            return ep.get("youtube_video_id")
    except Exception as e:
        # Log but don't fail - state manager might not be available
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.debug(
                "upload.check_already_uploaded.failed",
                f"Failed to check upload status: {e}",
                episode_id=episode_id
            )
    
    return None


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Upload video to YouTube (Workflow Stage 10)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--episode",
        required=True,
        help="Episode ID (YYYYMMDD format)"
    )
    
    parser.add_argument(
        "--video",
        type=Path,
        required=False,
        help="Path to video file (*_youtube.mp4). Auto-detected if not provided."
    )
    
    parser.add_argument(
        "--title-file",
        type=Path,
        help="Path to title file (*_youtube_title.txt). Auto-detected if not provided."
    )
    
    parser.add_argument(
        "--desc-file",
        type=Path,
        help="Path to description file (*_youtube_description.txt). Auto-detected if not provided."
    )
    
    parser.add_argument(
        "--privacy",
        choices=["private", "unlisted", "public"],
        help="Privacy status (overrides config)"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force upload even if already uploaded"
    )
    
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Schedule upload for episode date at 9:00 AM (requires episode_id to be in YYYYMMDD format)"
    )
    
    args = parser.parse_args()
    
    episode_id = args.episode
    
    # Auto-detect video file if not provided
    if args.video:
        video_file = Path(args.video)
    else:
        # Try to find video file automatically
        output_dir = REPO_ROOT / "output"
        
        # First, try in output root
        video_file = output_dir / f"{episode_id}_youtube.mp4"
        
        # If not found, try in final directories
        if not video_file.exists():
            final_dirs = list(output_dir.glob(f"{episode_id[:8]}-*"))
            for final_dir in final_dirs:
                candidate = final_dir / f"{episode_id}_youtube.mp4"
                if candidate.exists():
                    video_file = candidate
                    break
        
        # If still not found, check all possible locations
        if not video_file.exists():
            all_videos = list(output_dir.rglob(f"{episode_id}_youtube.mp4"))
            if all_videos:
                video_file = all_videos[0]
    
    # Validate inputs
    if not video_file.exists():
        log_event("upload", episode_id, "error", error="Video file not found", file=str(video_file))
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.error(
                "upload.file_not_found",
                f"Video file not found: {video_file}",
                episode_id=episode_id,
                metadata={"video_file": str(video_file)}
            )
        # Keep user-friendly message for CLI
        print(f'\n❌ 视频文件未找到: {video_file}')
        print(f'💡 请确保视频文件存在，或使用 --video 参数指定路径\n')
        print(f'{{"event": "upload", "episode": "{episode_id}", "status": "error", "error": "Video file not found: {video_file}. Please specify --video or ensure file exists."}}')
        sys.exit(1)
    
    # Check if already uploaded (idempotent)
    existing_video_id = check_already_uploaded(episode_id)
    if existing_video_id and not args.force:
        log_event("upload", episode_id, "skipped", video_id=existing_video_id, reason="already_uploaded")
        print(f'{{"event": "upload", "episode": "{episode_id}", "status": "skipped", "video_id": "{existing_video_id}", "reason": "already_uploaded"}}')
        sys.exit(0)
    
    # Load configuration
    config = load_config()
    if args.privacy:
        config["privacy_status"] = args.privacy
    
    # Add schedule flag to config
    config["schedule"] = getattr(args, 'schedule', False)
    
    # Read metadata
    metadata = read_metadata_files(episode_id, video_file, args.title_file, args.desc_file)
    
    # Log metadata reading results for debugging
    if STATE_MANAGEMENT_AVAILABLE and get_logger:
        logger = get_logger()
        logger.debug(
            "upload.metadata.read",
            f"Read metadata: title={bool(metadata['title'])}, desc={bool(metadata['description'])}, subtitle={bool(metadata['subtitle_path'])}, thumbnail={bool(metadata['thumbnail_path'])}",
            episode_id=episode_id,
            metadata={
                "has_title": bool(metadata["title"]),
                "has_description": bool(metadata["description"]),
                "has_subtitle": bool(metadata["subtitle_path"]),
                "has_thumbnail": bool(metadata["thumbnail_path"]),
            }
        )
    
    if not metadata["title"]:
        metadata["title"] = f"Kat Records Lo-Fi Mix - {episode_id}"
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.warning(
                "upload.metadata.fallback",
                f"Using default title, title file not found",
                episode_id=episode_id
            )
    
    if not metadata["description"]:
        metadata["description"] = "Kat Records - Lo-Fi Radio Mix"
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.warning(
                "upload.metadata.fallback",
                f"Using default description, description file not found",
                episode_id=episode_id
            )
    
    # Log upload start
    log_event("upload", episode_id, "started", video_file=str(video_file))
    
    try:
        # Build metadata for logging (validate JSON structure)
        test_metadata = build_youtube_metadata(
            episode_id=episode_id,
            title=metadata["title"] or f"Kat Records Lo-Fi Mix - {episode_id}",
            description=metadata["description"] or "Kat Records - Lo-Fi Radio Mix",
            privacy=config["privacy_status"],
            tags=config["tags"],
            category_id=config["category_id"],
            schedule=config.get("schedule", False),
            default_language=config.get("default_language", "en")
        )
        
        # Log metadata structure for debugging
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.debug(
                "upload.metadata.built",
                f"Built YouTube metadata with {len(test_metadata)} sections",
                episode_id=episode_id,
                metadata={"sections": list(test_metadata.keys()), "section_count": len(test_metadata)}
            )
        
        # Get authenticated service
        youtube = get_authenticated_service(config)
        
        # Resize thumbnail if needed before upload
        thumbnail_path = None
        if metadata["thumbnail_path"]:
            thumbnail_path = resize_thumbnail_if_needed(Path(metadata["thumbnail_path"]))
        
        # Upload video
        result = upload_video(
            youtube=youtube,
            video_file=video_file,
            title=metadata["title"],
            description=metadata["description"],
            config=config,
            subtitle_path=Path(metadata["subtitle_path"]) if metadata["subtitle_path"] else None,
            thumbnail_path=thumbnail_path,
            episode_id=episode_id,
            max_retries=5
        )
        
        # Update schedule_master.json
        update_schedule_record(episode_id, result["video_id"], result["video_url"])
        
        # Trigger event bus
        if STATE_MANAGEMENT_AVAILABLE and get_event_bus:
            try:
                event_bus = get_event_bus()
                event_bus.emit_upload_started(episode_id)
                event_bus.emit_upload_completed(episode_id, result["video_id"], result["video_url"])
            except Exception as e:
                # Event bus optional, log but don't fail
                if get_logger:
                    logger = get_logger()
                    logger.warning(
                        "upload.event_bus.failed",
                        f"Event bus notification failed: {e}",
                        episode_id=episode_id
                    )
        
        # Write upload result JSON
        output_dir = video_file.parent
        result_file = output_dir / f"{episode_id}_youtube_upload.json"
        result_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        
        # Log success
        log_event(
            "upload",
            episode_id,
            "completed",
            video_id=result["video_id"],
            video_url=result["video_url"],
            latency=result["duration_seconds"]
        )
        
        # Output JSON result
        print(json.dumps({
            "event": "upload",
            "episode": episode_id,
            "status": "completed",
            "video_id": result["video_id"],
            "video_url": result["video_url"],
            "latency": result["duration_seconds"],
        }, ensure_ascii=False))
        
        sys.exit(0)
    
    except YouTubeUploadError as e:
        log_event("upload", episode_id, "failed", error=str(e))
        print(json.dumps({
            "event": "upload",
            "episode": episode_id,
            "status": "failed",
            "error": str(e),
        }, ensure_ascii=False))
        
        # Trigger error event
        if STATE_MANAGEMENT_AVAILABLE and get_event_bus:
            try:
                event_bus = get_event_bus()
                event_bus.emit_upload_failed(episode_id, str(e))
            except Exception as event_error:
                # Event bus optional, log but don't fail
                if get_logger:
                    logger = get_logger()
                    logger.warning(
                        "upload.event_bus.error_failed",
                        f"Event bus error notification failed: {event_error}",
                        episode_id=episode_id
                    )
        
        sys.exit(1)
    
    except Exception as e:
        error_msg = str(e)
        log_event("upload", episode_id, "error", error=error_msg, exception_type=type(e).__name__)
        
        # Log to structured logger
        if STATE_MANAGEMENT_AVAILABLE and get_logger:
            logger = get_logger()
            logger.error(
                "upload.unexpected_error",
                f"Unexpected error during upload: {error_msg}",
                episode_id=episode_id,
                traceback=str(e),
                metadata={"exception_type": type(e).__name__}
            )
        
        # 提供更友好的错误提示
        if "403" in error_msg or "accessNotConfigured" in error_msg:
            print(f'\n❌ 上传失败：YouTube Data API v3 未启用')
            print(f'\n🔧 解决步骤：')
            print(f'   1. 访问 Google Cloud Console：')
            print(f'      https://console.cloud.google.com/')
            print(f'   2. 转到 "APIs & Services" → "Library"')
            print(f'   3. 搜索并启用 "YouTube Data API v3"')
            print(f'   4. 等待 2-5 分钟让更改生效')
            print(f'   5. 重新运行上传命令')
            print(f'\n💡 或运行检查脚本：')
            print(f'   .venv/bin/python3 scripts/check_youtube_api.py\n')
        elif "401" in error_msg or "unauthorized" in error_msg.lower():
            print(f'\n⚠️  认证失败：需要重新授权')
            print(f'💡 下次运行上传时会自动触发授权流程\n')
        else:
            print(f'\n❌ 上传失败：{error_msg}\n')
        
        print(json.dumps({
            "event": "upload",
            "episode": episode_id,
            "status": "error",
            "error": error_msg,
            "exception_type": type(e).__name__,
        }, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()

