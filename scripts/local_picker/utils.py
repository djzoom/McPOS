#!/usr/bin/env python3
# coding: utf-8
"""
共享工具函数，避免代码重复
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def extract_title_from_playlist(playlist_path: Path) -> Optional[str]:
    """
    从歌单CSV中提取标题（AlbumTitle 或 Title 字段）
    
    Args:
        playlist_path: 歌单CSV文件路径
        
    Returns:
        提取的标题，如果失败则返回 None
    """
    try:
        import csv
        with playlist_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if (row.get("Section") or "").strip() == "Metadata":
                    field = (row.get("Field") or "").strip()
                    # 尝试 AlbumTitle 或 Title
                    if field in ("AlbumTitle", "Title"):
                        title = (row.get("Value") or "").strip()
                        if title:
                            return title
    except Exception as e:
        print(f"⚠️  读取标题失败 {playlist_path}: {e}")
    return None


def get_final_output_dir(
    schedule_date: datetime,
    title: str
) -> Path:
    """
    获取最终输出目录（打包文件夹）
    
    Args:
        schedule_date: 排播日期 (datetime对象)
        title: 唱片标题
    
    Returns:
        最终文件夹路径: output/{YYYY-MM-DD}_{标题}/
    
    Raises:
        ValueError: 如果标题无效
    """
    from src.core.path_utils import safe_join_path, sanitize_path_component
    
    date_str = schedule_date.strftime("%Y-%m-%d")
    
    # 使用安全的路径组件清理
    safe_title = sanitize_path_component(title)
    # 进一步处理：只保留字母数字、空格、连字符和下划线
    safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in safe_title)
    safe_title = safe_title.strip().replace(" ", "_")[:50]  # 限制长度
    
    if not safe_title:
        raise ValueError(f"Title sanitization resulted in empty string: {title}")
    
    folder_name = f"{date_str}_{safe_title}"
    
    # 使用安全的路径连接
    base_output = (REPO_ROOT / "output").resolve()
    return safe_join_path(base_output, folder_name)

