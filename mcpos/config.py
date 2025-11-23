"""
McPOS 级别配置

提供 McPOS 系统的基础配置，包括路径、日志、频道等设置。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class McPOSConfig:
    """McPOS 系统配置"""
    
    # 仓库根目录
    repo_root: Path = Path(__file__).parent.parent
    
    # 频道目录
    channels_root: Path = repo_root / "channels"
    
    # 图库目录
    images_pool_root: Path = repo_root / "images_pool"
    images_pool_available: Path = images_pool_root / "available"
    images_pool_used: Path = images_pool_root / "used"
    
    # 资源目录（字体、蒙版等）
    assets_root: Path = repo_root / "assets"
    fonts_dir: Path = assets_root / "fonts"
    design_dir: Path = assets_root / "design"  # 设计资源目录（蒙版等）
    
    # Cover generation settings
    cover_font_path: Optional[Path] = None  # 封面字体路径（可选，如果为 None 则使用系统字体）
    
    # Debug settings
    debug_ffprobe: bool = False  # 是否保存 ffprobe 调试输出到文件（用于排查视频校验问题）
    
    # 日志目录
    logs_dir: Path = repo_root / "mcpos" / "logs"
    
    # YouTube 上传配置
    youtube_client_secrets_file: Optional[Path] = None
    youtube_token_file: Optional[Path] = None
    youtube_privacy_status: str = "private"  # 默认设为 private，配合排播使用
    youtube_category_id: int = 10
    youtube_default_tags: List[str] = field(default_factory=lambda: ["lofi", "music", "Kat Records", "chill"])
    youtube_playlist_id: Optional[str] = None  # 默认从 config.yaml 读取
    youtube_default_language: str = "en"  # 必须设置为 "en"，字幕上传需要
    youtube_max_retries: int = 5
    youtube_schedule: bool = False
    
    # 注意：McPOS 原则是完全独立，不引用外部文件夹的业务逻辑
    # 这些路径仅用于文档说明，实际代码不应 import 这些路径下的模块
    
    def __post_init__(self):
        """确保必要的目录存在，初始化默认配置"""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.images_pool_available.mkdir(parents=True, exist_ok=True)
        self.images_pool_used.mkdir(parents=True, exist_ok=True)
        
        # YouTube 配置默认值
        if self.youtube_client_secrets_file is None:
            self.youtube_client_secrets_file = self.repo_root / "config" / "google" / "client_secrets.json"
        
        if self.youtube_token_file is None:
            self.youtube_token_file = self.repo_root / "config" / "google" / "youtube_token.json"
        
        # 从 config.yaml 读取 YouTube 配置
        config_yaml = self.repo_root / "config" / "config.yaml"
        if config_yaml.exists():
            try:
                import yaml
                with config_yaml.open("r", encoding="utf-8") as f:
                    config_data = yaml.safe_load(f) or {}
                    youtube_config = config_data.get("youtube", {})
                    
                    # 读取 playlist_id（如果未设置）
                    if self.youtube_playlist_id is None and youtube_config.get("playlist_id"):
                        self.youtube_playlist_id = youtube_config["playlist_id"]
                    
                    # 读取 privacyStatus（如果 config.yaml 中设置了）
                    # 注意：如果 config.yaml 中是 "unlisted"，我们需要强制改为 "private" 以配合排播
                    upload_defaults = youtube_config.get("upload_defaults", {})
                    if upload_defaults.get("privacyStatus"):
                        privacy_status_from_config = str(upload_defaults["privacyStatus"])
                        # 如果配置是 "unlisted"，强制改为 "private"（配合排播）
                        if privacy_status_from_config == "unlisted":
                            self.youtube_privacy_status = "private"
                        else:
                            self.youtube_privacy_status = privacy_status_from_config
            except Exception:
                # 如果读取失败，保持默认值
                pass


# 全局配置实例
_config: Optional[McPOSConfig] = None


def get_config() -> McPOSConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = McPOSConfig()
    return _config


def set_config(config: McPOSConfig) -> None:
    """设置全局配置实例（主要用于测试）"""
    global _config
    _config = config


def get_openai_api_key() -> Optional[str]:
    """
    获取 OpenAI API Key
    
    优先级：
    1. 从配置文件读取：config/openai_api_key.txt
    2. 从环境变量读取：OPENAI_API_KEY
    
    Returns:
        API key 字符串，如果都未设置则返回 None
    """
    config = get_config()
    api_key_file = config.repo_root / "config" / "openai_api_key.txt"
    
    # 优先从文件读取
    if api_key_file.exists():
        try:
            api_key = api_key_file.read_text(encoding="utf-8").strip()
            if api_key:
                return api_key
        except Exception:
            # 文件读取失败，继续尝试环境变量
            pass
    
    # 从环境变量读取
    return os.getenv("OPENAI_API_KEY")

