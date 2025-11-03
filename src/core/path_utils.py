#!/usr/bin/env python3
# coding: utf-8
"""
路径工具模块

提供安全的路径构造和验证功能
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .errors import ConfigError


def safe_join_path(base: Path, *parts: str) -> Path:
    """
    安全地连接路径组件，防止路径遍历攻击
    
    Args:
        base: 基础路径（受信任的目录）
        *parts: 路径组件（可能不受信任）
    
    Returns:
        规范化后的安全路径
    
    Raises:
        ConfigError: 如果路径试图转义基础目录
    
    Example:
        >>> base = Path("/safe/dir")
        >>> safe_join_path(base, "file.txt")  # OK
        Path("/safe/dir/file.txt")
        >>> safe_join_path(base, "..", "etc", "passwd")  # Raises ConfigError
    """
    if not base.is_absolute():
        raise ConfigError(f"Base path must be absolute: {base}")
    
    # 规范化基础路径
    base = base.resolve()
    
    # 构建目标路径
    target = base
    for part in parts:
        if not part or part == ".":
            continue
        
        # 检查危险的路径组件
        if part == ".." or part.startswith("../"):
            raise ConfigError(f"Path traversal detected: {part}")
        
        if part.startswith("/"):
            raise ConfigError(f"Absolute path component not allowed: {part}")
        
        # 检查 Windows 路径分隔符（即使是跨平台）
        if "\\" in part or "/" in part:
            # 只允许最后一个组件包含分隔符（如果是文件名的一部分）
            normalized = part.replace("\\", "/")
            if normalized.count("/") > 0 and not normalized.endswith("/"):
                parts_list = normalized.split("/")
                if any(p == ".." for p in parts_list):
                    raise ConfigError(f"Path traversal detected in: {part}")
        
        target = target / part
    
    # 规范化并验证结果在基础目录内
    resolved_target = target.resolve()
    
    try:
        resolved_target.relative_to(base)
    except ValueError:
        raise ConfigError(
            f"Path escapes base directory: {resolved_target} not under {base}"
        )
    
    return resolved_target


def validate_path_exists(path: Path, must_exist: bool = False) -> Path:
    """
    验证路径是否存在，并可选择要求存在
    
    Args:
        path: 要验证的路径
        must_exist: 如果为 True，路径必须存在
    
    Returns:
        规范化后的路径
    
    Raises:
        ConfigError: 如果路径不符合要求
    """
    resolved = path.resolve()
    
    if must_exist and not resolved.exists():
        raise ConfigError(f"Required path does not exist: {path}")
    
    return resolved


def sanitize_path_component(component: str) -> str:
    """
    清理路径组件，移除危险字符
    
    Args:
        component: 路径组件（如文件名）
    
    Returns:
        清理后的组件
    """
    # 移除危险字符
    dangerous_chars = ["/", "\\", "..", "\x00"]
    sanitized = component
    
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "_")
    
    # 限制长度（避免过长的文件名）
    if len(sanitized) > 255:
        sanitized = sanitized[:255]
    
    return sanitized


def ensure_directory(path: Path, create: bool = True) -> Path:
    """
    确保目录存在
    
    Args:
        path: 目录路径
        create: 如果目录不存在，是否创建
    
    Returns:
        规范化后的目录路径
    
    Raises:
        ConfigError: 如果路径不是目录或创建失败
    """
    resolved = path.resolve()
    
    if resolved.exists():
        if not resolved.is_dir():
            raise ConfigError(f"Path exists but is not a directory: {path}")
        return resolved
    
    if create:
        try:
            resolved.mkdir(parents=True, exist_ok=True)
            return resolved
        except (OSError, PermissionError) as e:
            raise ConfigError(f"Failed to create directory {path}: {e}") from e
    
    raise ConfigError(f"Directory does not exist: {path}")

