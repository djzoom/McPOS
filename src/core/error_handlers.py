#!/usr/bin/env python3
# coding: utf-8
"""
统一错误处理工具

提供可重用的错误处理函数，消除重复代码
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from .errors import ConfigError, KatRecError, TransientError, UploadError

F = TypeVar("F", bound=Callable[..., Any])


@contextmanager
def handle_file_io(path: Path, operation: str = "operation"):
    """
    文件IO操作的统一错误处理上下文管理器
    
    Args:
        path: 文件路径
        operation: 操作描述（用于错误消息）
    
    Example:
        with handle_file_io(file_path, "reading config"):
            content = file_path.read_text()
    """
    try:
        yield path
    except FileNotFoundError:
        raise ConfigError(f"{operation} failed: File not found: {path}") from None
    except PermissionError as e:
        raise ConfigError(f"{operation} failed: Permission denied: {path}") from e
    except OSError as e:
        raise ConfigError(f"{operation} failed: OS error: {e}") from e
    except UnicodeDecodeError as e:
        raise ConfigError(
            f"{operation} failed: Cannot decode file (not UTF-8?): {path}"
        ) from e


def safe_file_read(path: Path, encoding: str = "utf-8") -> str:
    """
    安全地读取文件，提供统一的错误处理
    
    Args:
        path: 文件路径
        encoding: 文件编码（默认：utf-8）
    
    Returns:
        文件内容
    
    Raises:
        ConfigError: 如果读取失败
    """
    with handle_file_io(path, f"Reading {path.name}"):
        return path.read_text(encoding=encoding)


def safe_file_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """
    安全地写入文件，提供统一的错误处理
    
    Args:
        path: 文件路径
        content: 要写入的内容
        encoding: 文件编码（默认：utf-8）
    
    Raises:
        ConfigError: 如果写入失败
    """
    with handle_file_io(path, f"Writing {path.name}"):
        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)


def handle_subprocess_error(
    cmd: list[str],
    result: Any,
    context: str = "subprocess",
) -> None:
    """
    统一处理子进程错误
    
    Args:
        cmd: 执行的命令
        result: subprocess.run 的结果对象
        context: 上下文描述
    
    Raises:
        KatRecError: 如果命令执行失败
    """
    if result.returncode != 0:
        error_msg = f"{context} failed (exit code {result.returncode})"
        if result.stderr:
            error_msg += f": {result.stderr[:500]}"
        raise KatRecError(error_msg)


def classify_error(error: Exception) -> type[KatRecError]:
    """
    根据异常类型分类为标准错误类型
    
    Args:
        error: 原始异常
    
    Returns:
        分类后的错误类型
    """
    # 文件系统错误 -> ConfigError
    if isinstance(error, (FileNotFoundError, PermissionError, OSError, IOError)):
        return ConfigError
    
    # 网络/API 错误 -> TransientError (可能可重试)
    if "network" in str(error).lower() or "timeout" in str(error).lower():
        return TransientError
    
    # 上传相关错误 -> UploadError
    if "upload" in str(error).lower() or "youtube" in str(error).lower():
        return UploadError
    
    # 默认 -> KatRecError
    return KatRecError


def format_user_error(error: Exception, context: Optional[str] = None) -> str:
    """
    格式化用户友好的错误消息
    
    Args:
        error: 异常对象
        context: 可选的上下文信息
    
    Returns:
        格式化的错误消息
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    # 提供友好的错误消息
    friendly_messages = {
        "FileNotFoundError": "文件未找到",
        "PermissionError": "权限不足",
        "ConfigError": "配置错误",
        "UploadError": "上传失败",
        "TransientError": "临时错误（可重试）",
    }
    
    friendly_type = friendly_messages.get(error_type, error_type)
    
    if context:
        return f"[{context}] {friendly_type}: {error_msg}"
    return f"{friendly_type}: {error_msg}"

