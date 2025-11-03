#!/usr/bin/env python3
# coding: utf-8
"""
向加菲众问好 - API问候功能
每次启动时调用，验证API并让加菲众开心
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from urllib import request as req
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))

from api_config import require_api_key, get_api_base_url, get_api_model, get_api_config


def greet_garfield_with_openai(api_key: str, base_url: str, model: str) -> tuple[bool, str]:
    """
    使用OpenAI API向加菲众问好
    """
    try:
        # 生成随机种子，确保每次问候都不同
        import random
        seed = random.randint(1, 1000000)
        
        sys_prompt = (
            "You are a friendly assistant greeting Garfield (加菲众), "
            "the boss and producer of KAT Records Studio. "
            "Create a warm, creative, and unique greeting message in Chinese. "
            "Each greeting should be different and bring joy. "
            "Keep it concise (1-2 sentences), friendly, and make Garfield smile. "
            "Use varied expressions and avoid repetition."
        )
        
        user_prompt = (
            f"Create a unique greeting for Garfield today. "
            f"Make it fresh and delightful. "
            f"Seed: {seed}"
        )
        
        payload = {
            "model": model,
            "temperature": 0.8,  # 更高温度确保多样性
            "max_tokens": 50,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        
        data = json.dumps(payload).encode("utf-8")
        http_req = req.Request(
            f"{base_url}/chat/completions",
            data=data,
            method="POST"
        )
        http_req.add_header("Content-Type", "application/json")
        http_req.add_header("Authorization", f"Bearer {api_key}")
        
        # 使用 certifi 的证书文件（解决 macOS SSL 证书问题）
        import ssl
        try:
            import certifi
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ssl_context = ssl.create_default_context()
        
        with req.urlopen(http_req, timeout=10, context=ssl_context) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        
        if isinstance(body, dict):
            choices = body.get("choices") or []
            if choices and isinstance(choices, list):
                msg = choices[0].get("message") or {}
                greeting = (msg.get("content") or "").strip()
                if greeting:
                    return True, greeting
        
        return False, "❌ API返回空响应"
        
    except req.HTTPError as e:
        if e.code == 401:
            return False, "❌ API密钥无效，请检查配置"
        elif e.code == 429:
            return False, "❌ API请求频率限制，请稍后再试"
        else:
            return False, f"❌ API请求失败: HTTP {e.code}"
    except Exception as e:
        error_msg = str(e)
        # 检测SSL证书错误
        if "SSL" in error_msg or "CERTIFICATE" in error_msg or "certificate verify failed" in error_msg.lower():
            return False, f"❌ SSL证书验证失败\n\n这是macOS常见问题，修复方法：\n1. 运行修复脚本: python scripts/fix_ssl_certificates.py\n2. 或手动运行: python -m pip install --upgrade certifi\n3. 或运行: /Applications/Python\\ 3.*/Install\\ Certificates.command"
        return False, f"❌ API调用失败: {error_msg}"


def greet_garfield_with_gemini(api_key: str, base_url: str, model: str) -> tuple[bool, str]:
    """
    使用Google Gemini API向加菲众问好
    """
    try:
        import random
        seed = random.randint(1, 1000000)
        
        prompt = (
            "You are a friendly assistant greeting Garfield (加菲众), "
            "the boss and producer of KAT Records Studio. "
            "Create a warm, creative, and unique greeting message in Chinese. "
            "Each greeting should be different and bring joy. "
            "Keep it concise (1-2 sentences), friendly, and make Garfield smile. "
            "Use varied expressions and avoid repetition.\n\n"
            f"Create a unique greeting for Garfield today. "
            f"Make it fresh and delightful. Seed: {seed}"
        )
        
        # Gemini API格式
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.8,
                "maxOutputTokens": 50,
            }
        }
        
        data = json.dumps(payload).encode("utf-8")
        http_req = req.Request(
            f"{base_url}/{model}:generateContent?key={api_key}",
            data=data,
            method="POST"
        )
        http_req.add_header("Content-Type", "application/json")
        
        # 使用 certifi 的证书文件（解决 macOS SSL 证书问题）
        import ssl
        try:
            import certifi
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ssl_context = ssl.create_default_context()
        
        with req.urlopen(http_req, timeout=10, context=ssl_context) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        
        if isinstance(body, dict):
            candidates = body.get("candidates") or []
            if candidates and isinstance(candidates, list):
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    text = parts[0].get("text", "").strip()
                    if text:
                        return True, text
        
        return False, "❌ API返回空响应"
        
    except req.HTTPError as e:
        if e.code == 401:
            return False, "❌ API密钥无效，请检查配置"
        elif e.code == 429:
            return False, "❌ API请求频率限制，请稍后再试"
        else:
            return False, f"❌ API请求失败: HTTP {e.code}"
    except Exception as e:
        error_msg = str(e)
        # 检测SSL证书错误
        if "SSL" in error_msg or "CERTIFICATE" in error_msg or "certificate verify failed" in error_msg.lower():
            return False, f"❌ SSL证书验证失败\n\n这是macOS常见问题，修复方法：\n1. 运行修复脚本: python scripts/fix_ssl_certificates.py\n2. 或手动运行: python -m pip install --upgrade certifi\n3. 或运行: /Applications/Python\\ 3.*/Install\\ Certificates.command"
        return False, f"❌ API调用失败: {error_msg}"


def greet_garfield(provider: Optional[str] = None) -> tuple[bool, str]:
    """
    调用API向加菲众问好
    
    Args:
        provider: API提供商名称，如果为None则使用默认提供商
    
    Returns:
        (success, message): 是否成功和问候消息
    """
    try:
        config = get_api_config()
        if provider is None:
            provider = config.get_provider()
        
        api_key = config.require_api_key(provider)
        base_url = config.get_base_url(provider)
        model = config.get_model(provider)
        
        if provider == "openai":
            return greet_garfield_with_openai(api_key, base_url, model)
        elif provider == "gemini":
            return greet_garfield_with_gemini(api_key, base_url, model)
        else:
            return False, f"❌ 不支持的API提供商: {provider}"
            
    except SystemExit:
        # API配置失败，返回错误消息
        return False, "❌ API未配置，请运行配置向导：python scripts/local_picker/configure_api.py"


if __name__ == "__main__":
    success, message = greet_garfield()
    print(message)
    sys.exit(0 if success else 1)

