#!/usr/bin/env python3
# coding: utf-8
"""
配置常量模块

集中管理硬编码的配置值，包括：
- 超时时间
- 默认路径
- 重试次数
- 其他魔法数字

这些值应该从配置文件读取，但在过渡期间集中管理。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

# ============================================================================
# 超时配置（秒）
# ============================================================================

# 子进程超时配置
STAGE1_PLAYLIST_TIMEOUT = 300  # 阶段1：歌单和封面生成超时（5分钟）
STAGE2_YOUTUBE_ASSETS_TIMEOUT = 120  # 阶段2：YouTube资源生成超时（2分钟）
STAGE3_AUDIO_TIMEOUT = 600  # 阶段3：音频混音超时（10分钟）
STAGE4_VIDEO_TIMEOUT = 3600  # 阶段4：视频生成超时（60分钟）

# 通用超时
DEFAULT_SUBPROCESS_TIMEOUT = 300  # 默认子进程超时（5分钟）
API_REQUEST_TIMEOUT = 30  # API请求超时（30秒）

# ============================================================================
# 重试配置
# ============================================================================

# 上传重试
UPLOAD_MAX_RETRIES = 5  # 上传最大重试次数
UPLOAD_RETRY_DELAY_BASE = 2  # 重试延迟基数（秒），使用指数退避：2^retry_count

# API调用重试
API_MAX_RETRIES = 3  # API调用最大重试次数
API_RETRY_DELAY_BASE = 1  # API重试延迟基数（秒）

# ============================================================================
# 默认路径配置
# ============================================================================

def get_repo_root() -> Path:
    """获取项目根目录"""
    try:
        # 尝试从当前模块位置推断
        current_file = Path(__file__).resolve()
        return current_file.parent.parent.parent
    except Exception:
        # 回退到当前工作目录
        return Path.cwd()


REPO_ROOT = get_repo_root()

# 配置文件路径
CONFIG_DIR = REPO_ROOT / "config"
CONFIG_YAML = CONFIG_DIR / "config.yaml"
API_CONFIG_JSON = CONFIG_DIR / "api_config.json"
SCHEDULE_MASTER_JSON = CONFIG_DIR / "schedule_master.json"
BEST_ENCODER_JSON = CONFIG_DIR / "best_encoder.json"

# 输出目录
OUTPUT_DIR = REPO_ROOT / "output"
LOGS_DIR = REPO_ROOT / "logs"
ASSETS_DIR = REPO_ROOT / "assets"

# Google OAuth 配置路径
GOOGLE_CONFIG_DIR = CONFIG_DIR / "google"
CLIENT_SECRETS_FILE = GOOGLE_CONFIG_DIR / "client_secrets.json"
YOUTUBE_TOKEN_FILE = GOOGLE_CONFIG_DIR / "youtube_token.json"

# ============================================================================
# 默认值配置
# ============================================================================

# YouTube上传默认值
DEFAULT_PRIVACY_STATUS = "unlisted"  # private, unlisted, public
DEFAULT_CATEGORY_ID = 10  # Music
DEFAULT_TAGS = ["lofi", "music", "Kat Records", "chill"]
DEFAULT_LANGUAGE = "en"
DEFAULT_QUOTA_LIMIT_DAILY = 9000

# API配置默认值
DEFAULT_API_PROVIDER = "openai"
DEFAULT_MODEL_OPENAI = "gpt-4o-mini"
DEFAULT_MODEL_GEMINI = "gemini-pro"

# 排播表默认值
DEFAULT_SCHEDULE_INTERVAL_DAYS = 7  # 默认排播间隔（天）

# ============================================================================
# 文件大小限制（字节）
# ============================================================================

MAX_THUMBNAIL_SIZE = 2 * 1024 * 1024  # 2MB
MAX_THUMBNAIL_DIMENSION = 1280  # 最大尺寸（宽或高，像素）
AUTO_CHUNK_UPLOAD_SIZE = 256 * 1024 * 1024  # 256MB，大于此大小自动分块上传

# ============================================================================
# 其他配置
# ============================================================================

# 日志配置
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB
LOG_BACKUP_COUNT = 5  # 保留最近5个日志文件

# 随机数种子（用于可复现性）
SCHEDULE_RANDOM_SEED = 42


def get_stage_timeout(stage: int) -> int:
    """
    获取指定阶段的超时时间
    
    Args:
        stage: 阶段编号（1-4）
    
    Returns:
        超时时间（秒）
    """
    timeouts: Dict[int, int] = {
        1: STAGE1_PLAYLIST_TIMEOUT,
        2: STAGE2_YOUTUBE_ASSETS_TIMEOUT,
        3: STAGE3_AUDIO_TIMEOUT,
        4: STAGE4_VIDEO_TIMEOUT,
    }
    return timeouts.get(stage, DEFAULT_SUBPROCESS_TIMEOUT)

