#!/usr/bin/env python3
# coding: utf-8
"""
统一API配置管理系统

支持多个API提供商：OpenAI、Google Gemini等
一次性配置，持久化存储
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

try:
    REPO_ROOT = Path(__file__).resolve().parent.parent.parent
except Exception:
    REPO_ROOT = Path.cwd()

# API配置文件名
API_CONFIG_FILE = REPO_ROOT / "config" / "api_config.json"

# 支持的API提供商
API_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "key_file": "openai_api_key.txt",
        "key_prefix": "sk-",
        "model": "gpt-4o-mini",
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1",
        "key_env": "GEMINI_API_KEY",
        "key_file": "gemini_api_key.txt",
        "key_prefix": "",  # Gemini密钥没有固定前缀
        "model": "gemini-pro",
    },
}

# 默认API提供商（优先级）
DEFAULT_PROVIDER = "openai"


class APIConfig:
    """API配置管理器"""
    
    def __init__(self):
        self.config_path = API_CONFIG_FILE
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        if not self.config_path.exists():
            return {
                "provider": DEFAULT_PROVIDER,
                "keys": {},
            }
        
        # 尝试使用新的安全文件读取工具，如果不可用则回退到原始方法
        try:
            # 尝试导入错误处理工具
            try:
                from src.core.error_handlers import safe_file_read
                content = safe_file_read(self.config_path)
                return json.loads(content)
            except (ImportError, ModuleNotFoundError):
                # 如果无法导入新工具，使用原始方法
                with self.config_path.open("r", encoding="utf-8") as f:
                    return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"⚠️  加载API配置失败: {type(e).__name__}: {e}")
            return {
                "provider": DEFAULT_PROVIDER,
                "keys": {},
            }
        except Exception as e:
            print(f"⚠️  加载API配置失败: {type(e).__name__}: {e}")
            return {
                "provider": DEFAULT_PROVIDER,
                "keys": {},
            }
    
    def _save_config(self):
        """保存配置文件"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        
        # 设置文件权限（仅所有者可读写）
        try:
            os.chmod(self.config_path, 0o600)
        except (OSError, AttributeError) as e:
            # Windows可能不支持chmod，忽略错误
            pass
    
    def get_api_key(self, provider: Optional[str] = None) -> Tuple[Optional[str], str]:
        """
        获取API密钥
        
        Args:
            provider: API提供商名称（如"openai", "gemini"），如果为None则使用配置的默认提供商
        
        Returns:
            (api_key, source): API密钥和来源说明
        """
        if provider is None:
            provider = self.config.get("provider", DEFAULT_PROVIDER)
        
        if provider not in API_PROVIDERS:
            return None, f"未知的API提供商: {provider}"
        
        provider_info = API_PROVIDERS[provider]
        
        # 优先级1：环境变量
        env_key = os.getenv(provider_info["key_env"])
        if env_key and env_key.strip():
            return env_key.strip(), f"环境变量 ({provider_info['key_env']})"
        
        # 优先级2：配置文件中的密钥
        saved_key = self.config.get("keys", {}).get(provider)
        if saved_key and saved_key.strip():
            return saved_key.strip(), f"配置文件 ({provider})"
        
        # 优先级3：传统密钥文件（向后兼容）
        key_file = REPO_ROOT / "config" / provider_info["key_file"]
        if key_file.exists():
            try:
                key = key_file.read_text(encoding="utf-8").strip()
                if key:
                    # 迁移到新配置
                    self.config.setdefault("keys", {})[provider] = key
                    self._save_config()
                    return key, f"密钥文件 ({provider_info['key_file']})，已迁移到配置"
            except (FileNotFoundError, PermissionError, UnicodeDecodeError, OSError):
                # 密钥文件读取失败，跳过
                pass
        
        return None, "未找到"
    
    def set_api_key(self, provider: str, key: str, save: bool = True):
        """
        设置API密钥
        
        Args:
            provider: API提供商名称
            key: API密钥
            save: 是否保存到配置文件
        """
        if provider not in API_PROVIDERS:
            raise ValueError(f"未知的API提供商: {provider}")
        
        self.config.setdefault("keys", {})[provider] = key.strip()
        
        if save:
            self._save_config()
    
    def get_provider(self) -> str:
        """获取当前配置的API提供商"""
        return self.config.get("provider", DEFAULT_PROVIDER)
    
    def set_provider(self, provider: str):
        """设置默认API提供商"""
        if provider not in API_PROVIDERS:
            raise ValueError(f"未知的API提供商: {provider}")
        self.config["provider"] = provider
        self._save_config()
    
    def require_api_key(self, provider: Optional[str] = None, interactive: bool = False) -> str:
        """
        强制要求API密钥，如果不存在则报错或退出
        
        Args:
            provider: API提供商名称，如果为None则使用默认提供商
            interactive: 是否允许交互式配置（当前不支持，未来可扩展）
        
        Returns:
            API密钥字符串
        
        Raises:
            SystemExit: 如果API不存在
        """
        if provider is None:
            provider = self.get_provider()
        
        api_key, source = self.get_api_key(provider)
        
        if api_key:
            # 验证格式
            provider_info = API_PROVIDERS[provider]
            if provider_info["key_prefix"]:
                if not api_key.startswith(provider_info["key_prefix"]):
                    print(f"❌ {provider_info['name']} API密钥格式错误：应该以 '{provider_info['key_prefix']}' 开头")
                    print(f"   来源: {source}")
                    print()
                    print("💡 请运行配置向导：")
                    print("   python scripts/local_picker/configure_api.py")
                    sys.exit(1)
            
            return api_key
        
        # API不存在，强制要求配置
        provider_info = API_PROVIDERS.get(provider, {"name": provider})
        print()
        print("=" * 70)
        print(f"❌ 错误：未找到 {provider_info['name']} API 密钥")
        print("=" * 70)
        print()
        print("🔑 API密钥是必需的，必须配置后才能继续。")
        print()
        print("📝 配置方法：")
        print(f"   1. 运行配置向导: python scripts/local_picker/configure_api.py")
        print(f"   2. 使用环境变量: export {provider_info.get('key_env', 'API_KEY')}='your-key'")
        print(f"   3. 手动编辑配置: {self.config_path}")
        print()
        print("💡 提示：配置向导会引导您一次性配置所有API，")
        print("   配置后无需重复输入，系统会自动使用。")
        print()
        sys.exit(1)
    
    def get_base_url(self, provider: Optional[str] = None) -> str:
        """获取API基础URL"""
        if provider is None:
            provider = self.get_provider()
        
        provider_info = API_PROVIDERS.get(provider, {})
        return provider_info.get("base_url", "")
    
    def get_model(self, provider: Optional[str] = None) -> str:
        """获取默认模型名称"""
        if provider is None:
            provider = self.get_provider()
        
        provider_info = API_PROVIDERS.get(provider, {})
        return provider_info.get("model", "")


# 全局配置实例
_config_instance: Optional[APIConfig] = None


def get_api_config() -> APIConfig:
    """获取全局API配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = APIConfig()
    return _config_instance


def require_api_key(provider: Optional[str] = None) -> str:
    """
    强制要求API密钥（便捷函数）
    
    Args:
        provider: API提供商名称，如果为None则使用默认提供商
    
    Returns:
        API密钥字符串
    
    Raises:
        SystemExit: 如果API不存在
    """
    config = get_api_config()
    return config.require_api_key(provider, interactive=False)


def get_api_base_url(provider: Optional[str] = None) -> str:
    """获取API基础URL（便捷函数）"""
    config = get_api_config()
    return config.get_base_url(provider)


def get_api_model(provider: Optional[str] = None) -> str:
    """获取默认模型（便捷函数）"""
    config = get_api_config()
    return config.get_model(provider)

