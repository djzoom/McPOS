#!/usr/bin/env python3
# coding: utf-8
"""
从曲库生成符合 Google Apps Script 逻辑的 AB 面歌单，并输出标题、封面提示词与简易封面。

使用方式：
    python scripts/local_picker/create_mixtape.py \
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json as _json
import os
import random
import shutil
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Set

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

# 尝试导入rich库用于进度显示
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
    from rich.spinner import Spinner
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# 将项目根目录加入 sys.path，确保可导入 src/* 模块
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

# 路径常量 (相对于项目根目录)
# 注意：OUTPUT_PLAYLIST_DIR 和 OUTPUT_COVER_DIR 仅作为向后兼容的回退路径
# 实际代码已使用统一的 output/{id_str}_{title}/ 目录结构
OUTPUT_PLAYLIST_DIR = REPO_ROOT / "output/playlists"  # 已弃用，仅作兼容
OUTPUT_COVER_DIR = REPO_ROOT / "output/cover"  # 已弃用，仅作兼容
FONT_DIR = REPO_ROOT / "assets/fonts"
DESIGN_DIR = REPO_ROOT / "assets/design"
CONFIG_DIR = REPO_ROOT / "config"

from src.creation_utils import (
    get_dominant_color,
    # generate_poetic_title removed: no longer using local fallback
    sanitize_title,
    to_title_case,
    select_vivid_dark_color,
)


def get_output_dir(id_str: str, title: str, schedule_date: Optional[dt.datetime] = None) -> Path:
    """
    获取输出目录路径（过程文件暂存目录）
    
    现在所有过程文件先输出到output根目录，资料齐了后会打包到最终文件夹
    
    Args:
        id_str: ID字符串（如 "20250101"）
        title: 唱片标题
        schedule_date: 排播日期（用于最终打包文件夹名）
    
    Returns:
        临时输出目录路径（output根目录）
    """
        # 过程文件暂存在output根目录
    return REPO_ROOT / "output"


# 注意：get_final_output_dir 已移至 utils.py，这里保留兼容性导入
# 如果需要修改逻辑，请更新 utils.py
try:
    from utils import get_final_output_dir
except ImportError:
    # 回退实现（兼容性）
    def get_final_output_dir(schedule_date: dt.datetime, title: str) -> Path:
        """获取最终打包文件夹路径（已移至 utils.py，此函数仅为兼容性保留）"""
        base = REPO_ROOT / "output"
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()[:50]
        safe_title = safe_title.replace(" ", "_")
        date_str = schedule_date.strftime("%Y-%m-%d")
        folder_name = f"{date_str}_{safe_title}"
        return base / folder_name

# 其他常量
MIN_DURATION = 30 * 60  # 1800 s
MAX_DURATION = 1850
CANVAS_SIZE_8K = (7680, 4320)
CANVAS_SIZE_4K = (3840, 2160)
SCALE_4K = 0.5


@dataclass
class Track:
    title: str
    duration_sec: int

    @property
    def duration_str(self) -> str:
        minutes, seconds = divmod(self.duration_sec, 60)
        return f"{minutes}:{seconds:02d}"


def load_tracklist(path: Path) -> List[Track]:
    if not path.exists():
        raise FileNotFoundError(f"找不到曲库文件：{path}")
    suffix = path.suffix.lower()
    delimiter = "\t" if suffix in {".tsv", ".txt"} else ","

    tracks: List[Track] = []
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        header = next(reader, None)
        if header is None:
            return tracks

        def norm_header(h: str) -> str:
            return h.strip().lower()

        columns = [norm_header(col) for col in header]
        try:
            # 检查并映射字段名
            if 'title' in columns:
                name_idx = columns.index('title')
            elif 'name' in columns:
                name_idx = columns.index('name')
            else:
                raise ValueError('未找到名称字段')

            if 'duration_seconds' in columns:
                duration_idx = columns.index('duration_seconds')
            elif 'duration' in columns:
                duration_idx = columns.index('duration')
            else:
                raise ValueError('未找到时长字段')
        except ValueError as exc:
            raise ValueError(f"曲库文件缺少所需字段，当前字段：{columns}") from exc

        for row in reader:
            if len(row) <= max(name_idx, duration_idx):
                continue
            name = row[name_idx].strip()
            duration_raw = row[duration_idx].strip()
            if not name or not duration_raw:
                continue
            try:
                duration_sec = parse_duration(duration_raw)
            except ValueError:
                continue
            if duration_sec <= 0:
                continue
            tracks.append(Track(title=name, duration_sec=duration_sec))
    if not tracks:
        raise ValueError("曲库文件解析后没有有效曲目")
    return tracks


def parse_duration(value: str) -> int:
    # 先尝试浮点数（常见格式，如99.912）
    try:
        return int(float(value))
    except (ValueError, TypeError):
        pass
    # 尝试整数
    if value.isdigit():
        return int(value)
    # 尝试时分秒格式（mm:ss 或 hh:mm:ss）
    parts = value.split(":")
    try:
        parts_int = [int(p) for p in parts]
    except ValueError as exc:
        raise ValueError(f"无法解析时长：{value}") from exc
    if len(parts_int) == 2:
        m, s = parts_int
        return m * 60 + s
    if len(parts_int) == 3:
        h, m, s = parts_int
        return h * 3600 + m * 60 + s
    raise ValueError(f"无法解析时长：{value}")


def select_tracks(
    tracks: Sequence[Track], 
    seed: int = 42,
    excluded_tracks: Optional[Set[str]] = None,
    excluded_starting_tracks: Optional[Set[str]] = None,
    all_used_tracks: Optional[Set[str]] = None,
    new_track_ratio: float = 0.7
) -> Tuple[List[Track], List[Track]]:
    """
    选择曲目，支持排除已使用的曲目和起始曲目
    优先使用新歌，但穿插旧歌以保持平衡
    
    Args:
        tracks: 曲库
        seed: 随机种子
        excluded_tracks: 要排除的曲目标题集合（避免临近期数重复）
        excluded_starting_tracks: 要排除的起始曲目标题集合（确保起始曲目独特）
        all_used_tracks: 所有已使用的歌曲（用于识别新歌）
        new_track_ratio: 新歌比例（默认70%）
    """
    pool = list(tracks)
    rng = random.Random(seed)
    
    # 分离新歌和旧歌
    new_tracks: List[Track] = []
    old_tracks: List[Track] = []
    
    if all_used_tracks:
        for track in pool:
            # 排除临近期数使用的歌曲
            if excluded_tracks and track.title in excluded_tracks:
                continue
            # 分离新歌和旧歌
            if track.title not in all_used_tracks:
                new_tracks.append(track)
            else:
                old_tracks.append(track)
    else:
        # 如果没有使用历史，全部视为新歌
        new_tracks = [t for t in pool if not excluded_tracks or t.title not in excluded_tracks]
        old_tracks = []
    
    # 先打乱新歌和旧歌列表（在选择起始曲目之前）
    rng.shuffle(new_tracks)
    rng.shuffle(old_tracks)
    
    # 确保起始曲目独特（必须排除已使用的起始曲目）
    # 注意：excluded_starting_tracks 可能是空集合，需要检查是否为空
    starting_candidate = None
    if excluded_starting_tracks is not None and len(excluded_starting_tracks) > 0:
        # 调试输出（只在列表较小时显示，避免刷屏）
        if len(excluded_starting_tracks) <= 10:
            excluded_list = sorted(excluded_starting_tracks)
            print(f"[选曲] 调试：排除起始曲目列表 ({len(excluded_list)} 首): {excluded_list[:5]}{'...' if len(excluded_list) > 5 else ''}")
        
        new_starting = [t for t in new_tracks if t.title not in excluded_starting_tracks]
        old_starting = [t for t in old_tracks if t.title not in excluded_starting_tracks]
        
        # 优先使用新歌作为起始曲目
        if new_starting:
            starting_candidate = new_starting[0]
            new_tracks.remove(starting_candidate)
            print(f"[选曲] 起始曲目（新歌）：{starting_candidate.title}")
        elif old_starting:
            starting_candidate = old_starting[0]
            old_tracks.remove(starting_candidate)
            print(f"[选曲] 起始曲目（旧歌）：{starting_candidate.title}")
        else:
            # 如果所有候选曲目都被排除了，仍然需要选择一首（从剩余的新歌或旧歌中选择）
            # 这种情况理论上不应该发生，因为排播表应该不会用完所有歌曲
            if new_tracks:
                starting_candidate = new_tracks[0]
                new_tracks.remove(starting_candidate)
                print(f"[选曲] ⚠️  警告：所有候选起始曲目都被排除，使用新歌: {starting_candidate.title}")
            elif old_tracks:
                starting_candidate = old_tracks[0]
                old_tracks.remove(starting_candidate)
                print(f"[选曲] ⚠️  警告：所有候选起始曲目都被排除，使用旧歌: {starting_candidate.title}")
            else:
                raise ValueError("无法选择起始曲目：所有曲目都被排除了")
    elif excluded_starting_tracks is not None:
        # excluded_starting_tracks 是空集合，不需要排除，直接选择第一首新歌
        if new_tracks:
            starting_candidate = new_tracks[0]
            new_tracks.remove(starting_candidate)
            print(f"[选曲] 起始曲目（新歌）：{starting_candidate.title} (排除列表为空)")
        elif old_tracks:
            starting_candidate = old_tracks[0]
            old_tracks.remove(starting_candidate)
            print(f"[选曲] 起始曲目（旧歌）：{starting_candidate.title} (排除列表为空)")
    else:
        # excluded_starting_tracks 为 None，不需要排除，直接选择第一首新歌
        if new_tracks:
            starting_candidate = new_tracks[0]
            new_tracks.remove(starting_candidate)
            print(f"[选曲] 起始曲目（新歌）：{starting_candidate.title}")
        elif old_tracks:
            starting_candidate = old_tracks[0]
            old_tracks.remove(starting_candidate)
            print(f"[选曲] 起始曲目（旧歌）：{starting_candidate.title}")
    
    # 按比例混合新歌和旧歌（优先新歌，穿插旧歌）
    mixed_pool: List[Track] = []
    new_idx = 0
    old_idx = 0
    target_new_count = int(26 * new_track_ratio)  # 目标新歌数量
    current_new_count = 0
    
    # 智能穿插：确保新歌和旧歌均匀分布
    # 计算穿插模式：每添加N首新歌后，添加1首旧歌
    if len(old_tracks) > 0 and target_new_count > 0:
        # 例如：70%新歌 = 18首新歌 + 8首旧歌
        # 穿插模式：每2-3首新歌后1首旧歌
        new_per_old = max(1, target_new_count // max(1, 26 - target_new_count))
    else:
        new_per_old = 100  # 如果没有旧歌或全是新歌，全部添加新歌
    
    # 交替添加，自然穿插
    while len(mixed_pool) < 26 and (new_idx < len(new_tracks) or old_idx < len(old_tracks)):
        # 检查是否需要添加旧歌（穿插逻辑）
        need_old = (old_idx < len(old_tracks) and 
                   current_new_count >= new_per_old and 
                   len(mixed_pool) - current_new_count < (26 - target_new_count))
        
        # 检查是否还需要新歌
        need_new = (new_idx < len(new_tracks) and 
                   current_new_count < target_new_count)
        
        if need_old:
            # 添加旧歌（穿插）
            mixed_pool.append(old_tracks[old_idx])
            old_idx += 1
            # 重置新歌计数，准备下一轮
            current_new_count = 0
        elif need_new:
            # 添加新歌
            mixed_pool.append(new_tracks[new_idx])
            new_idx += 1
            current_new_count += 1
        elif new_idx < len(new_tracks):
            # 如果旧歌已用完或不需要，继续添加新歌
            mixed_pool.append(new_tracks[new_idx])
            new_idx += 1
            current_new_count += 1
        elif old_idx < len(old_tracks):
            # 如果新歌已用完，添加旧歌
            mixed_pool.append(old_tracks[old_idx])
            old_idx += 1
        else:
            break
    
    # 如果混合池不足，从原池补充（排除临近期数）
    if len(mixed_pool) < 26:
        remaining = [t for t in pool if t not in mixed_pool and (not excluded_tracks or t.title not in excluded_tracks)]
        rng.shuffle(remaining)
        mixed_pool.extend(remaining[:26 - len(mixed_pool)])
    
    # 统计
    if all_used_tracks:
        actual_new = sum(1 for t in mixed_pool if t.title not in all_used_tracks)
        actual_old = len(mixed_pool) - actual_new
        print(f"[选曲] 新歌：{actual_new} 首，旧歌：{actual_old} 首（目标比例：{new_track_ratio:.0%} 新歌）")
    
    pool = mixed_pool
    
    # 关键修复：确保起始曲目在混合池的第一个位置
    # 这样它会被第一个分配到 side_a[0]
    if starting_candidate and starting_candidate in pool:
        # 如果起始曲目在池中，移除它并放到第一个位置
        pool.remove(starting_candidate)
        pool.insert(0, starting_candidate)
        print(f"[选曲] ✅ 起始曲目已固定到第一个位置: {starting_candidate.title}")
    elif starting_candidate:
        # 如果起始曲目不在池中（理论上不应该发生），添加到第一个位置
        pool.insert(0, starting_candidate)
        print(f"[选曲] ⚠️  警告：起始曲目不在池中，已添加到第一个位置: {starting_candidate.title}")

    side_a: List[Track] = []
    side_b: List[Track] = []
    total_a = 0
    total_b = 0

    for track in pool:
        added = False
        if total_a < MIN_DURATION and total_a + track.duration_sec <= MAX_DURATION:
            side_a.append(track)
            total_a += track.duration_sec
            added = True
        elif total_b < MIN_DURATION and total_b + track.duration_sec <= MAX_DURATION:
            side_b.append(track)
            total_b += track.duration_sec
            added = True
        if total_a >= MIN_DURATION and total_b >= MIN_DURATION:
            break

    # 如果仍不满足，尝试宽松填充
    if total_a < MIN_DURATION or total_b < MIN_DURATION:
        for track in pool:
            if track in side_a or track in side_b:
                continue
            if total_a < MIN_DURATION:
                side_a.append(track)
                total_a += track.duration_sec
            elif total_b < MIN_DURATION:
                side_b.append(track)
                total_b += track.duration_sec
            if total_a >= MIN_DURATION and total_b >= MIN_DURATION:
                break
    
    # 最终验证：确保起始曲目在 side_a[0] 位置
    if starting_candidate and side_a:
        if side_a[0].title != starting_candidate.title:
            # 如果起始曲目不在 side_a[0]，找到它并移动到第一个位置
            for i, track in enumerate(side_a):
                if track.title == starting_candidate.title:
                    side_a.pop(i)
                    side_a.insert(0, track)
                    print(f"[选曲] ✅ 已修正起始曲目位置: {starting_candidate.title}")
                    break
            # 如果没在 side_a 中找到，尝试从 side_b 移到 side_a[0]
            if side_a[0].title != starting_candidate.title:
                for i, track in enumerate(side_b):
                    if track.title == starting_candidate.title:
                        side_b.pop(i)
                        side_a.insert(0, track)
                        print(f"[选曲] ✅ 已从 side_b 移到 side_a[0]: {starting_candidate.title}")
                        break

    return side_a, side_b


def select_tracks_by_count(tracks: Sequence[Track], total_count: int, seed: int = 42) -> Tuple[List[Track], List[Track]]:
    """按曲目数量选择，不考虑时长。将前一半分配到 A，后一半分配到 B。

    - 从曲库随机打乱后取 total_count 首
    - A 面分配 ceil(total/2)，B 面分配其余
    """
    pool = list(tracks)
    rng = random.Random(seed)
    rng.shuffle(pool)
    chosen = pool[: max(0, total_count)]
    split_a = (len(chosen) + 1) // 2
    side_a = chosen[:split_a]
    side_b = chosen[split_a:]
    return side_a, side_b


def enforce_track_count_constraints(
    side_a: List[Track], side_b: List[Track]
) -> Tuple[List[Track], List[Track]]:
    """限制总曲目数与 A/B 面分布：
    - 总数最大 26
    - 若出现 A/B 均 >=13（即 13/13 或更大），则减少一首使之不同时 >=13
    """
    total = len(side_a) + len(side_b)
    # 限制总数 <= 26（若超出，从较长的一面尾部裁掉）
    while total > 26:
        if len(side_a) >= len(side_b) and side_a:
            side_a.pop()
        elif side_b:
            side_b.pop()
        total = len(side_a) + len(side_b)
    # 若恰好 13/13，则去掉一首（优先去 B 面）→ 13/12
    if len(side_a) >= 13 and len(side_b) >= 13:
        if len(side_b) >= len(side_a) and side_b:
            side_b.pop()
        elif side_a:
            side_a.pop()
    return side_a, side_b


def _try_api_title(
    image_filename: str,
    dominant_rgb: Tuple[int, int, int],
    playlist_keywords: List[str],
    seed: int,
    api_key: str,
    base_url: str,
    model: str,
    provider: str = "openai",
) -> str | None:
    """
    调用API生成标题（支持OpenAI和Gemini）
    
    Returns sanitized string or None on failure.
    """
    try:
        import json as _json
        from urllib import request as _req

        sys_prompt = (
            "You write short poetic album titles for cozy lo-fi music. "
            "Return only the title in English, AT MOST 7 WORDS (strictly enforced), "
            "the title MUST be a complete expression (even if just one word). "
            "NEVER return incomplete or truncated titles. "
            "Avoid punctuation, be concise and evocative. "
            "STRICTLY AVOID these overused phrases: "
            "'soft sigh', 'did you dream of', 'lost in...found in', "
            "'unseen depths', 'slow blink', 'whispers of fur', "
            "'velvet paws', 'curled up', 'nestled deep'. "
            "Be creative, use fresh vocabulary, and avoid repetitive patterns. "
            "Each title must be unique and distinct from previous ones."
        )
        user_prompt = (
            f"image: {image_filename}\n"
            f"color_rgb: {dominant_rgb}\n"
            f"keywords: {', '.join(playlist_keywords[:20])}\n"
            f"seed: {seed}"
        )
        
        if provider == "openai":
            payload = {
                "model": model,
                "temperature": 0.3,
                "max_tokens": 32,  # 增加以支持最多8个词（每个词约2-4个token）
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            data = _json.dumps(payload).encode("utf-8")
            http_req = _req.Request(f"{base_url}/chat/completions", data=data, method="POST")
            http_req.add_header("Content-Type", "application/json")
            http_req.add_header("Authorization", f"Bearer {api_key}")
            
            # 使用 certifi 的证书文件（解决 macOS SSL 证书问题）
            import ssl as _ssl
            try:
                import certifi as _certifi
                ssl_context = _ssl.create_default_context(cafile=_certifi.where())
            except ImportError:
                ssl_context = _ssl.create_default_context()
            
            with _req.urlopen(http_req, timeout=10, context=ssl_context) as resp:
                body = _json.loads(resp.read().decode("utf-8"))
            
            text: str | None = None
            if isinstance(body, dict):
                choices = body.get("choices") or []
                if choices and isinstance(choices, list):
                    msg = choices[0].get("message") or {}
                    text = (msg.get("content") or "").strip() or None
        
        elif provider == "gemini":
            # Gemini API格式
            prompt = f"{sys_prompt}\n\n{user_prompt}"
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 32,  # 增加以支持最多8个词
                }
            }
            data = _json.dumps(payload).encode("utf-8")
            http_req = _req.Request(
                f"{base_url}/{model}:generateContent?key={api_key}",
                data=data,
                method="POST"
            )
            http_req.add_header("Content-Type", "application/json")
            
            # 使用 certifi 的证书文件（解决 macOS SSL 证书问题）
            import ssl as _ssl
            try:
                import certifi as _certifi
                ssl_context = _ssl.create_default_context(cafile=_certifi.where())
            except ImportError:
                ssl_context = _ssl.create_default_context()
            
            with _req.urlopen(http_req, timeout=10, context=ssl_context) as resp:
                body = _json.loads(resp.read().decode("utf-8"))
            
            text: str | None = None
            if isinstance(body, dict):
                candidates = body.get("candidates") or []
                if candidates and isinstance(candidates, list):
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        text = parts[0].get("text", "").strip() or None
        
        else:
            print(f"[WARN] 不支持的API提供商: {provider}")
            return None
        
        if text:
            title = to_title_case(sanitize_title(text))
            # 验证标题长度：最多7个词，且必须是完整表达
            words = title.split()
            if len(words) > 7:
                # 如果超过7个词，返回None让调用者重新生成
                print(f"[WARN] 标题超过7个词（{len(words)}词），需要重新生成: {title}")
                return None
            return title
    except Exception as _e:
        print(f"[WARN] API 标题生成失败 ({provider}): {_e}")
    return None


# 向后兼容的别名
def _try_openai_title(
    image_filename: str,
    dominant_rgb: Tuple[int, int, int],
    playlist_keywords: List[str],
    seed: int,
    api_key: str,
    model: str = "gpt-4o-mini",
) -> str | None:
    """向后兼容的OpenAI标题生成函数"""
    from api_config import get_api_base_url
    base_url = get_api_base_url("openai")
    return _try_api_title(image_filename, dominant_rgb, playlist_keywords, seed, api_key, base_url, model, "openai")


# ====== Text color selection (WCAG-based) ======
def _srgb_to_linear(component: int) -> float:
    c = component / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb: Tuple[int, int, int]) -> float:
    r, g, b = rgb
    R = _srgb_to_linear(r)
    G = _srgb_to_linear(g)
    B = _srgb_to_linear(b)
    return 0.2126 * R + 0.7152 * G + 0.0722 * B


def _contrast_ratio(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
    L1 = _relative_luminance(rgb1)
    L2 = _relative_luminance(rgb2)
    L1, L2 = (L1, L2) if L1 >= L2 else (L2, L1)
    return (L1 + 0.05) / (L2 + 0.05)


def _pick_text_color(bg_rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    light = (250, 250, 250)      # near-white（偏暖白）
    gray_dark = (60, 60, 60)     # 浅灰偏深（更柔和，比纯黑优雅）
    c_light = _contrast_ratio(bg_rgb, light)
    c_gray = _contrast_ratio(bg_rgb, gray_dark)
    L = _relative_luminance(bg_rgb)
    # 美学优先：更多白字。仅当背景“极亮且接近白纸”才换浅灰，避免过度黑字。
    # 1) 背景极亮（≈白纸）：改用浅灰，避免白字糊在一起
    if L >= 0.96:
        return gray_dark
    # 2) 白字阈值放宽（>=2.4:1 即可），考虑做旧蒙版后肉眼对比更高
    if c_light >= 2.4:
        return light
    # 3) 白字不足而浅灰明显更清晰（>=3:1），才用浅灰
    if c_gray >= 3.0 and c_gray > c_light:
        return gray_dark
    # 4) 其余情况倾向白字
    return light


def format_mmss(total_seconds: int) -> str:
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def export_playlist(
    side_a: Sequence[Track],
    side_b: Sequence[Track],
    title: str,
    color_hex: str,
    prompt: str,
    needle_timeline: Sequence[Dict[str, str]],
    clean_timeline: Sequence[Dict[str, str]],
    title_source: str = "local",
    output_dir: Path | None = None,
    id_str: str | None = None,
) -> Path:
    if output_dir is None:
        output_dir = OUTPUT_PLAYLIST_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        if id_str:
            filename = f"{id_str}_playlist.csv"
        else:
            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"{timestamp}_mixtape_playlist.csv"
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        if id_str:
            filename = f"{id_str}_playlist.csv"
        else:
            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"{timestamp}_playlist.csv"
    target = output_dir / filename
    total_a = sum(t.duration_sec for t in side_a)
    total_b = sum(t.duration_sec for t in side_b)

    with target.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "Section",
                "Field",
                "Value",
                "Side",
                "Order",
                "Title",
                "Duration",
                "DurationSeconds",
                "Timeline",
                "Timestamp",
                "Description",
            ]
        )

        # 元信息
        writer.writerow(["Metadata", "AlbumTitle", title, "", "", "", "", "", "", "", ""])
        writer.writerow(["Metadata", "ColorHex", f"#{color_hex}", "", "", "", "", "", "", "", ""])
        writer.writerow(["Metadata", "Prompt", prompt, "", "", "", "", "", "", "", ""])
        writer.writerow(["Metadata", "TitleSource", title_source, "", "", "", "", "", "", "", ""])

        # 摘要
        writer.writerow(
            [
                "Summary",
                "SideTotal",
                f"{len(side_a)} tracks",
                "A",
                "",
                "",
                format_mmss(total_a),
                total_a,
                "",
                "",
                "",
            ]
        )
        writer.writerow(
            [
                "Summary",
                "SideTotal",
                f"{len(side_b)} tracks",
                "B",
                "",
                "",
                format_mmss(total_b),
                total_b,
                "",
                "",
                "",
            ]
        )

        # 曲目列表
        for idx, track in enumerate(side_a, start=1):
            writer.writerow(
                [
                    "Track",
                    "",
                    "",
                    "A",
                    idx,
                    track.title,
                    track.duration_str,
                    track.duration_sec,
                    "",
                    "",
                    "",
                ]
            )
        for idx, track in enumerate(side_b, start=1):
            writer.writerow(
                [
                    "Track",
                    "",
                    "",
                    "B",
                    idx,
                    track.title,
                    track.duration_str,
                    track.duration_sec,
                    "",
                    "",
                    "",
                ]
            )

        # 时间轴（Needle）
        for event in needle_timeline:
            writer.writerow(
                [
                    "Timeline",
                    "",
                    "",
                    event["side"],
                    "",
                    "",
                    "",
                    "",
                    "Needle",
                    event["timestamp"],
                    event["description"],
                ]
            )

        # 时间轴（Clean）
        for event in clean_timeline:
            writer.writerow(
                [
                    "Timeline",
                    "",
                    "",
                    event["side"],
                    "",
                    "",
                    "",
                    "",
                    "Clean",
                    event["timestamp"],
                    event["description"],
                ]
            )
    return target


def generate_prompt(title: str, color_hex: str) -> str:
    return textwrap.dedent(
        f"""
        Cozy illustration album cover, warm pastel palette #{color_hex}, lo-fi vinyl aesthetic,
        featuring a gentle cat-themed record nook, soft lighting, bokeh window rain, cinematic depth,
        elegant typography reading "{title}", 4K ultra high definition, minimal grain, whimsical atmosphere.
        """.strip()
    )


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    font_path = FONT_DIR / name
    if not font_path.exists():
        raise FileNotFoundError(f"未找到字体: {font_path}")
    return ImageFont.truetype(str(font_path), size)


def choose_font_path(rng: random.Random) -> Path | None:
    candidates = list(FONT_DIR.glob("*.ttf")) + list(FONT_DIR.glob("*.otf"))
    if not candidates:
        return None
    return rng.choice(candidates)


@dataclass
class CoverLayoutConfig:
    """Configurable layout settings for cover composition.

    All values are fractions relative to the base canvas width/height unless
    otherwise noted. Keep these adjustable to reuse across batches.
    """
    canvas_size: Tuple[int, int] = CANVAS_SIZE_4K
    x_margin_frac: float = 0.08
    y_margin_frac: float = 0.18
    left_block_width_frac: float = 0.38
    spine_width_px: int = int(90 * SCALE_4K)
    spine_x_pos: int = int(3295 * SCALE_4K)
    title_size_frac: float = 0.035
    body_size_frac: float = 0.012
    side_title_size_frac: float = 0.018
    min_title_px: int = int(36 * SCALE_4K)
    min_body_px: int = int(16 * SCALE_4K)
    side_title_x_offset: float = 0.03
    text_opacity: float = 1.0
    title_right_center_frac: float = 0.70
    title_top_margin: int = int(250 * SCALE_4K)


def wrap_track_lines(label: str, tracks: Sequence[Track], width: int = 28) -> List[str]:
    lines = []
    for idx, track in enumerate(tracks, 1):
        # 不换行，所有曲目一行显示
        lines.append(f"{idx:02d}. {track.title}")
    return lines


def compose_cover(
    title: str,
    side_a: Sequence[Track],
    side_b: Sequence[Track],
    color_hex: str,
    seed: int,
    layout: CoverLayoutConfig | None = None,
    spine_x: int | None = None,
    output_name: str | None = None,
    font_name: str | None = None,
    output_size: Tuple[int, int] = CANVAS_SIZE_4K,
    image_path: Path | None = None, # New parameter for image path
    text_style: str = "noise",
    output_dir: Path | None = None,
    id_str: str | None = None,
) -> Path:
    """Compose cover using a layout configuration.

    Key behaviors implemented to match the requested rules:
    - Base canvas is layout.canvas_size (defaults to 7680x4320)
    - Background is single unique color (color_hex)
    - White text at layout.white_opacity used for title and tracklist
    - Title appears once on the right, and once vertically in the center (spine)
    - Song list block stays at left x position; font auto-scales to fit one line per track
    """
    cfg = layout or CoverLayoutConfig()
    # 已移除：OUTPUT_COVER_DIR 的无条件创建，现在使用传入的 output_dir 参数

    width, height = CANVAS_SIZE_4K
    scale = SCALE_4K
    bg_color = tuple(int(color_hex[i : i + 2], 16) for i in (0, 2, 4))
    canvas = Image.new("RGBA", (width, height), bg_color + (255,))

    # 统一文字样式：纯白色，85% 不透明度
    fill_track = (255, 255, 255, 217)
    fill_title_full = (255, 255, 255, 217)

    # ====== 做旧颗粒感叠加 ======
    import numpy as np
    noise_strength = 18  # 噪点强度，建议10~30
    noise_alpha = 32     # 透明度，建议16~48
    noise = np.random.normal(128, noise_strength, (height, width)).clip(0,255).astype(np.uint8)
    noise_img = Image.fromarray(noise, mode="L").convert("RGBA")
    # 设置alpha通道
    alpha = Image.new("L", (width, height), noise_alpha)
    noise_img.putalpha(alpha)
    # 叠加到主画布
    canvas = Image.alpha_composite(canvas, noise_img)

    # 支持直接传参指定字体名和是否标注
    font_path = None
    if font_name:
        for f in FONT_DIR.iterdir():
            if f.stem == font_name and f.suffix.lower() in {'.ttf','.otf'}:
                font_path = f
                break
        if not font_path:
            raise FileNotFoundError(f"未找到字体: {font_name}")
    rng = random.Random(seed + 17)
    if not font_path:
        font_path = choose_font_path(rng)

    # 主图等比缩放，裁切并粘贴到指定区域（左上角1885,282，宽1746高1599）
    try:
        if not image_path:
            raise ValueError("Image path must be provided to compose_cover.")
        if not image_path.exists():
            raise FileNotFoundError(f"Configured default image not found: {image_path}")
        img = Image.open(image_path).convert("RGBA")
        # 区域参数
        box_x, box_y = 1885, 282
        box_w, box_h = 1746, 1599
        img_ratio = img.width / img.height
        box_ratio = box_w / box_h
        if img_ratio > box_ratio:
            # 主图更扁，按高度拉伸，左右裁切
            img_scale = box_h / img.height
            new_w = int(img.width * img_scale)
            img_resized = img.resize((new_w, box_h), Image.LANCZOS)
            left = (new_w - box_w) // 2
            img_cropped = img_resized.crop((left, 0, left + box_w, box_h))
        else:
            # 主图更高，按宽度拉伸，上下裁切
            img_scale = box_w / img.width
            new_h = int(img.height * img_scale)
            img_resized = img.resize((box_w, new_h), Image.LANCZOS)
            top = (new_h - box_h) // 2
            img_cropped = img_resized.crop((0, top, box_w, top + box_h))
        # 使用 paste 并携带自身 alpha 作为蒙版，正确贴到 (box_x, box_y)
        canvas.paste(img_cropped, (box_x, box_y), img_cropped)
    except Exception as e:
        print(f"[WARN] 粘贴主插图失败: {e}")
    base_title_px = max(cfg.min_title_px, int(height * cfg.title_size_frac))
    base_body_px = max(cfg.min_body_px, int(height * cfg.body_size_frac))

    # 定义left_block_w用于后续宽度计算
    left_block_w = int(width * cfg.left_block_width_frac)

    # （已移除随机贴图，仅保留主图）

    # Try to load fonts; fallback to Arial-like system font
    try:
        if font_path:
            print(f"使用字体：{font_path}")
            # We'll instantiate actual fonts later after autoscaling
            chosen_font_path = str(font_path)
        else:
            raise FileNotFoundError
    except (OSError, FileNotFoundError):
        chosen_font_path = None

    text_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_overlay)

    x_margin = int(width * cfg.x_margin_frac)
    y_margin = int(height * cfg.y_margin_frac)

    # 主标题直接用正文自适应得到的side_title_font，保证与歌单一致
    current_y = y_margin


    # 歌单行内容先定义，供字号自适应测量用
    # 始终以AB各12首（24行）为基准，保证字体不会因曲目少而过大
    max_tracks_per_side = 12
    fake_side_a = side_a[:max_tracks_per_side] + [Track(title="", duration_sec=0)] * max(0, max_tracks_per_side - len(side_a))
    fake_side_b = side_b[:max_tracks_per_side] + [Track(title="", duration_sec=0)] * max(0, max_tracks_per_side - len(side_b))
    side_a_lines = wrap_track_lines("A", fake_side_a)
    side_b_lines = wrap_track_lines("B", fake_side_b)

    # 歌单区块严格限制在主图左侧蓝色区域
    # 主图左上角x=1885，蓝色区域宽=1885像素
    # 主图左上角x=1885，主图下边缘y=282+1599=1881
    # 歌单区块参数固定为用户指定
    block_x = 251
    block_y = 225
    block_w = 1100
    block_h = 1400

    # 自动适配字号：最大化填满block_h且不超宽
    def measure_block(font_size):
        try:
            body_font = ImageFont.truetype(chosen_font_path, font_size) if chosen_font_path else ImageFont.truetype("Arial.ttf", font_size)
            side_title_font = ImageFont.truetype(chosen_font_path, int(font_size*1.5)) if chosen_font_path else ImageFont.truetype("Arial.ttf", int(font_size*1.5))
        except Exception:
            body_font = side_title_font = ImageFont.load_default()
        # 预估总高度（24行基准）
        h = 0
        h += int(side_title_font.size * 1.2) # Side A标题
        h += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25) # 空行
        h += max_tracks_per_side * (body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25))
        h += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25) # A-B间空行
        h += int(side_title_font.size * 1.2) # Side B标题
        h += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25) # 空行
        h += max_tracks_per_side * (body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25))
        max_line_w = max(
            [body_font.getlength(ln) for ln in side_a_lines + side_b_lines] +
            [side_title_font.getlength("SIDE A"), side_title_font.getlength("SIDE B")]
        )
        return h, body_font, side_title_font, max_line_w

    min_px, max_px = int(12 * scale), int(180 * scale)
    best_px, best_fonts = min_px, None
    while min_px <= max_px:
        mid = (min_px + max_px) // 2
        h, bf, stf, max_line_w = measure_block(mid)
        if h <= block_h and max_line_w <= block_w:
            best_px, best_fonts = mid, (bf, stf)
            min_px = mid + 1
        else:
            max_px = mid - 1
    if best_fonts is None:
        h, bf, stf, _ = measure_block(int(12 * scale))
        best_fonts = (bf, stf)
    body_font, side_title_font = best_fonts

    # 重新计算总高度，确定起始y实现上下居中
    h = 0
    h += int(side_title_font.size * 1.2)
    h += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)
    h += len(side_a_lines) * (body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25))
    h += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)
    h += int(side_title_font.size * 1.2)
    h += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)
    h += len(side_b_lines) * (body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25))
    start_y = block_y + (block_h - h) // 2
    center_x = block_x + block_w // 2
    current_y = start_y

    # 直接使用二分查找得到的最大字号字体
    # body_font, side_title_font 已由上面二分查找得到
    # Side A/B 标题的 x 位置（右移）
    side_title_x = x_margin + int(left_block_w * cfg.side_title_x_offset)
    # 分别处理 Side A 和 Side B 部分
    side_a_lines = wrap_track_lines("A", side_a)
    side_b_lines = wrap_track_lines("B", side_b)


    # 统一 85% 不透明度的文本颜色（纯白）
    fill_80 = fill_track

    # Side A 标题
    side_a_title = "SIDE A"
    side_a_title_w = text_draw.textlength(side_a_title, font=side_title_font)
    text_draw.text((center_x - side_a_title_w // 2, current_y), side_a_title, font=side_title_font, fill=fill_80)
    current_y += int(side_title_font.size * 1.2)
    # 插入空行
    current_y += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)

    # Side A 曲目
    for ln in side_a_lines:
        w = text_draw.textlength(ln, font=body_font)
        text_draw.text((center_x - w // 2, current_y), ln, font=body_font, fill=fill_80)
        current_y += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)


    # 间隔（A曲目与Side B之间插入空行）
    current_y += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)

    # Side B 标题
    side_b_title = "SIDE B"
    side_b_title_w = text_draw.textlength(side_b_title, font=side_title_font)
    text_draw.text((center_x - side_b_title_w // 2, current_y), side_b_title, font=side_title_font, fill=fill_80)
    current_y += int(side_title_font.size * 1.2)
    # 插入空行
    current_y += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)

    # Side B 曲目
    for ln in side_b_lines:
        w = text_draw.textlength(ln, font=body_font)
        text_draw.text((center_x - w // 2, current_y), ln, font=body_font, fill=fill_80)
        current_y += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)

    # Draw right horizontal title - 在主题图正上方，左右与主题图居中对齐
    # 图片区域参数（与上面图片粘贴位置一致）
    box_x, box_y = 1885, 282
    box_w, box_h = 1746, 1599
    
    # 标题水平居中：与图片的水平中心对齐
    image_center_x = box_x + box_w // 2
    
    try:
        title_font = ImageFont.truetype(chosen_font_path, side_title_font.size + 10) if chosen_font_path else ImageFont.truetype("Arial.ttf", side_title_font.size + 10)
    except Exception:
        title_font = ImageFont.load_default()
    
    # 计算标题宽度，实现水平居中
    title_width = text_draw.textlength(title, font=title_font)
    title_x = image_center_x - int(title_width / 2)
    
    # 标题Y位置：在图片上方，画布上边的正中央
    # 获取标题高度
    title_bbox = text_draw.textbbox((0, 0), title, font=title_font)
    title_height = title_bbox[3] - title_bbox[1]
    
    # 标题放在图片正上方，画布上边的正中央
    # 计算上边区域（从画布顶部到图片顶部）的中央位置
    top_area_center = int((box_y - title_height) // 2)
    title_y = top_area_center
    
    text_draw.text((title_x, title_y), title, font=title_font, fill=fill_title_full)

    # Draw vertical spine title at fixed position with fixed width
    # spine_x 已在上面根据 CLI/config 计算并限制到 3243-3333
    # 使用一个大画布测量文本尺寸，然后根据 cfg.spine_width_px 和画布高度缩放字体以适配脊宽
    measure_img = Image.new("RGBA", (2000, 2000), (0, 0, 0, 0))
    measure_draw = ImageDraw.Draw(measure_img)

    # 脊柱标题字号自适应，先用较小字号，逐步增大，确保不越界也不小于最小字号
    min_spine_px = max(cfg.min_body_px, int(18 * scale))
    max_spine_px = min(cfg.spine_width_px, body_font.size)
    best_spine_px = min_spine_px
    for px in range(min_spine_px, max_spine_px+1):
        try:
            test_font = ImageFont.truetype(chosen_font_path, px) if chosen_font_path else ImageFont.truetype("Arial.ttf", px)
        except Exception:
            continue
        bbox = measure_draw.textbbox((0, 0), title, font=test_font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        fits_vert = text_w <= int(height * 0.95)
        fits_width = text_h <= int(cfg.spine_width_px * 0.95)
        if fits_vert and fits_width:
            best_spine_px = px
        else:
            break
    # 脊柱字号-1，最小为1
    best_spine_px = max(1, best_spine_px - 1)
    try:
        spine_font = ImageFont.truetype(chosen_font_path, best_spine_px) if chosen_font_path else ImageFont.truetype("Arial.ttf", best_spine_px)
    except Exception:
        spine_font = ImageFont.load_default()

    # 使用测量到的 bbox 创建最终临时图像并绘制文本（水平），增加高度冗余并垂直居中，之后旋转-90度粘贴
    final_bbox = measure_draw.textbbox((0, 0), title, font=spine_font)
    text_w = final_bbox[2] - final_bbox[0]
    text_h = final_bbox[3] - final_bbox[1]
    pad_h = int(text_h * 0.3)
    spine_img = Image.new("RGBA", (text_w, text_h + pad_h), (0, 0, 0, 0))
    spine_draw = ImageDraw.Draw(spine_img)
    # 顶部对齐绘制，避免下半部分被裁切
    spine_draw.text((0, 0), title, font=spine_font, fill=fill_title_full)

    # 旋转并粘贴到主画布（在水平位置 spine_x 处，垂直居中）
    spine_img = spine_img.rotate(-90, expand=True)
    paste_y = (height - spine_img.height) // 2
    # 若spine_x为None则用默认配置
    use_spine_x = int(spine_x * scale) if spine_x is not None else cfg.spine_x_pos
    canvas.alpha_composite(spine_img, (use_spine_x - spine_img.width // 2, paste_y))


    # ====== 条形码与ID ======
    # 使用传入的ID（如果未提供则生成简短ID）
    if id_str:
        # 使用传入的ID作为条形码内容，确保表观内里一致
        barcode_id = id_str
    else:
        # 回退：生成简短ID（仅日期+时间，10位：YYMMDDHHmm）
        now = dt.datetime.now()
        barcode_id = now.strftime("%y%m%d%H%M")
    
    # 用 python-barcode 生成优雅可扫描的条码（直接使用ID）
    import barcode
    from barcode.writer import ImageWriter
    from io import BytesIO
    barcode_class = barcode.get_barcode_class('code128')
    barcode_img_io = BytesIO()
    code128 = barcode_class(barcode_id, writer=ImageWriter())
    # 先用黑色生成，后处理为背景色
    code128.write(barcode_img_io, options={
        'module_width': 0.3,
        'module_height': 32,
        'font_size': 18,
        'text_distance': 2,
        'quiet_zone': 2,
        'background': 'white',
        'foreground': 'black',
        'write_text': False
    })
    barcode_img_io.seek(0)
    barcode_img = Image.open(barcode_img_io).convert("RGBA")
    # 替换黑色为背景色
    bg_rgb = tuple(int(color_hex[i:i+2], 16) for i in (0,2,4))
    datas = barcode_img.getdata()
    new_data = []
    for item in datas:
        if item[:3] == (0,0,0):
            new_data.append(bg_rgb + (255,))
        else:
            new_data.append(item)
    barcode_img.putdata(new_data)
    # 旋转90度竖排，缩小到1/3宽度，去除条码下方字符，仅保留条码本身
    barcode_img = barcode_img.rotate(90, expand=True)
    orig_w, orig_h = barcode_img.size
    target_w = orig_w // 3
    target_h = int(360 * scale)
    # 裁切去除条码图片四周所有白边（假设白底为纯白）
    barcode_np = np.array(barcode_img)
    gray = np.mean(barcode_np[:,:,:3], axis=2)
    mask = gray < 250
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    top, bottom = np.argmax(rows), len(rows) - np.argmax(rows[::-1])
    left, right = np.argmax(cols), len(cols) - np.argmax(cols[::-1])
    barcode_np = barcode_np[top:bottom, left:right, :]
    barcode_img = Image.fromarray(barcode_np)
    # resize到目标尺寸
    barcode_img = barcode_img.resize((target_w, target_h), Image.LANCZOS)
    barcode_x = int(10 * scale)
    barcode_y = int(3442 * scale) + (int(360 * scale) - target_h) // 2
    canvas.alpha_composite(barcode_img, (barcode_x, barcode_y))

    # 先合成蒙版，再合成文字，保证所有文字在最上层
    overlay_path = DESIGN_DIR / "TopCover_HD.png"
    if overlay_path.exists():
        overlay = Image.open(overlay_path).convert("RGBA")
        overlay = overlay.resize((width, height), Image.LANCZOS)
        canvas = Image.alpha_composite(canvas, overlay)
    # 文字噪点风格（仅对文字区域叠加噪点），或将文字置于覆盖纹理之下
    if text_style == "noise":
        try:
            # 生成与画布同尺寸的噪点图层
            noise = np.random.normal(128, 22, (height, width)).clip(0, 255).astype(np.uint8)
            noise_rgba = Image.fromarray(noise, mode="L").convert("RGBA")
            # 设置较低全局透明度
            global_alpha = Image.new("L", (width, height), 36)
            noise_rgba.putalpha(global_alpha)
            # 仅作用于文字区域：以文字图层的 alpha 作为掩模
            text_alpha = text_overlay.split()[3]
            masked_noise = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            masked_noise.paste(noise_rgba, (0, 0), mask=text_alpha)
            # 把噪点叠加到文字图层上，使文字更“旧”
            text_overlay = Image.alpha_composite(text_overlay, masked_noise)
        except Exception as e:
            print(f"[WARN] 文字噪点处理失败: {e}")

    # 合成顺序：behind_overlay 时文字在覆盖纹理之下，否则文字在最上层
    if text_style == "behind_overlay":
        canvas = Image.alpha_composite(canvas, text_overlay)
        if overlay_path.exists():
            overlay = Image.open(overlay_path).convert("RGBA")
            overlay = overlay.resize((width, height), Image.LANCZOS)
            canvas = Image.alpha_composite(canvas, overlay)
    else:
        # 先覆盖纹理，再把文字放在最上层
        if overlay_path.exists():
            overlay = Image.open(overlay_path).convert("RGBA")
            overlay = overlay.resize((width, height), Image.LANCZOS)
            canvas = Image.alpha_composite(canvas, overlay)
    canvas = Image.alpha_composite(canvas, text_overlay)

    # 文件名：优先使用传入的id_str，否则生成时间戳
    now = dt.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    if output_dir is None:
        output_dir = OUTPUT_COVER_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if output_name:
        target = output_dir / output_name
    elif id_str:
        target = output_dir / f"{id_str}_cover.png"
    else:
        # 回退：生成包含时间戳的文件名
        target = output_dir / f"{timestamp}_{color_hex}_{seed}.png"
    # 最终输出为output_size（如4K），保持8K排版比例
    out_img = canvas.convert("RGB")
    out_img.save(target, "PNG")
    return target


def summarize(side: Sequence[Track]) -> str:
    total = sum(t.duration_sec for t in side)
    minutes, seconds = divmod(total, 60)
    return f"{len(side)} 首 · {minutes} 分 {seconds:02d} 秒"


def summarize_en(side: Sequence[Track]) -> str:
    total = sum(t.duration_sec for t in side)
    minutes, seconds = divmod(total, 60)
    return f"{len(side)} tracks, {minutes}m{seconds:02d}s"


def build_timelines(
    side_a: Sequence[Track], side_b: Sequence[Track]
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    def fmt(sec: int) -> str:
        minutes, seconds = divmod(sec, 60)
        return f"{minutes}:{seconds:02d}"

    timeline: List[Dict[str, str]] = []
    clean_events: List[Dict[str, str]] = []
    current = 0

    # Side A
    timeline.append({"side": "A", "timestamp": fmt(current), "description": "Needle On Vinyl Record"})
    current += 3
    for idx, track in enumerate(side_a):
        timeline.append({"side": "A", "timestamp": fmt(current), "description": track.title})
        clean_events.append({"side": "A", "timestamp": fmt(current), "description": track.title})
        current += max(0, track.duration_sec - 2)
        # 只有不是最后一首才加Vinyl Noise
        if idx != len(side_a) - 1:
            timeline.append({"side": "A", "timestamp": fmt(current), "description": "Vinyl Noise"})
            current += 5

    # Side A结束后，3秒静音
    timeline.append({"side": "A", "timestamp": fmt(current), "description": "Silence"})
    current += 3

    # Side B
    timeline.append({"side": "B", "timestamp": fmt(current), "description": "Needle On Vinyl Record"})
    current += 3
    for idx, track in enumerate(side_b):
        timeline.append({"side": "B", "timestamp": fmt(current), "description": track.title})
        clean_events.append({"side": "B", "timestamp": fmt(current), "description": track.title})
        current += max(0, track.duration_sec - 2)
        if idx != len(side_b) - 1:
            timeline.append({"side": "B", "timestamp": fmt(current), "description": "Vinyl Noise"})
            current += 5

    return timeline, clean_events


def main() -> tuple:
    parser = argparse.ArgumentParser(description="生成 Kat Records AB 面歌单与示例封面")
    parser.add_argument(
        "--tracklist",
        type=Path,
        default=Path("data/song_library.csv"),
        help="曲库数据文件（CSV/TSV），默认 data/song_library.csv，若不存在则尝试 google_sheet tsv。",
    )
    parser.add_argument(
        "--images_dir",
        type=Path,
        default=None,
        help="可选：覆盖图片目录，默认使用 assets/design/images",
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=None,
        help="可选：指定单张图片路径，若提供则不再随机选择",
    )
    parser.add_argument("--total-tracks", type=int, default=None, help="强制总曲目数（按数量选曲，A/B 平分）")
    parser.add_argument("--seed", type=int, default=None, help="随机种子，便于复现。不指定则自动随机。")
    parser.add_argument(
        "--spine-x",
        type=int,
        default=None,
        help="可选：覆盖脊柱标题的横向像素位置（会被钳制到 3243-3333 之间）。",
    )

    parser.add_argument("--output_name", type=str, default=None, help="指定输出文件名")
    parser.add_argument("--font_name", type=str, default=None, help="指定字体名（不含扩展名）")
    parser.add_argument("--show_font_name", action="store_true", help="左上角标注字体名")
    parser.add_argument("--episode-id", type=str, help="指定期数ID（YYYYMMDD格式），例如：20251101")
    parser.add_argument("--schedule-date", type=str, help="指定排播日期（YYYY-MM-DD格式），默认自动计算下一个排播日期")
    parser.add_argument("--no-remix", action="store_true", help="仅生成歌单与封面，跳过混音与后续流程")
    parser.add_argument("--no-youtube", action="store_true", help="跳过 YouTube 资源生成（SRT、标题、描述）")
    parser.add_argument("--no-video", action="store_true", help="跳过视频生成")
    parser.add_argument("--title-api", type=str, default=None, help="可选：标题生成服务URL (POST JSON)")
    parser.add_argument("--title-api-key", type=str, default=None, help="可选：标题服务API Key")
    parser.add_argument(
        "--text-style",
        type=str,
        choices=["noise", "behind_overlay"],
        default="noise",
        help="文字风格：noise=给文字加噪点(默认)，behind_overlay=把文字置于覆盖纹理之下",
    )
    # 视频/音频编码参数
    parser.add_argument("--fps", type=int, default=1, help="视频帧率，默认 1")
    parser.add_argument("--codec_v", type=str, default="auto", help="视频编码器：auto|h264_videotoolbox|libx264|h264_nvenc|mjpeg，默认 auto")
    parser.add_argument("--duration-fix", type=str, choices=["none", "30fps", "explicit", "1fps-precise"], default="1fps-precise",
                       help="时长修复方案: none=原逻辑, 30fps=30fps(误差≤1s但文件大), explicit=显式裁剪, 1fps-precise=1fps精确时间戳(推荐,最快最小)")
    parser.add_argument("--v_bitrate", type=str, default="3M", help="视频码率（用于硬编），默认 3M，30fps模式时自动提升至6M")
    parser.add_argument("--crf", type=str, default="22", help="x264 CRF，默认 22（数值越小越清晰）")
    parser.add_argument("--preset", type=str, default="veryfast", help="x264 预设，默认 veryfast")
    parser.add_argument("--pix_fmt", type=str, default="yuv420p", help="像素格式，默认 yuv420p")
    parser.add_argument("--audio_copy", action="store_true", help="视频音频直接 copy，不转码为 AAC")
    parser.add_argument("--v_audio_bitrate", type=str, default="256k", help="视频内音频 AAC 码率，默认 256k")
    # 预检与跳过
    parser.add_argument("--preflight-only", action="store_true", help="仅执行环境与资源预检后退出")
    parser.add_argument("--force", action="store_true", help="预检失败仍强制继续，同时强制重新生成所有文件（即使文件已存在）")
    def preflight_check(_args) -> bool:
        ok = True
        issues: List[str] = []
        # ffmpeg
        if not shutil.which("ffmpeg"):
            ok = False
            issues.append("未找到 ffmpeg，请安装：brew install ffmpeg")
        # Python 版本提示（推荐 3.12）
        try:
            import sys as _sys
            if _sys.version_info[:2] >= (3, 14):
                issues.append("警告：当前 Python ≥3.14，建议使用 3.12 以避免音频依赖问题")
        except Exception:
            pass
        # 字体
        font_count = len(list(FONT_DIR.glob("*.ttf"))) + len(list(FONT_DIR.glob("*.otf")))
        if font_count == 0:
            ok = False
            issues.append(f"未找到字体文件：{FONT_DIR}")
        # 图片
        img_dir = _args.images_dir if _args.images_dir else (DESIGN_DIR / "images")
        img_count = len(list(img_dir.glob("*.png"))) + len(list(img_dir.glob("*.jpg")))
        if not _args.image and img_count == 0:
            ok = False
            issues.append(f"未找到封面图片：{img_dir}")
        # 输出写权限（检查统一的输出目录）
        try:
            output_base = REPO_ROOT / "output"
            output_base.mkdir(parents=True, exist_ok=True)
            test_path = output_base / ".write_test"
            with open(test_path, "w") as _fh:
                _fh.write("ok")
            test_path.unlink(missing_ok=True)
        except Exception as e:
            ok = False
            issues.append(f"输出目录不可写：{output_base}，原因：{e}")
        if not ok or issues:
            print("[Preflight] 检查结果：")
            for it in issues:
                print(" -", it)
        return ok

    # 先解析参数，再执行预检
    args = parser.parse_args()
    pf_ok = preflight_check(args)
    if args.preflight_only:
        print("[Preflight] 仅执行预检并退出。")
        return None, None, args
    if not pf_ok and not args.force:
        raise SystemExit("[Preflight] 失败，使用 --force 可忽略预检继续运行。")
    import time
    if args.seed is None:
        args.seed = int(time.time() * 1000) % 1000000007  # 用当前毫秒时间生成随机种子

    tracklist_path = args.tracklist
    if not tracklist_path.exists():
        fallback = next(Path("data/google_sheet").glob("*.tsv"), None)
        if fallback is None:
            raise FileNotFoundError("找不到曲库文件，请先生成 data/song_library.csv 或提供 TSV。")
        tracklist_path = fallback

    tracks = load_tracklist(tracklist_path)
    
    # ===== 提前加载排播表（用于排除列表和图片选择）=====
    # 必须在函数开头声明，避免作用域问题
    schedule_master = None
    
    # ===== 从排播表获取排除列表（避免临近期数重复）=====
    excluded_tracks = None
    excluded_starting_tracks = None
    all_used_tracks = None  # 所有已使用的歌曲（用于识别新歌）
    
    # 加载排播表以获取排除列表（在ID生成之前）
    try:
        from schedule_master import ScheduleMaster
        from production_log import ProductionLog
        
        schedule_master = ScheduleMaster.load()
        if schedule_master:
            # 获取临时ID（用于查询排除列表）
            temp_id_str = None
            if hasattr(args, 'episode_id') and args.episode_id:
                temp_id_str = args.episode_id
            elif hasattr(args, 'schedule_date') and args.schedule_date:
                temp_schedule_date = dt.datetime.fromisoformat(args.schedule_date)
                temp_id_str = temp_schedule_date.strftime("%Y%m%d")
            else:
                # 从生产日志获取下一个排播日期
                temp_log = ProductionLog.load()
                temp_schedule_date = temp_log.get_next_schedule_date()
                if temp_schedule_date:
                    temp_id_str = temp_schedule_date.strftime("%Y%m%d")
            
            # 如果有临时ID，获取排除列表
            if temp_id_str:
                excluded_tracks = schedule_master.get_recent_tracks(temp_id_str, window=5)
                excluded_starting_tracks = schedule_master.get_used_starting_tracks()
                # 获取所有已使用的歌曲（用于识别新歌）
                all_used_tracks = schedule_master.get_all_used_tracks()
                
                if excluded_tracks:
                    print(f"[排播表] 排除最近5期使用的歌曲：{len(excluded_tracks)} 首")
                if excluded_starting_tracks:
                    print(f"[排播表] 确保起始曲目独特（已用：{len(excluded_starting_tracks)} 首）")
                if all_used_tracks:
                    print(f"[排播表] 已使用的歌曲总数：{len(all_used_tracks)} 首")
            
            print(f"[排播表] ✅ 已加载永恒排播表（共 {schedule_master.total_episodes} 期）")
    except Exception as e:
        print(f"[排播表] ⚠️ 加载失败或不存在: {e}，使用默认逻辑")
        schedule_master = None  # 确保设置为None
    
    if args.total_tracks is not None and args.total_tracks > 0:
        # 总数上限 26
        requested = min(args.total_tracks, 26)
        side_a, side_b = select_tracks_by_count(tracks, requested, seed=args.seed)
    else:
        side_a, side_b = select_tracks(
            tracks, 
            seed=args.seed,
            excluded_tracks=excluded_tracks,
            excluded_starting_tracks=excluded_starting_tracks,
            all_used_tracks=all_used_tracks,
            new_track_ratio=0.7  # 70%新歌，30%旧歌
        )
    # 统一应用曲目数量约束
    side_a, side_b = enforce_track_count_constraints(list(side_a), list(side_b))

    # --- Image selection and color extraction ---
    # schedule_master 已在上面加载
    # 优先使用排播表分配的图片
    image_dir = args.images_dir if args.images_dir else (DESIGN_DIR / "images")
    if args.image:
        selected_image_path = args.image
        if not selected_image_path.exists():
            raise FileNotFoundError(f"指定图片不存在: {selected_image_path}")
    else:
        # 尝试从排播表获取分配的图片
        selected_image_path = None
        # 需要先确定id_str才能从排播表获取图片
        id_str_for_image = None
        if args.episode_id:
            id_str_for_image = args.episode_id
        elif schedule_master and hasattr(args, 'schedule_date') and args.schedule_date:
            schedule_date = dt.datetime.fromisoformat(args.schedule_date)
            id_str_for_image = schedule_date.strftime("%Y%m%d")
        
        if schedule_master and id_str_for_image:
            ep_record = schedule_master.get_episode(id_str_for_image)
            if ep_record:
                image_path_str = ep_record.get("image_path")
                if image_path_str:
                    selected_image_path = Path(image_path_str)
                    if selected_image_path.exists():
                        print(f"[排播表] 使用分配的图片：{selected_image_path.name}")
                        # 确认图片使用标记（分配给当前期数的图片应该在images_used中，这是正常的）
                        if image_path_str in schedule_master.images_used:
                            # 检查是否分配给其他期数（异常情况）
                            other_episodes = [ep for ep in schedule_master.episodes 
                                            if ep.get("episode_id") != id_str_for_image 
                                            and ep.get("image_path") == image_path_str]
                            if other_episodes:
                                print(f"[排播表] ⚠️ 警告：此图片同时分配给多个期数！")
                            # 否则，图片在images_used中是正常的（因为它被分配给了当前期数）
                    else:
                        print(f"[排播表] ⚠️ 分配的图片不存在，回退到随机选择")
                        selected_image_path = None
        
        # 如果排播表没有或失败，使用随机选择
        if not selected_image_path:
            image_files = list(image_dir.glob("*.png")) + list(image_dir.glob("*.jpg"))
            if not image_files:
                raise FileNotFoundError(f"No image files found in {image_dir}")
            rng = random.Random(args.seed) # Use the same RNG for image selection
            selected_image_path = rng.choice(image_files)
            print(f"[图片] 随机选择：{selected_image_path.name}")
    # 选择“更暗更艳”的背景色（避免偏灰/过亮），失败则回退 dominant
    try:
        preferred_rgb = select_vivid_dark_color(selected_image_path)
    except Exception:
        preferred_rgb = get_dominant_color(selected_image_path)
    color_hex = f"{preferred_rgb[0]:02x}{preferred_rgb[1]:02x}{preferred_rgb[2]:02x}"

    # --- Title Generation (API only, no fallback) ---
    # 必须先检查API密钥
    from api_config import require_api_key
    openai_key = require_api_key()  # 强制要求，不允许交互式输入
    
    playlist_keywords = [t.title for t in (side_a + side_b)]
    title: str | None = None

    # 标题去重检查函数
    # 注意：需要捕获外部的 schedule_master 变量，避免 Python 作用域问题
    _schedule_master_ref = schedule_master  # 在函数定义前捕获外部变量
    
    def _generate_title_with_dedup(max_attempts: int = 3) -> Optional[str]:
        """生成标题并检查去重（最多尝试max_attempts次）"""
        from api_config import get_api_config, get_api_base_url, get_api_model
        config = get_api_config()
        provider = config.get_provider()
        base_url = config.get_base_url(provider)
        model = config.get_model(provider)
        
        for attempt in range(max_attempts):
            t = _try_api_title(
                selected_image_path.name,
                preferred_rgb,
                playlist_keywords,
                args.seed + attempt,  # 每次尝试改变seed
                openai_key,
                base_url,
                model,
                provider,
            )
            if not t:
                if attempt < max_attempts - 1:
                    print(f"[API] 标题生成失败，重试中... (第{attempt+1}/{max_attempts}次)")
                    import time
                    time.sleep(1)
                continue
            
            # 检查标题模式是否重复（使用捕获的引用）
            if _schedule_master_ref:
                is_unique, pattern = _schedule_master_ref.check_title_pattern(t)
                if is_unique:
                    print(f"[标题检查] 标题模式：{pattern} ✅ 唯一")
                    return t
                else:
                    # 检查是否是短语重复
                    phrase_unique, repeated_phrases = _schedule_master_ref.check_phrase_repetition(t)
                    if not phrase_unique:
                        print(f"[标题检查] ⚠️ 检测到重复短语: {', '.join(repeated_phrases)}")
                    print(f"[标题检查] 标题模式：{pattern} ⚠️ 重复（第{attempt+1}次尝试）")
                    if attempt < max_attempts - 1:
                        print(f"[标题检查] 重新生成...")
            else:
                # 没有排播表，直接返回
                return t
        
        # 如果所有尝试都失败或重复
        if t:
            print(f"[标题检查] ⚠️ 尝试{max_attempts}次仍有重复模式，使用最后一次结果")
            return t
        return None
    
    print("[API] 正在调用 OpenAI API 生成唱片标题...")
    try:
        title = _generate_title_with_dedup(max_attempts=3)
        if not title:
            raise RuntimeError("API调用失败或返回空标题，已重试3次仍失败")
        
        print(f"[API] ✅ 唱片标题生成成功: {title}")
        title_source = "api"  # 标题来源：API生成
    except Exception as e:
        print(f"\n❌ 错误：无法生成标题")
        print(f"   原因: {e}")
        print(f"\n💡 提示：")
        print(f"   1. 检查网络连接")
        print(f"   2. 验证API密钥是否有效: make check-api --test")
        print(f"   3. 检查API余额是否充足")
        print()
        raise SystemExit("标题生成失败，程序退出")
    # Sanitize and title-case
    title = to_title_case(sanitize_title(title))
    
    # 标题去重检查（已通过API生成，仅检查不重新生成）
    if schedule_master:
        is_unique, pattern = schedule_master.check_title_pattern(title)
        if not is_unique:
            print(f"[标题检查] ⚠️ 警告：标题模式重复 ({pattern})，但已使用API生成，继续使用")

    # 生成基于排播日期的ID
    from production_log import (
        ProductionLog,
        get_library_snapshot,
        get_production_id
    )
    
    production_log = ProductionLog.load()
    library_snapshot = get_library_snapshot(tracklist_path, track_count=len(tracks))
    
    # 获取排播日期和ID
    schedule_date = None
    id_str = None
    
    # 优先使用指定的episode-id
    if hasattr(args, 'episode_id') and args.episode_id:
        id_str = args.episode_id
        # 从ID解析日期（YYYYMMDD -> YYYY-MM-DD）
        try:
            schedule_date = dt.datetime.strptime(id_str, "%Y%m%d")
            print(f"[排播ID] 使用指定ID：{id_str} (日期：{schedule_date.strftime('%Y-%m-%d')})")
        except ValueError:
            print(f"⚠️  警告：ID格式无效 {id_str}，应使用 YYYYMMDD 格式（如 20251101）")
            # 继续使用原逻辑
            id_str = None
    
    # 如果指定了schedule-date但没指定ID，从日期生成ID
    if not id_str and hasattr(args, 'schedule_date') and args.schedule_date:
        schedule_date = dt.datetime.fromisoformat(args.schedule_date)
        id_str = schedule_date.strftime("%Y%m%d")
        print(f"[排播日期] 使用指定日期：{schedule_date.strftime('%Y-%m-%d')} (ID: {id_str})")
    
    # 如果都没指定，自动计算下一个
    if not id_str:
        id_str, schedule_date, production_log = get_production_id(
            log=production_log,
            schedule_date=schedule_date,
            tracklist_path=tracklist_path
        )
    
    # 创建或更新生产记录
    record = production_log.find_record(id_str)
    if not record:
        production_log.create_record(
            schedule_date=schedule_date,
            library_snapshot=library_snapshot,
            status="pending"
        )
    # 如果记录已存在且为pending状态，保持原样（可能在重试）
    
    # 更新最后歌库更新时间
    production_log.last_library_update = library_snapshot.updated_at
    production_log.save()
    
    episode_number = production_log.get_episode_number(schedule_date)
    print(f"[生产日志] 期数：第 {episode_number} 期")
    print(f"[生产日志] 排播日期：{schedule_date.strftime('%Y-%m-%d')}")
    print(f"[生产日志] ID：{id_str}")
    print(f"[生产日志] 歌库规模：{library_snapshot.total_tracks} 首")
    
    # ===== 使用已加载的排播表（schedule_master 已在前面加载）=====
    # 防御性检查：如果由于某种原因未加载，则重新加载
    if schedule_master is None:
        try:
            from schedule_master import ScheduleMaster
            schedule_master = ScheduleMaster.load()
        except Exception:
            pass
    
    if schedule_master:
        ep_record = schedule_master.get_episode(id_str)
        if ep_record:
            print(f"[排播表] 使用第 {ep_record['episode_number']} 期排播计划")
        else:
            print(f"[排播表] ⚠️ 未找到期数 {id_str} 的排播记录")
    
    unified_output_dir = get_output_dir(id_str, title)
    unified_output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[输出目录] 过程文件暂存目录: {unified_output_dir}（资料齐了后会打包到最终文件夹）")
    
    # ===== 检查已存在的文件，避免重复生成 =====
    def check_file_exists(file_path: Path, file_type: str) -> bool:
        """检查文件是否存在（在output目录或最终文件夹中）"""
        if file_path.exists():
            return True
        # 检查最终文件夹
        if schedule_date:
            try:
                final_dir = get_final_output_dir(schedule_date, title)
                final_file = final_dir / file_path.name
                if final_file.exists():
                    return True
            except:
                pass
        return False
    
    # 检查歌单和封面文件
    playlist_check_path = unified_output_dir / f"{id_str}_playlist.csv"
    cover_check_path = unified_output_dir / f"{id_str}_cover.png"
    playlist_exists = check_file_exists(playlist_check_path, "歌单")
    cover_exists = check_file_exists(cover_check_path, "封面")
    
    # 显示文件存在性检查结果
    if playlist_exists or cover_exists:
        print("\n" + "=" * 70)
        print("📋 文件存在性检查")
        print("=" * 70)
        if playlist_exists:
            print(f"  ✅ 歌单已存在: {playlist_check_path.name}")
        if cover_exists:
            print(f"  ✅ 封面已存在: {cover_check_path.name}")
        if not args.force and (playlist_exists and cover_exists):
            print(f"\n💡 提示：歌单和封面都已存在，将跳过生成步骤")
            print(f"   如需重新生成，请使用 --force 参数")

    side_a_summary = summarize(side_a)
    side_b_summary = summarize(side_b)
    side_a_summary_en = summarize_en(side_a)
    side_b_summary_en = summarize_en(side_b)

    prompt = generate_prompt(title, color_hex)
    subtitle = f"Side A {side_a_summary_en} - Side B {side_b_summary_en}"
    needle_timeline, clean_timeline = build_timelines(side_a, side_b)

    # 生成或使用已存在的文件
    if playlist_exists and not args.force:
        print(f"[生成] ⏭️  跳过歌单生成（文件已存在）")
        playlist_path = playlist_check_path
        if not playlist_path.exists() and schedule_date:
            # 尝试从最终文件夹获取
            final_dir = get_final_output_dir(schedule_date, title)
            final_playlist = final_dir / playlist_check_path.name
            if final_playlist.exists():
                playlist_path = final_playlist
    else:
        playlist_path = export_playlist(
            side_a,
            side_b,
            title,
            color_hex,
            prompt,
            needle_timeline,
            clean_timeline,
            title_source,
            output_dir=unified_output_dir,
            id_str=id_str,
        )
    
    if cover_exists and not args.force:
        print(f"[生成] ⏭️  跳过封面生成（文件已存在）")
        cover_path = cover_check_path
        if not cover_path.exists() and schedule_date:
            # 尝试从最终文件夹获取
            final_dir = get_final_output_dir(schedule_date, title)
            final_cover = final_dir / cover_check_path.name
            if final_cover.exists():
                cover_path = final_cover
    else:
        cover_path = compose_cover(
            title, side_a, side_b, color_hex, args.seed,
            spine_x=args.spine_x,
            output_name=args.output_name,
            font_name=args.font_name,
            output_size=(3840, 2160),
            image_path=selected_image_path,
            text_style=args.text_style,
            output_dir=unified_output_dir,
            id_str=id_str,
        )

    print("=" * 60)
    print(f"标题：{title}")
    print(f"封面色调：#{color_hex}")
    print(f"封面提示词：\n{prompt}")
    print("-" * 60)

    print("[Side A]")
    for idx, track in enumerate(side_a, start=1):
        print(f"{idx:02d}. {track.title} ({track.duration_str})")
    print(f"总计：{side_a_summary}")
    print("-" * 60)

    print("[Side B]")
    for idx, track in enumerate(side_b, start=1):
        print(f"{idx:02d}. {track.title} ({track.duration_str})")
    print(f"总计：{side_b_summary}")
    print("-" * 60)


    print(f"歌单已写入：{playlist_path}")
    print(f"封面已生成：{cover_path}")
    
    # ===== 使用统一状态管理器更新排播表（标题和曲目，但状态保持pending直到所有阶段成功） =====
    try:
        from core.event_bus import get_event_bus
        from core.state_manager import get_state_manager, STATUS_PENDING
        
        state_manager = get_state_manager()
        event_bus = get_event_bus()
        
        # 更新元数据（不改变状态）
        if schedule_master and id_str:
            tracks_list = [t.title for t in (side_a + side_b)]
            starting_track = side_a[0].title if side_a else None
            
            # 使用状态管理器更新元数据
            state_manager.update_episode_metadata(
                episode_id=id_str,
                title=title,
                tracks_used=tracks_list,
                starting_track=starting_track
            )
            print(f"[状态管理] ✅ 排播表元数据已更新（标题和曲目），状态保持 pending（等待后续阶段）")
            
            # 触发阶段完成事件（playlist/cover生成完成）
            event_bus.emit_stage_completed(id_str, "playlist_and_cover")
        
    except ImportError:
        # 如果新模块不可用，回退到旧方式
        from production_log import ProductionLog
        production_log = ProductionLog.load()
        production_log.update_record(
            episode_id=id_str,
            status="pending",  # 不再标记为completed
            output_dir=str(unified_output_dir),
            title=title,
            track_count=len(side_a) + len(side_b)
        )
        production_log.save()
        
        if schedule_master:
            tracks_list = [t.title for t in (side_a + side_b)]
            starting_track = side_a[0].title if side_a else None
            
            success = schedule_master.update_episode(
                episode_id=id_str,
                title=title,
                tracks_used=tracks_list,
                starting_track=starting_track,
            )
            
            if success:
                schedule_master.save()
                print(f"[排播表] ✅ 排播表已更新（标题和曲目），状态保持 pending")
    
    # 检查剩余图片（如果使用旧方式）
    if schedule_master:
        remaining, unused = schedule_master.check_remaining_images()
        print(f"[排播表] 剩余可用图片：{remaining} 张")
        if remaining < 10:
            print(f"[排播表] ⚠️ 警告：可用图片不足10张，建议补充图片！")
    
    # 生成 YouTube 资源（SRT、标题、描述）
    if not args.no_youtube:
        try:
            # 使用统一输出目录
            youtube_output_dir = unified_output_dir
            youtube_output_dir.mkdir(parents=True, exist_ok=True)
            
            # 检查YouTube资源是否已存在
            youtube_check_paths = [
                unified_output_dir / f"{id_str}_youtube.srt",
                unified_output_dir / f"{id_str}_youtube_title.txt",
                unified_output_dir / f"{id_str}_youtube_description.txt",
            ]
            if schedule_date:
                final_dir = get_final_output_dir(schedule_date, title)
                youtube_check_paths.extend([
                    final_dir / f"{id_str}_youtube.srt",
                    final_dir / f"{id_str}_youtube_title.txt",
                    final_dir / f"{id_str}_youtube_description.txt",
                ])
            
            youtube_exists = all(p.exists() for p in youtube_check_paths[:3]) or \
                           (schedule_date and all(p.exists() for p in youtube_check_paths[3:]))
            
            if youtube_exists and not args.force:
                print(f"[YouTube] ⏭️  跳过YouTube资源生成（文件已存在）")
                print(f"   如需重新生成，请使用 --force 参数")
            
            # 导入 YouTube 生成脚本
            import sys
            youtube_script = Path(__file__).parent / "generate_youtube_assets.py"
            if youtube_script.exists() and (not youtube_exists or args.force):
                import subprocess
                openai_key = os.environ.get("OPENAI_API_KEY")
                openai_base = os.environ.get("OPENAI_BASE_URL")
                
                cmd = [
                    sys.executable,
                    str(youtube_script),
                    "--playlist", str(playlist_path),
                    "--title", title,
                    "--output", str(youtube_output_dir),
                ]
                if openai_key:
                    cmd.extend(["--openai-api-key", openai_key])
                if openai_base:
                    cmd.extend(["--openai-base-url", openai_base])
                
                print("[YouTube] 正在生成 SRT 字幕、标题和描述...")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    print("[YouTube] ✅ 资源生成完成！")
                    # 只打印关键输出，不打印所有 stdout
                    if result.stdout:
                        for line in result.stdout.split("\n"):
                            if "[API]" in line or "[完成]" in line or "[生成]" in line or "✅" in line:
                                print(line)
                else:
                    print(f"[YouTube] ⚠️ 生成失败: {result.stderr}")
                    if result.stdout:
                        print(result.stdout)
            else:
                print(f"[YouTube] ⚠️ 未找到生成脚本: {youtube_script}")
        except Exception as e:
            print(f"[YouTube] ⚠️ 生成 YouTube 资源失败: {e}")
    
    print("=" * 60)
    # 结构化日志
    try:
        logs_dir = Path("output/logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_item = {
            "stage": "generate",
            "timestamp": dt.datetime.now().isoformat(),
            "seed": args.seed,
            "title": title,
            "title_source": title_source,
            "color_hex": f"#{color_hex}",
            "cover_path": str(cover_path),
            "playlist_path": str(playlist_path),
        }
        with (logs_dir / "katrec.log").open("a", encoding="utf-8") as lf:
            lf.write(_json.dumps(log_item, ensure_ascii=False) + "\n")
    except (PermissionError, OSError, IOError) as e:
        print(f"[log] 写入失败：{type(e).__name__}: {e}")
    except Exception as e:
        print(f"[log] 写入失败：{type(e).__name__}: {e}")
    # 写入 run.json 元信息（附加到列表）
    try:
        import json
        import subprocess
        run_dir = Path("output")
        run_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"
        try:
            ffmpeg_ver = subprocess.check_output([ffmpeg_path, "-version"], text=True, timeout=3).splitlines()[0]
        except Exception:
            ffmpeg_ver = "unknown"
        run_item = {
            "timestamp": dt.datetime.now().isoformat(),
            "seed": args.seed,
            "image": str(selected_image_path),
            "color_hex": f"#{color_hex}",
            "title": title,
            "title_source": title_source,
            "cover_path": str(cover_path),
            "playlist_path": str(playlist_path),
            "fps": args.fps,
            "codec_v": args.codec_v,
            "v_bitrate": args.v_bitrate,
            "crf": args.crf,
            "preset": args.preset,
            "pix_fmt": args.pix_fmt,
            "audio_copy": bool(args.audio_copy),
            "v_audio_bitrate": args.v_audio_bitrate,
            "ffmpeg": ffmpeg_ver,
        }
        run_index = run_dir / "run.json"
        data = []
        if run_index.exists():
            try:
                with run_index.open("r", encoding="utf-8") as fh:
                    data = json.load(fh) or []
                    if not isinstance(data, list):
                        data = []
            except Exception:
                data = []
        data.append(run_item)
        with run_index.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except (PermissionError, OSError, IOError) as e:
        print(f"[run.json] 写入失败：{type(e).__name__}: {e}")
    except Exception as e:
        print(f"[run.json] 写入失败：{type(e).__name__}: {e}")

    return playlist_path, cover_path, args, id_str, title, unified_output_dir, schedule_date


if __name__ == "__main__":
    result = main()
    if result[0] is None:  # preflight_only 或失败
        sys.exit(0)
    playlist_path, cover_path, args, id_str, title, unified_output_dir, schedule_date = result
    # 自动联动remix_mixtape.py（带事件驱动状态更新）
    remix_success = False
    if getattr(args, "no_remix", False):
        print("[联动] 已按 --no-remix 跳过混音与后续流程。")
    else:
        try:
            # 尝试导入事件总线
            try:
                from core.event_bus import get_event_bus
                from core.state_manager import get_state_manager, STATUS_ERROR, STATUS_REMIXING
                event_bus = get_event_bus()
                state_manager = get_state_manager()
                use_event_system = True
            except ImportError:
                use_event_system = False
                event_bus = None
                state_manager = None
            
            import subprocess
            import sys
            remix_script = (Path(__file__).parent / "remix_mixtape.py").resolve()
            
            # 检查混音音频是否已存在
            audio_check_paths = [
                unified_output_dir / f"{id_str}_full_mix.mp3",
                unified_output_dir / f"{id_str}_playlist_full_mix.mp3",
            ]
            if schedule_date:
                try:
                    final_dir = get_final_output_dir(schedule_date, title)
                    audio_check_paths.extend([
                        final_dir / f"{id_str}_full_mix.mp3",
                        final_dir / f"{id_str}_playlist_full_mix.mp3",
                    ])
                except:
                    pass
            
            audio_exists = any(p.exists() for p in audio_check_paths)
            
            if audio_exists and not args.force:
                print(f"[联动] ⏭️  跳过混音生成（音频文件已存在）")
                print(f"   如需重新生成，请使用 --force 参数")
                remix_success = True
            elif playlist_path is not None and Path(remix_script).exists() and (not audio_exists or args.force):
                # 触发混音开始事件
                if use_event_system and id_str:
                    event_bus.emit_remix_started(id_str)
                
                if RICH_AVAILABLE:
                    console = Console()
                    with console.status("[cyan]正在生成混音音频...", spinner="dots"):
                        result = subprocess.run([
                            sys.executable,
                            str(remix_script),
                            "--playlist",
                            str(playlist_path)
                        ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                        
                        if result.returncode == 0:
                            remix_success = True
                            console.print("[green]✓ 混音已完成！[/green]")
                        else:
                            remix_success = False
                            error_msg = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "未知错误"
                            console.print(f"[red]✗ 混音失败: {error_msg}[/red]")
                else:
                    print(f"[联动] 正在自动生成混音...\nremix脚本: {remix_script}\nplaylist: {playlist_path}")
                    result = subprocess.run([
                        sys.executable,
                        str(remix_script),
                        "--playlist",
                        str(playlist_path)
                    ], check=False, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        remix_success = True
                        print("[联动] 混音已完成！")
                    else:
                        remix_success = False
                        print(f"[联动] 混音失败: {result.stderr}")
                
                # 触发事件
                if use_event_system and id_str:
                    if remix_success:
                        event_bus.emit_remix_completed(id_str)
                    else:
                        error_msg = result.stderr.decode('utf-8', errors='ignore') if hasattr(result, 'stderr') and result.stderr else "混音失败"
                        event_bus.emit_remix_failed(id_str, error_msg)
                        # 回滚状态
                        state_manager.rollback_status(id_str, target_status="pending")
                        print(f"[状态管理] ⚠️ 状态已回滚至 pending（混音失败）")
            else:
                print(f"[联动] 未找到playlist({playlist_path})或remix脚本({remix_script})，跳过自动混音。")
        except Exception as e:
            remix_success = False
            error_msg = str(e)
            print(f"[联动] 自动混音失败: {e}")
            
            # 触发失败事件并回滚
            try:
                from core.event_bus import get_event_bus
                from core.state_manager import get_state_manager
                event_bus = get_event_bus()
                state_manager = get_state_manager()
                if id_str:
                    event_bus.emit_remix_failed(id_str, error_msg)
                    state_manager.rollback_status(id_str, target_status="pending")
                    print(f"[状态管理] ⚠️ 状态已回滚至 pending（混音失败）")
            except ImportError:
                pass

    # 打包文件到最终文件夹（无论是否生成视频）
    should_package = schedule_date and id_str
    
    if should_package:
        try:
            final_dir = get_final_output_dir(schedule_date, title)
            final_dir.mkdir(parents=True, exist_ok=True)
            
            # 收集所有相关文件（在output根目录中）
            files_to_move = []
            import glob
            
            # 封面
            cover_pattern = str(unified_output_dir / f"{id_str}_cover.png")
            cover_files = glob.glob(cover_pattern)
            if cover_files:
                files_to_move.append(Path(cover_files[0]))
            
            # 歌单
            playlist_pattern = str(unified_output_dir / f"{id_str}_playlist.csv")
            playlist_files = glob.glob(playlist_pattern)
            if playlist_files:
                files_to_move.append(Path(playlist_files[0]))
            
            # 音频（支持两种命名）
            audio_patterns = [
                str(unified_output_dir / f"{id_str}_full_mix.mp3"),
                str(unified_output_dir / f"{id_str}_playlist_full_mix.mp3"),
            ]
            for pattern in audio_patterns:
                audio_files = glob.glob(pattern)
                if audio_files:
                    files_to_move.append(Path(audio_files[0]))
                    break
            
            # 视频（如果已生成）
            video_patterns = [
                str(unified_output_dir / f"{id_str}_youtube.mp4"),
                str(unified_output_dir / f"{id_str}_youtube.mov"),
            ]
            for pattern in video_patterns:
                video_files = glob.glob(pattern)
                if video_files:
                    files_to_move.append(Path(video_files[0]))
                    break
            
            # YouTube相关文件
            youtube_patterns = [
                str(unified_output_dir / f"{id_str}_youtube*.srt"),
                str(unified_output_dir / f"{id_str}_youtube*.txt"),
                str(unified_output_dir / f"{id_str}_youtube*.csv"),
                str(unified_output_dir / f"{id_str}_full_mix_timeline.csv"),
            ]
            for pattern in youtube_patterns:
                found = glob.glob(pattern)
                files_to_move.extend([Path(f) for f in found])
            
            # 移动所有文件到最终文件夹
            moved_count = 0
            skipped_count = 0
            for src_file in files_to_move:
                if src_file.exists():
                    dst_file = final_dir / src_file.name
                    # 如果源文件在unified_output_dir，移动到最终文件夹
                    # 如果源文件已经在最终文件夹，跳过（避免重复移动）
                    if src_file.parent == unified_output_dir:
                        if not dst_file.exists():
                            shutil.move(str(src_file), str(dst_file))
                            moved_count += 1
                        else:
                            # 目标已存在，删除源文件（可能是重复的）
                            src_file.unlink()
                            skipped_count += 1
                    elif src_file.parent == final_dir:
                        # 文件已在最终文件夹，跳过
                        skipped_count += 1
                    else:
                        # 文件在其他位置，复制到最终文件夹
                        if not dst_file.exists():
                            shutil.copy2(str(src_file), str(dst_file))
                            moved_count += 1
            
            if moved_count > 0:
                print(f"[打包] ✅ 已将 {moved_count} 个文件打包到: {final_dir.name}")
            if skipped_count > 0:
                print(f"[打包] ℹ️  跳过 {skipped_count} 个已存在的文件")
        except Exception as e:
            print(f"[打包] ⚠️  打包失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 自动查找刚生成的cover和full_mix音频（从统一输出目录）
    if getattr(args, "no_video", False):
        print("[视频合成] 已按 --no-video 跳过视频生成。")
        sys_exit_guard = False
    else:
        # 使用统一输出目录（从main返回）
        import glob
        import re
        # unified_output_dir 已从main返回
        
        # 初始化success变量，避免未定义错误
        success = False
        video_path = None  # 初始化变量，避免未定义错误
        
        # 优先查找文件：1) output根目录 2) 最终文件夹（如果已打包） 3) 旧目录（兼容性）
        cover_path = None
        audio_path = None
        
        # 1. 优先在output根目录查找（使用id_str精确匹配）
        if 'id_str' in locals() and id_str:
            cover_candidate = unified_output_dir / f"{id_str}_cover.png"
            audio_candidates = [
                unified_output_dir / f"{id_str}_full_mix.mp3",
                unified_output_dir / f"{id_str}_playlist_full_mix.mp3",
            ]
            if cover_candidate.exists():
                cover_path = cover_candidate
            for audio_candidate in audio_candidates:
                if audio_candidate.exists():
                    audio_path = audio_candidate
                    break
        
        # 2. 如果未找到且id_str已确定，检查最终文件夹（如果已打包）
        if (not cover_path or not audio_path) and 'id_str' in locals() and id_str and schedule_date and title:
            try:
                final_dir = get_final_output_dir(schedule_date, title)
                if final_dir.exists():
                    if not cover_path:
                        cover_final = final_dir / f"{id_str}_cover.png"
                        if cover_final.exists():
                            cover_path = cover_final
                    if not audio_path:
                        audio_final_candidates = [
                            final_dir / f"{id_str}_full_mix.mp3",
                            final_dir / f"{id_str}_playlist_full_mix.mp3",
                        ]
                        for audio_final in audio_final_candidates:
                            if audio_final.exists():
                                audio_path = audio_final
                                break
            except Exception:
                pass
        
        # 3. 如果仍未找到，在output根目录中使用通配符查找（兼容旧逻辑）
        if not cover_path:
            cover_files = sorted(glob.glob(str(unified_output_dir / "*_cover.png")), reverse=True)
            if cover_files:
                cover_path = Path(cover_files[0])
        
        if not audio_path:
            audio_files = sorted(glob.glob(str(unified_output_dir / "*_full_mix.mp3")), reverse=True)
            if audio_files:
                audio_path = Path(audio_files[0])
        
        # 4. 最后的兼容性回退（旧目录结构）
        if not cover_path:
            old_cover_files = sorted(glob.glob(str(Path("output/cover") / "*.png")), reverse=True)
            if old_cover_files:
                cover_path = Path(old_cover_files[0])
        
        if not audio_path:
            old_audio_files = sorted(glob.glob(str(Path("output/audio") / "*_full_mix.mp3")), reverse=True)
            if old_audio_files:
                audio_path = Path(old_audio_files[0])
        
        if not cover_path or not audio_path:
            print("[视频合成] 未找到cover或full_mix音频，跳过视频生成。")
            if not cover_path:
                print(f"  ⚠️  封面文件不存在（查找路径：output根目录、最终文件夹、旧目录）")
            if not audio_path:
                print(f"  ⚠️  音频文件不存在（查找路径：output根目录、最终文件夹、旧目录）")
        else:
            # 从文件名提取ID（如果还未确定）
            if 'id_str' not in locals() or not id_str:
                if audio_path:
                    m = re.search(r'(\d{8})', str(audio_path.name))
                    if m:
                        id_str = m.group(1)
                    else:
                        id_str = audio_path.stem.replace('_full_mix', '').replace('_playlist_full_mix', '')
            
            # 视频输出到统一目录，文件名与SRT同名（不含扩展名）
            video_base_name = f"{id_str}_youtube"
            video_path = unified_output_dir / f"{video_base_name}.mp4"
            
            # 获取音频时长（用于explicit模式）
            audio_duration_sec = None
            if args.duration_fix == "explicit":
                try:
                    import subprocess
                    probe_cmd = [
                        "ffprobe", "-v", "error",
                        "-select_streams", "a:0",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        str(audio_path)
                    ]
                    result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0 and result.stdout.strip():
                        audio_duration_sec = float(result.stdout.strip())
                        print(f"[时长修复] 方案B：音频时长 = {audio_duration_sec:.3f}秒 ({audio_duration_sec/60:.1f}分钟)")
                except Exception as e:
                    print(f"[警告] 无法获取音频时长，将使用方案A(30fps)代替: {e}")
                    args.duration_fix = "30fps"  # 回退到30fps
            
            import time
        # 构造主/备份编码命令（支持4种方法：x264/vtb/nvenc/mjpeg + 时长修复）
        def build_cmd(codec: str, output_path: Path):
            base = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
            
            # 方案B：显式时长裁剪（在输入阶段限制）
            if args.duration_fix == "explicit" and audio_duration_sec is not None:
                base.extend(["-loop", "1", "-t", str(audio_duration_sec), "-i", str(cover_path)])
            else:
                base.extend(["-loop", "1", "-i", str(cover_path)])
            
            base.append("-i")
            base.append(str(audio_path))
            
            # 视频滤镜：缩放+填充+帧率控制
            sw, sh = 3840, 2160  # 4K分辨率
            
            # 帧率控制策略
            if args.duration_fix == "30fps":
                # 方案A：用30fps固定帧率（更细时间颗粒度，减少四舍五入误差）
                filter_fps = 30
                if args.fps == 1:
                    # 使用 round=down 确保向下取整
                    vf = f"scale={sw}:{sh}:force_original_aspect_ratio=decrease,pad={sw}:{sh}:(ow-iw)/2:(oh-ih)/2,fps=30:round=down"
                else:
                    vf = f"scale={sw}:{sh}:force_original_aspect_ratio=decrease,pad={sw}:{sh}:(ow-iw)/2:(oh-ih)/2,fps={filter_fps}"
            elif args.duration_fix == "1fps-precise":
                # 方案C：保持1fps但用向下取整（最优化：文件小、编码快、时长准确）
                vf = f"scale={sw}:{sh}:force_original_aspect_ratio=decrease,pad={sw}:{sh}:(ow-iw)/2:(oh-ih)/2,fps=1:round=down"
            else:
                # 原逻辑或explicit：使用原始fps
                filter_fps = args.fps
                vf = f"scale={sw}:{sh}:force_original_aspect_ratio=decrease,pad={sw}:{sh}:(ow-iw)/2:(oh-ih)/2,fps={filter_fps}"
            
            base.extend(["-vf", vf])
            base.extend(["-pix_fmt", args.pix_fmt])
            
            # 方案C：添加精确时间控制
            if args.duration_fix == "1fps-precise":
                # 使用VFR模式和精确时间戳传递
                base.extend(["-vsync", "vfr", "-fps_mode", "passthrough"])
            
            # 编码器配置
            if codec == "h264_videotoolbox":
                # 码率设置：30fps需要更高，1fps-precise保持原码率（最优）
                if args.duration_fix == "30fps":
                    v_bitrate, maxrate, bufsize = "6M", "8M", "12M"
                else:
                    v_bitrate, maxrate, bufsize = args.v_bitrate, "4M", "6M"
                base += ["-c:v", "h264_videotoolbox", "-b:v", v_bitrate, "-maxrate", maxrate, "-bufsize", bufsize]
            elif codec == "h264_nvenc":
                base += ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "23"]
            elif codec == "mjpeg":
                # MJPEG 使用 .mov 容器更稳定
                output_path = output_path.parent / f"{output_path.stem}.mov"
                base += ["-c:v", "mjpeg", "-q:v", "3"]
            else:  # libx264 (默认)
                base += ["-c:v", "libx264", "-preset", args.preset, "-crf", args.crf]
            
            # 方案A和C：不在输出端设-r，让filter主导（避免时间戳冲突）
            if args.duration_fix not in ["30fps", "1fps-precise"]:
                base.extend(["-r", str(args.fps)])
            
            # 音频编码
            if args.audio_copy:
                base += ["-c:a", "copy"]
            else:
                base += ["-c:a", "aac", "-b:a", args.v_audio_bitrate]
            
            # 时长控制：方案B已经有-t限制，方案A和原逻辑都用-shortest
            if args.duration_fix != "explicit":
                base.append("-shortest")
            
            base.extend(["-movflags", "+faststart", str(output_path)])
            return base, output_path

        # 检测可用的编码器
        import platform
        import subprocess
        encoders_available = []
        try:
            enc_output = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], 
                                      capture_output=True, text=True, timeout=5)
            encoders_text = enc_output.stdout + enc_output.stderr
            
            # 检查各编码器是否可用
            is_macos = platform.system().lower() == "darwin"
            if is_macos and "h264_videotoolbox" in encoders_text:
                encoders_available.append("h264_videotoolbox")
            if "h264_nvenc" in encoders_text:
                encoders_available.append("h264_nvenc")
            if "mjpeg" in encoders_text:
                encoders_available.append("mjpeg")
            # libx264 总是可用（作为回退）
            encoders_available.append("libx264")
        except Exception:
            # 如果检查失败，默认使用 libx264
            encoders_available = ["libx264"]
        
        preferred = []
        if args.codec_v == "auto":
            # 尝试从每周测试配置中读取最佳编码器
            best_encoder_config = None
            try:
                import json
                config_file = REPO_ROOT / "config" / "best_encoder.json"
                if config_file.exists():
                    with config_file.open("r", encoding="utf-8") as f:
                        best_encoder_config = json.load(f)
                    best_encoder = best_encoder_config.get("best_encoder")
                    # 验证最佳编码器是否仍然可用
                    if best_encoder and best_encoder in encoders_available:
                        preferred = [best_encoder]
                        print(f"[视频合成] 使用每周测试推荐编码器: {best_encoder}")
            except Exception:
                pass  # 如果读取失败，继续使用默认逻辑
            
            # 如果没有配置或配置的编码器不可用，使用默认逻辑
            if not preferred:
                # 自动选择：优先硬件加速，回退到软件编码
                # 注意：MJPEG虽然速度快但文件体积大，在自动模式下不优先选择
                for codec in ["h264_videotoolbox", "h264_nvenc", "libx264"]:
                    if codec in encoders_available:
                        preferred.append(codec)
                        print(f"[视频合成] 自动选择编码器: {codec}")
                        break  # 只使用第一个可用的
                if not preferred:
                    preferred = ["libx264"]  # 最后的回退
                    print(f"[视频合成] 使用默认编码器: libx264")
        else:
            # 用户指定编码器
            if args.codec_v in encoders_available:
                preferred = [args.codec_v]
            else:
                print(f"[警告] 指定的编码器 {args.codec_v} 不可用，回退到 libx264")
                preferred = ["libx264"]

        # 环境检查和提示
        try:
            import json
            from datetime import datetime
            config_file = REPO_ROOT / "config" / "best_encoder.json"
            env_fingerprint_file = REPO_ROOT / "config" / "env_fingerprint.json"
            
            # 检查是否需要初始化
            needs_init = False
            if not config_file.exists() or not env_fingerprint_file.exists():
                needs_init = True
            else:
                # 检查环境是否变化
                try:
                    from scripts.init_env import (
                        get_environment_fingerprint,
                        load_env_fingerprint,
                        has_environment_changed
                    )
                    current_fp = get_environment_fingerprint()
                    saved_fp = load_env_fingerprint()
                    if has_environment_changed(current_fp, saved_fp):
                        needs_init = True
                except Exception:
                    pass
            
            if needs_init:
                print(f"\n[提示] 检测到环境未初始化或环境已变化")
                print(f"      建议运行初始化: python scripts/init_env.py")
                print(f"      或强制重新测试: python scripts/init_env.py --force")
            elif config_file.exists():
                # 检查是否需要每周测试
                with config_file.open("r", encoding="utf-8") as f:
                    test_config = json.load(f)
                test_date_str = test_config.get("test_date")
                if test_date_str:
                    test_date = dt.datetime.fromisoformat(test_date_str)
                    days_since = (dt.datetime.now() - test_date).days
                    if days_since >= 7:
                        print(f"\n[提示] 上次编码器测试已过去 {days_since} 天")
                        print(f"      建议运行每周测试: python scripts/weekly_bench.py")
        except Exception:
            pass
        
        # 只有在找到文件时才继续视频合成
        if not video_path:
            # 如果未找到文件，跳过视频合成
            if RICH_AVAILABLE:
                console = Console()
            # 直接结束，不进行后续视频合成和打包
            print("[打包] ℹ️  资料未齐备，跳过打包")
        else:
            # 继续视频合成流程
            if RICH_AVAILABLE:
                console = Console()
                console.print(f"[cyan][视频合成] 目标: {video_path}[/cyan]")
                console.print(f"[cyan][视频合成] 可用编码器: {', '.join(encoders_available)}[/cyan]")
            else:
                print(f"[视频合成] 目标: {video_path}")
                print(f"[视频合成] 可用编码器: {', '.join(encoders_available)}")
            
            duration_fix_desc = {
                "30fps": "30fps固定帧率，时长误差≤1s（文件较大）",
                "1fps-precise": "1fps精确时间戳，时长准确（推荐：最快最小）",
                "explicit": "显式裁剪，最强一致性",
                "none": "原逻辑，可能有偏差"
            }
            if RICH_AVAILABLE:
                console.print(f"[cyan][时长修复] 使用方案: {args.duration_fix} ({duration_fix_desc.get(args.duration_fix, '未知')})[/cyan]")
            else:
                print(f"[时长修复] 使用方案: {args.duration_fix} ({duration_fix_desc.get(args.duration_fix, '未知')})")
            
            t0 = time.time()
            success = False
            final_video_path = video_path
            successful_codec = None
            for codec in preferred:
                cmd, output_path = build_cmd(codec, video_path)
                final_video_path = output_path  # 保存最终输出路径（mjpeg 可能需要 .mov）
                
                if RICH_AVAILABLE:
                    with console.status(f"[cyan]正在合成视频 ({codec})...", spinner="dots"):
                        try:
                            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                            rc = result.returncode
                        except Exception as e:
                            console.print(f"[yellow][视频合成] {codec} 失败: {e}[/yellow]")
                            continue
                    
                    if rc == 0:
                        success = True
                        successful_codec = codec
                        video_path = final_video_path  # 更新为实际输出路径
                        break
                    else:
                        console.print(f"[yellow][视频合成] {codec} 退出码 {rc}，尝试下一个编码器…[/yellow]")
                else:
                    print(f"[视频合成] 尝试编码器: {codec}")
                    try:
                        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                        for line in process.stdout:
                            print(line, end="")
                        rc = process.wait()
                        if rc == 0:
                            success = True
                            successful_codec = codec
                            video_path = final_video_path  # 更新为实际输出路径
                            break
                        else:
                            print(f"[视频合成] {codec} 退出码 {rc}，尝试下一个编码器…")
                    except Exception as e:
                        print(f"[视频合成] {codec} 失败: {e}，尝试下一个编码器…")
            t1 = time.time()
            if success:
                print(f"[视频合成] ✅ 视频已生成: {final_video_path}")
                print(f"[视频合成] 使用编码器: {successful_codec}")
                print(f"[视频合成] 编码耗时: {t1-t0:.1f} 秒")
                
                # 触发视频渲染完成事件（所有阶段成功，标记为completed）
                try:
                    from core.event_bus import get_event_bus
                    from core.state_manager import get_state_manager
                    event_bus = get_event_bus()
                    state_manager = get_state_manager()
                    
                    if id_str:
                        event_bus.emit_video_render_completed(id_str)
                        print(f"[状态管理] ✅ 所有阶段完成，状态已更新为 completed")
                except ImportError:
                    # 回退到旧方式
                    if schedule_date and schedule_master:
                        schedule_master.update_episode(
                            episode_id=id_str,
                            status="已完成"
                        )
                        schedule_master.save()
                        print(f"[排播表] ✅ 所有阶段完成，状态已更新为 已完成")
            else:
                # 视频生成失败，触发失败事件并回滚
                print(f"[视频合成] ❌ 所有编码器均失败")
                try:
                    from core.event_bus import get_event_bus
                    from core.state_manager import get_state_manager
                    event_bus = get_event_bus()
                    state_manager = get_state_manager()
                    
                    if id_str:
                        error_msg = "所有编码器均失败"
                        event_bus.emit_video_render_failed(id_str, error_msg)
                        state_manager.rollback_status(id_str, target_status="pending")
                        print(f"[状态管理] ⚠️ 状态已回滚至 pending（视频生成失败）")
                except ImportError:
                    # 回退到旧方式：保持pending状态
                    pass
                
                # 视频生成后，统一打包所有剩余文件（确保所有文件都被正确打包）
                if should_package:
                    try:
                        final_dir = get_final_output_dir(schedule_date, title)
                        final_dir.mkdir(parents=True, exist_ok=True)
                        
                        # 收集所有需要打包的文件（包括刚生成的视频和可能遗漏的文件）
                        all_files_to_package = []
                        import glob
                        
                        # 视频文件（优先）
                        if final_video_path and final_video_path.exists():
                            all_files_to_package.append(final_video_path)
                        
                        # 收集output根目录中所有与该期数相关的文件
                        for pattern in [
                            f"{id_str}_cover.png",
                            f"{id_str}_playlist.csv",
                            f"{id_str}_full_mix.mp3",
                            f"{id_str}_playlist_full_mix.mp3",
                            f"{id_str}_youtube.mp4",
                            f"{id_str}_youtube.mov",
                            f"{id_str}_youtube*.srt",
                            f"{id_str}_youtube*.txt",
                            f"{id_str}_youtube*.csv",
                            f"{id_str}_full_mix_timeline.csv",
                        ]:
                            found = list(unified_output_dir.glob(pattern))
                            all_files_to_package.extend(found)
                        
                        # 去重
                        all_files_to_package = list(set(all_files_to_package))
                        
                        # 移动所有文件到最终文件夹
                        moved_count = 0
                        for src_file in all_files_to_package:
                            if src_file.exists() and src_file.parent == unified_output_dir:
                                dst_file = final_dir / src_file.name
                                if not dst_file.exists():
                                    shutil.move(str(src_file), str(dst_file))
                                    moved_count += 1
                                elif src_file != dst_file:
                                    # 目标已存在，删除源文件（避免重复）
                                    src_file.unlink()
                        
                        if moved_count > 0:
                            print(f"[打包] ✅ 已将 {moved_count} 个文件（含视频）打包到: {final_dir.name}")
                    except Exception as e:
                        print(f"[打包] ⚠️  打包视频失败: {e}")
                        import traceback
                        traceback.print_exc()
        
        # 只有在成功生成视频后才生成上传CSV和更新排播表状态
        if success:
            # ===== 更新永恒排播表状态（仅在视频成功生成后） =====
            try:
                from schedule_master import ScheduleMaster
                from episode_status import STATUS_已完成
                schedule_master = ScheduleMaster.load()
                if schedule_master:
                    # 从id_str获取episode_id（可能是YYYYMMDD格式或YYYYMMDD_HHMMSS格式）
                    episode_id = id_str
                    if '_' in episode_id:
                        # 如果是YYYYMMDD_HHMMSS格式，提取YYYYMMDD部分
                        episode_id = episode_id.split('_')[0]
                    
                    # 检查是否已存在期数记录
                    ep = schedule_master.get_episode(episode_id)
                    if ep:
                        success_update = schedule_master.update_episode(
                            episode_id=episode_id,
                            status=STATUS_已完成
                        )
                        if success_update:
                            schedule_master.save()
                            print(f"[排播表] ✅ 排播表状态已更新为 {STATUS_已完成} (ID: {episode_id})")
                            
                            # 自动同步资源标记（基于分配）
                            print(f"[排播表] 🔄 自动同步图片使用标记...")
                            try:
                                images_synced = schedule_master.sync_images_from_assignments()
                                schedule_master.save()
                                if images_synced != 0:
                                    print(f"[排播表] ✅ 图片使用标记已同步（{images_synced:+d} 张）")
                                else:
                                    print(f"[排播表] ✅ 图片使用标记已是最新状态")
                            except Exception as e:
                                print(f"[排播表] ⚠️  同步图片标记失败: {e}")
                                import traceback
                                traceback.print_exc()
                    else:
                        print(f"[排播表] ⚠️  未找到期数记录 (ID: {episode_id})，跳过状态更新")
            except Exception as e:
                print(f"[排播表] ⚠️  更新排播表状态失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 自动生成YouTube上传csv（在统一目录）- 仅在成功生成视频后
        if success:
            csv_path = unified_output_dir / f"{video_base_name}_youtube_upload.csv"
            # 读取歌单标题、描述、时间轴（title已在main中生成）
            # 描述使用从YouTube资源生成的内容（如果存在）
            desc_file = unified_output_dir / f"{video_base_name}_description.txt"
            if desc_file.exists():
                description = desc_file.read_text(encoding="utf-8")
            else:
                # 使用 Kat Records 品牌风格的默认描述
                description = f"""{title} LP | Kat Records Presents Night Session

