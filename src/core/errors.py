#!/usr/bin/env python3
# coding: utf-8
"""
统一错误处理系统

定义错误类型和错误处理装饰器
"""
from __future__ import annotations

import functools
import traceback
from typing import Any, Callable, TypeVar

try:
    from .logger import get_logger
except ImportError:
    get_logger = None

F = TypeVar("F", bound=Callable[..., Any])


class KatRecError(Exception):
    """基础错误类"""

    pass


class TransientError(KatRecError):
    """临时错误（可重试）"""

    pass


class UploadError(KatRecError):
    """上传相关错误"""

    pass


class ConfigError(KatRecError):
    """配置相关错误"""

    pass


def handle_errors(context: str) -> Callable[[F], F]:
    """
    错误处理装饰器
    
    自动记录错误日志并重新抛出异常
    
    Args:
        context: 上下文描述（用于日志记录）
    
    Example:
        @handle_errors("upload_video")
        def upload_video():
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except (TransientError, UploadError, ConfigError) as e:
                # 已知错误类型，记录并重新抛出
                if get_logger:
                    logger = get_logger()
                    logger.error(
                        f"{context}.error",
                        f"{context} failed: {str(e)}",
                        traceback=traceback.format_exc(),
                    )
                raise
            except Exception as e:
                # 未知错误，包装为KatRecError并记录
                if get_logger:
                    logger = get_logger()
                    logger.error(
                        f"{context}.unexpected_error",
                        f"Unexpected error in {context}: {str(e)}",
                        traceback=traceback.format_exc(),
                    )
                raise KatRecError(f"{context} failed: {str(e)}") from e

        return wrapper  # type: ignore

    return decorator

