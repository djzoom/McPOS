#!/usr/bin/env python3
# coding: utf-8
"""
YouTube视频上传模块

功能：
1. 单视频上传（支持大文件分块上传）
2. 自动上传字幕和缩略图
3. 错误处理和重试机制（指数退避）
4. 配额感知和限流
5. 与状态管理器集成
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

try:
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    print("⚠️  Google API 库未安装，请运行: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT / "src"))

from youtube_auth import get_authenticated_service, YouTubeAuthError, setup_auth, check_auth_status

# 默认配置
DEFAULT_PRIVACY_STATUS = "unlisted"  # private, unlisted, public
DEFAULT_CATEGORY_ID = 10  # Music
DEFAULT_TAGS = ["lofi", "kat records", "vibe coding"]
UPLOAD_LOGS_DIR = REPO_ROOT / "output" / "upload_logs"


class YouTubeUploadError(Exception):
    """YouTube上传错误"""
    pass


def read_youtube_metadata(episode_dir: Path, episode_id: str) -> Dict[str, str]:
    """
    读取期数目录中的YouTube元数据文件
    
    返回：
    - title: 标题（从 {episode_id}_youtube_title.txt）
    - description: 描述（从 {episode_id}_youtube_description.txt）
    - subtitle_path: SRT字幕文件路径
    - thumbnail_path: 封面图片路径
    """
    metadata = {
        "title": None,
        "description": None,
        "subtitle_path": None,
        "thumbnail_path": None,
    }
    
    # 读取标题
    title_file = episode_dir / f"{episode_id}_youtube_title.txt"
    if title_file.exists():
        metadata["title"] = title_file.read_text(encoding="utf-8").strip()
    
    # 读取描述
    desc_file = episode_dir / f"{episode_id}_youtube_description.txt"
    if desc_file.exists():
        metadata["description"] = desc_file.read_text(encoding="utf-8").strip()
    
    # 检查字幕文件
    srt_file = episode_dir / f"{episode_id}_youtube.srt"
    if srt_file.exists():
        metadata["subtitle_path"] = str(srt_file)
    
    # 检查封面图片
    cover_file = episode_dir / f"{episode_id}_cover.png"
    if cover_file.exists():
        metadata["thumbnail_path"] = str(cover_file)
    
    return metadata


def upload_video(
    video_path: Path,
    title: str,
    description: str,
    privacy_status: str = DEFAULT_PRIVACY_STATUS,
    tags: Optional[List[str]] = None,
    category_id: int = DEFAULT_CATEGORY_ID,
    thumbnail_path: Optional[Path] = None,
    subtitle_path: Optional[Path] = None,
    episode_id: Optional[str] = None,
    max_retries: int = 3
) -> Dict[str, str]:
    """
    上传视频到YouTube
    
    Args:
        video_path: 视频文件路径
        title: 视频标题
        description: 视频描述
        privacy_status: 可见性（private/unlisted/public）
        tags: 标签列表
        category_id: 分类ID（10=Music）
        thumbnail_path: 缩略图路径（可选）
        subtitle_path: 字幕文件路径（可选）
        episode_id: 期数ID（用于状态跟踪）
        max_retries: 最大重试次数
    
    Returns:
        {
            "video_id": "YouTube视频ID",
            "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
            "upload_time": "ISO时间戳"
        }
    
    Raises:
        YouTubeUploadError: 上传失败
    """
    if not GOOGLE_API_AVAILABLE:
        raise YouTubeUploadError("Google API 库未安装")
    
    if not video_path.exists():
        raise YouTubeUploadError(f"视频文件不存在: {video_path}")
    
    # 检查认证状态
    if not check_auth_status():
        raise YouTubeUploadError("未通过认证，请先运行: python scripts/local_picker/youtube_upload.py --setup")
    
    # 获取YouTube API服务
    try:
        youtube = get_authenticated_service()
    except Exception as e:
        raise YouTubeUploadError(f"获取YouTube API服务失败: {e}")
    
    # 如果没有标题，使用默认值
    if not title:
        title = f"Kat Records Lo-Fi Mix - {episode_id or 'Unknown'}"
    
    # 如果没有描述，使用默认值
    if not description:
        description = "Kat Records - Lo-Fi Radio Mix"
    
    # 构建视频元数据
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags or DEFAULT_TAGS,
            'categoryId': str(category_id),
        },
        'status': {
            'privacyStatus': privacy_status,
        }
    }
    
    # 创建媒体上传对象（支持大文件分块上传）
    file_size = video_path.stat().st_size
    print(f"📹 上传视频: {video_path.name} ({file_size / 1024 / 1024:.1f} MB)")
    
    # 根据文件大小选择上传方式
    chunksize = -1  # -1表示自动分块（适用于大文件）
    if file_size < 256 * 1024 * 1024:  # <256MB使用标准上传
        chunksize = None
    
    media = MediaFileUpload(
        str(video_path),
        chunksize=chunksize,
        resumable=True
    )
    
    # 执行上传（带重试机制）
    upload_request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )
    
    video_id = None
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            status, response = upload_request.next_chunk()
            if response is not None:
                if 'id' in response:
                    video_id = response['id']
                    print(f"✅ 视频上传成功！Video ID: {video_id}")
                    break
                else:
                    raise YouTubeUploadError(f"上传响应异常: {response}")
            
            # 显示上传进度
            if status:
                progress = int(status.progress() * 100)
                print(f"📊 上传进度: {progress}%", end='\r')
        
        except HttpError as e:
            error_content = e.content.decode('utf-8') if e.content else str(e)
            
            # 检查是否是配额错误
            if e.resp.status == 403 and 'quotaExceeded' in error_content:
                raise YouTubeUploadError("❌ API配额已耗尽，请明天再试或申请配额提升")
            
            # 检查是否是认证错误
            if e.resp.status == 401:
                raise YouTubeUploadError("❌ 认证失败，请重新授权: python scripts/local_picker/youtube_upload.py --setup")
            
            # 其他错误，根据状态码决定是否重试
            if e.resp.status in [500, 502, 503, 504]:  # 服务器错误，可重试
                retry_count += 1
                if retry_count <= max_retries:
                    wait_time = 2 ** retry_count  # 指数退避
                    print(f"⚠️  上传失败 (尝试 {retry_count}/{max_retries})，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise YouTubeUploadError(f"上传失败（已重试{max_retries}次）: {error_content}")
            else:
                # 客户端错误，不重试
                raise YouTubeUploadError(f"上传失败: {error_content}")
        
        except Exception as e:
            retry_count += 1
            if retry_count <= max_retries:
                wait_time = 2 ** retry_count
                print(f"⚠️  上传异常 (尝试 {retry_count}/{max_retries})，{wait_time}秒后重试...")
                time.sleep(wait_time)
                continue
            else:
                raise YouTubeUploadError(f"上传异常（已重试{max_retries}次）: {e}")
    
    if not video_id:
        raise YouTubeUploadError("上传失败：未获得Video ID")
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # 上传字幕（如果存在）
    if subtitle_path and Path(subtitle_path).exists():
        try:
            upload_subtitle(youtube, video_id, subtitle_path)
        except Exception as e:
            print(f"⚠️  字幕上传失败（不影响视频）: {e}")
    
    # 上传缩略图（如果存在）
    if thumbnail_path and Path(thumbnail_path).exists():
        try:
            upload_thumbnail(youtube, video_id, thumbnail_path)
        except Exception as e:
            print(f"⚠️  缩略图上传失败（不影响视频）: {e}")
    
    return {
        "video_id": video_id,
        "video_url": video_url,
        "upload_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "episode_id": episode_id,
    }


def upload_subtitle(youtube, video_id: str, srt_path: Path, language: str = "zh-CN") -> None:
    """上传字幕文件"""
    print(f"📝 上传字幕: {Path(srt_path).name}")
    
    youtube.captions().insert(
        part='snippet',
        body={
            'snippet': {
                'videoId': video_id,
                'language': language,
                'name': '中文字幕'
            }
        },
        media_body=MediaFileUpload(str(srt_path))
    ).execute()
    
    print("✅ 字幕上传成功")


def upload_thumbnail(youtube, video_id: str, thumbnail_path: Path) -> None:
    """上传缩略图"""
    print(f"🖼️  上传缩略图: {Path(thumbnail_path).name}")
    
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(str(thumbnail_path))
    ).execute()
    
    print("✅ 缩略图上传成功")


def save_upload_log(result: Dict[str, str], episode_dir: Path) -> None:
    """保存上传日志"""
    UPLOAD_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    log_file = episode_dir / "upload_result.json"
    log_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    
    # 同时保存到全局日志目录
    today = time.strftime("%Y-%m-%d")
    global_log = UPLOAD_LOGS_DIR / f"upload_{today}.jsonl"
    with global_log.open("a", encoding='utf-8') as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


def upload_episode(
    episode_dir: Path,
    episode_id: str,
    privacy_status: str = DEFAULT_PRIVACY_STATUS,
    update_state: bool = True
) -> Dict[str, str]:
    """
    上传期数的视频
    
    Args:
        episode_dir: 期数目录（如 output/20251102_Title/）
        episode_id: 期数ID（如 "20251102"）
        privacy_status: 可见性设置
        update_state: 是否更新schedule_master.json状态
    
    Returns:
        上传结果字典
    """
    # 查找视频文件
    video_files = list(episode_dir.glob(f"{episode_id}_youtube.mp4"))
    if not video_files:
        # 回退：查找任何mp4文件
        video_files = list(episode_dir.glob("*.mp4"))
    
    if not video_files:
        raise YouTubeUploadError(f"未找到视频文件: {episode_dir}")
    
    video_path = video_files[0]
    
    # 读取元数据
    metadata = read_youtube_metadata(episode_dir, episode_id)
    
    # 更新状态为uploading（如果启用）
    if update_state:
        try:
            from core.state_manager import get_state_manager
            from core.event_bus import get_event_bus
            state_manager = get_state_manager()
            event_bus = get_event_bus()
            
            # 触发上传开始事件
            event_bus.emit_upload_started(episode_id)
        except Exception as e:
            print(f"⚠️  状态更新失败（不影响上传）: {e}")
    
    # 执行上传
    try:
        result = upload_video(
            video_path=video_path,
            title=metadata["title"],
            description=metadata["description"],
            privacy_status=privacy_status,
            subtitle_path=Path(metadata["subtitle_path"]) if metadata["subtitle_path"] else None,
            thumbnail_path=Path(metadata["thumbnail_path"]) if metadata["thumbnail_path"] else None,
            episode_id=episode_id
        )
        
        # 保存上传日志
        save_upload_log(result, episode_dir)
        
        # 更新状态为completed（如果启用）
        if update_state:
            try:
                from core.state_manager import get_state_manager
                from core.event_bus import get_event_bus
                state_manager = get_state_manager()
                event_bus = get_event_bus()
                
                # 触发上传完成事件
                event_bus.emit_upload_completed(episode_id, result["video_id"], result["video_url"])
            except Exception as e:
                print(f"⚠️  状态更新失败: {e}")
        
        return result
    
    except Exception as e:
        # 更新状态为error（如果启用）
        if update_state:
            try:
                from core.state_manager import get_state_manager
                from core.event_bus import get_event_bus
                state_manager = get_state_manager()
                event_bus = get_event_bus()
                
                # 触发上传失败事件
                event_bus.emit_upload_failed(episode_id, str(e))
            except Exception:
                pass
        
        raise


def main():
    parser = argparse.ArgumentParser(description="YouTube视频上传工具")
    parser.add_argument("--setup", action="store_true", help="运行OAuth配置向导")
    parser.add_argument("--episode-dir", type=Path, help="期数目录路径")
    parser.add_argument("--episode-id", help="期数ID（如20251102）")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default=DEFAULT_PRIVACY_STATUS, help="视频可见性")
    parser.add_argument("--no-state", action="store_true", help="不更新状态管理器")
    
    args = parser.parse_args()
    
    # 设置模式
    if args.setup:
        setup_auth()
        return
    
    # 检查认证
    if not check_auth_status():
        print("❌ 未通过认证")
        print("💡 请先运行: python scripts/local_picker/youtube_upload.py --setup")
        sys.exit(1)
    
    # 确定期数目录和ID
    if args.episode_dir:
        episode_dir = args.episode_dir
        if not args.episode_id:
            # 从目录名提取ID（假设格式为 YYYY-MM-DD_Title 或 YYYYMMDD_Title）
            dir_name = episode_dir.name
            if len(dir_name) >= 8:
                args.episode_id = dir_name[:8]  # 前8位应该是日期
    else:
        print("❌ 请指定期数目录: --episode-dir <path>")
        sys.exit(1)
    
    if not args.episode_id:
        print("❌ 请指定期数ID: --episode-id <YYYYMMDD>")
        sys.exit(1)
    
    # 执行上传
    try:
        result = upload_episode(
            episode_dir=episode_dir,
            episode_id=args.episode_id,
            privacy_status=args.privacy,
            update_state=not args.no_state
        )
        
        print()
        print("=" * 70)
        print("✅ 上传完成！")
        print("=" * 70)
        print(f"Video ID: {result['video_id']}")
        print(f"Video URL: {result['video_url']}")
        print(f"上传时间: {result['upload_time']}")
        print()
        
    except Exception as e:
        print(f"❌ 上传失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