A new vinyl from Kat Records.
Recorded between analog dreams and digital precision.
Each LP is a coded emotion — pressed in silence, played in your world.

🎧 For: writers, designers, dreamers, night thinkers.
☕ Sounds: tape hiss, jazz chords, gentle rain, heartbeat tempo.
💿 Side A – code breathes rhythm. Side B – rhythm decodes time.

Perfect for: vibe coding, night study, cozy coffee breaks, deep focus, journaling, slow mornings.

Produced by Kat Records.
Kat Records is where emotion meets algorithm.
Subscribe for the next LP release and join the sonic lab:
https://www.youtube.com/@Run-Baby-Run/playlists"""
            # 读取时间轴（在统一目录中查找）
            timeline_files = sorted(glob.glob(str(unified_output_dir / f"{id_str}_full_mix_timeline.csv")), reverse=True)
            if not timeline_files:
                # 回退到旧目录
                old_timeline_files = sorted(glob.glob(str(Path("output/audio") / f"{id_str}_full_mix_timeline.csv")), reverse=True)
                if old_timeline_files:
                    timeline_files = old_timeline_files
            timeline_str = ""
            if timeline_files:
                with open(timeline_files[0], encoding="utf-8") as tf:
                    timeline_str = tf.read()
            with open(csv_path, "w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(["video_file", "title", "description", "made_for_kids", "timeline"])
                writer.writerow([
                    video_path.name,
                    title,  # 使用从main生成的title
                    description,
                    "no",
                    timeline_str
                ])
            print(f"[YouTube上传] 信息csv已生成: {csv_path}")
