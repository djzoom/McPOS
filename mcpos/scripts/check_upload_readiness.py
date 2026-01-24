#!/usr/bin/env python3
"""
检查期数上传前的所有必需文件

用法:
    python -m mcpos.scripts.check_upload_readiness <channel_id> <episode_id>
    
示例:
    python -m mcpos.scripts.check_upload_readiness kat kat_20250108
"""

import sys
import json
from pathlib import Path
from typing import List, Tuple

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mcpos.adapters.filesystem import build_asset_paths
from mcpos.adapters.uploader import _ensure_video_asset_ok, _probe_video_asset
from mcpos.models import EpisodeSpec
from mcpos.config import get_config
from mcpos.core.logging import log_info, log_error, log_warning


def check_file_exists(file_path: Path, name: str) -> Tuple[bool, str]:
    """检查文件是否存在"""
    if not file_path.exists():
        return False, f"❌ {name} 缺失: {file_path}"
    
    if not file_path.is_file():
        return False, f"❌ {name} 不是文件: {file_path}"
    
    size = file_path.stat().st_size
    if size == 0:
        return False, f"❌ {name} 文件大小为 0: {file_path}"
    
    return True, f"✅ {name} 存在 (大小: {size:,} 字节): {file_path}"


def check_text_file_content(file_path: Path, name: str, required: bool = True) -> Tuple[bool, str]:
    """检查文本文件内容"""
    exists, msg = check_file_exists(file_path, name)
    if not exists:
        return False, msg
    
    try:
        content = file_path.read_text(encoding="utf-8").strip()
        if required and not content:
            return False, f"❌ {name} 文件内容为空: {file_path}"
        
        return True, f"✅ {name} 内容有效 (长度: {len(content)} 字符): {file_path}"
    except Exception as e:
        return False, f"❌ {name} 读取失败: {e}"


def check_tags_file(file_path: Path) -> Tuple[bool, str]:
    """检查标签文件"""
    exists, msg = check_file_exists(file_path, "标签文件")
    if not exists:
        return False, msg
    
    try:
        tags = [
            line.strip()
            for line in file_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not tags:
            return False, f"❌ 标签文件没有有效标签: {file_path}"
        
        return True, f"✅ 标签文件有效 (标签数: {len(tags)}): {file_path}"
    except Exception as e:
        return False, f"❌ 标签文件读取失败: {e}"


def check_video_file(video_path: Path) -> Tuple[bool, str]:
    """检查视频文件（包括 ffprobe 校验）"""
    exists, msg = check_file_exists(video_path, "视频文件")
    if not exists:
        return False, msg
    
    # 使用 ffprobe 进行深入校验
    ok, probe_error = _probe_video_asset(video_path, None)
    if not ok:
        return False, f"❌ 视频文件 ffprobe 校验失败: {probe_error or 'unknown error'}"
    
    return True, f"✅ 视频文件通过 ffprobe 校验: {video_path}"


def check_upload_result_json(json_path: Path) -> Tuple[bool, str]:
    """检查上传结果 JSON 文件"""
    exists, msg = check_file_exists(json_path, "上传结果 JSON")
    if not exists:
        return False, msg
    
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        video_id = data.get("video_id")
        if not video_id:
            return False, f"❌ 上传结果 JSON 缺少 video_id: {json_path}"
        
        video_url = data.get("video_url") or f"https://www.youtube.com/watch?v={video_id}"
        return True, f"✅ 上传结果 JSON 有效 (video_id: {video_id}, URL: {video_url}): {json_path}"
    except json.JSONDecodeError as e:
        return False, f"❌ 上传结果 JSON 格式无效: {e}"
    except Exception as e:
        return False, f"❌ 上传结果 JSON 读取失败: {e}"


def check_episode_upload_readiness(channel_id: str, episode_id: str, check_upload_result: bool = False) -> bool:
    """
    检查期数是否准备好上传
    
    Args:
        channel_id: 频道 ID
        episode_id: 期数 ID
        check_upload_result: 是否检查上传结果（上传后验证）
    
    Returns:
        True 如果所有检查通过，False 否则
    """
    spec = EpisodeSpec(channel_id=channel_id, episode_id=episode_id)
    config = get_config()
    paths = build_asset_paths(spec, config)
    
    print(f"\n检查期数: {channel_id}/{episode_id}")
    print(f"输出目录: {paths.episode_output_dir}\n")
    
    all_ok = True
    
    if check_upload_result:
        # 上传后验证
        print("=" * 60)
        print("上传后验证")
        print("=" * 60)
        
        upload_json = paths.episode_output_dir / f"{episode_id}_youtube_upload.json"
        upload_flag = paths.upload_complete_flag
        
        ok, msg = check_upload_result_json(upload_json)
        print(msg)
        if not ok:
            all_ok = False
        
        ok, msg = check_file_exists(upload_flag, "上传完成标记")
        print(msg)
        if not ok:
            all_ok = False
    else:
        # 上传前检查
        print("=" * 60)
        print("上传前检查")
        print("=" * 60)
        
        # 1. 视频文件检查
        print("\n[1] 视频文件检查")
        ok, msg = check_video_file(paths.youtube_mp4)
        print(msg)
        if not ok:
            all_ok = False
        
        # 2. 元数据文件检查
        print("\n[2] 元数据文件检查")
        ok, msg = check_text_file_content(paths.youtube_title_txt, "标题文件", required=True)
        print(msg)
        if not ok:
            all_ok = False
        
        ok, msg = check_text_file_content(paths.youtube_description_txt, "描述文件", required=False)
        print(msg)
        if not ok:
            all_ok = False
        
        ok, msg = check_tags_file(paths.youtube_tags_txt)
        print(msg)
        if not ok:
            all_ok = False
        
        # 3. 字幕文件检查
        print("\n[3] 字幕文件检查")
        ok, msg = check_text_file_content(paths.youtube_srt, "字幕文件", required=True)
        print(msg)
        if not ok:
            all_ok = False
        
        # 4. 可选文件检查
        print("\n[4] 可选文件检查")
        ok, msg = check_file_exists(paths.cover_png, "封面文件（可选）")
        print(msg)
        # 封面文件是可选的，不影响上传
    
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ 所有检查通过")
        return True
    else:
        print("❌ 部分检查失败，请修复后重试")
        return False


def main():
    """主函数"""
    if len(sys.argv) < 3:
        print("用法: python -m mcpos.scripts.check_upload_readiness <channel_id> <episode_id> [--check-upload]")
        print("\n选项:")
        print("  --check-upload    检查上传结果（上传后验证）")
        print("\n示例:")
        print("  python -m mcpos.scripts.check_upload_readiness kat kat_20250108")
        print("  python -m mcpos.scripts.check_upload_readiness kat kat_20250108 --check-upload")
        sys.exit(1)
    
    channel_id = sys.argv[1]
    episode_id = sys.argv[2]
    check_upload_result = "--check-upload" in sys.argv
    
    try:
        success = check_episode_upload_readiness(channel_id, episode_id, check_upload_result)
        sys.exit(0 if success else 1)
    except Exception as e:
        log_error(f"检查失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
