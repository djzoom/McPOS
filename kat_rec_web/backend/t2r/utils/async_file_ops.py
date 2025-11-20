"""
异步文件操作工具函数

提供统一的异步文件操作接口，替代同步操作以避免阻塞事件循环。
使用 aiofiles 库实现真正的异步文件 I/O。
"""
import aiofiles
import aiofiles.os
from pathlib import Path
from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)

# 检查 aiofiles 是否可用
try:
    import aiofiles
    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False
    logger.warning("aiofiles not available, falling back to asyncio.to_thread")


async def async_file_exists(path: Path) -> bool:
    """
    异步检查文件是否存在。
    
    Args:
        path: 文件路径
        
    Returns:
        如果文件存在返回 True，否则返回 False
    """
    if not AIOFILES_AVAILABLE:
        # 降级到 asyncio.to_thread
        import asyncio
        return await asyncio.to_thread(path.exists)
    
    try:
        return await aiofiles.os.path.exists(str(path))
    except Exception as e:
        logger.error(f"Error checking file existence for {path}: {e}")
        # 降级到同步检查
        return path.exists()


async def async_read_text(path: Path, encoding: str = "utf-8") -> str:
    """
    异步读取文本文件。
    
    Args:
        path: 文件路径
        encoding: 文件编码（默认 utf-8）
        
    Returns:
        文件内容字符串
        
    Raises:
        FileNotFoundError: 如果文件不存在
        IOError: 如果读取失败
    """
    if not AIOFILES_AVAILABLE:
        # 降级到 asyncio.to_thread
        import asyncio
        def _read_sync():
            return path.read_text(encoding=encoding)
        return await asyncio.to_thread(_read_sync)
    
    try:
        async with aiofiles.open(path, "r", encoding=encoding) as f:
            return await f.read()
    except FileNotFoundError:
        logger.error(f"File not found: {path}")
        raise
    except Exception as e:
        logger.error(f"Error reading file {path}: {e}")
        raise


async def async_write_text(
    path: Path, 
    content: str, 
    encoding: str = "utf-8",
    create_parents: bool = True
) -> None:
    """
    异步写入文本文件。
    
    Args:
        path: 文件路径
        content: 要写入的内容
        encoding: 文件编码（默认 utf-8）
        create_parents: 是否自动创建父目录（默认 True）
        
    Raises:
        IOError: 如果写入失败
    """
    if not AIOFILES_AVAILABLE:
        # 降级到 asyncio.to_thread
        import asyncio
        def _write_sync():
            if create_parents:
                path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding=encoding)
        await asyncio.to_thread(_write_sync)
        return
    
    try:
        if create_parents:
            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(path, "w", encoding=encoding) as f:
            await f.write(content)
    except Exception as e:
        logger.error(f"Error writing file {path}: {e}")
        raise


async def async_read_json(path: Path, encoding: str = "utf-8") -> Dict[str, Any]:
    """
    异步读取 JSON 文件。
    
    Args:
        path: JSON 文件路径
        encoding: 文件编码（默认 utf-8）
        
    Returns:
        解析后的 JSON 数据字典
        
    Raises:
        FileNotFoundError: 如果文件不存在
        json.JSONDecodeError: 如果 JSON 格式无效
    """
    try:
        content = await async_read_text(path, encoding=encoding)
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file {path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error reading JSON file {path}: {e}")
        raise


async def async_write_json(
    path: Path,
    data: Dict[str, Any],
    indent: int = 2,
    encoding: str = "utf-8",
    create_parents: bool = True
) -> None:
    """
    异步写入 JSON 文件。
    
    Args:
        path: JSON 文件路径
        data: 要写入的数据字典
        indent: JSON 缩进（默认 2）
        encoding: 文件编码（默认 utf-8）
        create_parents: 是否自动创建父目录（默认 True）
        
    Raises:
        IOError: 如果写入失败
        TypeError: 如果数据无法序列化为 JSON
    """
    try:
        content = json.dumps(data, ensure_ascii=False, indent=indent)
        await async_write_text(path, content, encoding=encoding, create_parents=create_parents)
    except TypeError as e:
        logger.error(f"Data cannot be serialized to JSON: {e}")
        raise
    except Exception as e:
        logger.error(f"Error writing JSON file {path}: {e}")
        raise


async def async_read_csv_lines(path: Path, encoding: str = "utf-8") -> list[str]:
    """
    异步读取 CSV 文件的所有行。
    
    Args:
        path: CSV 文件路径
        encoding: 文件编码（默认 utf-8）
        
    Returns:
        文件行的列表
        
    Raises:
        FileNotFoundError: 如果文件不存在
    """
    content = await async_read_text(path, encoding=encoding)
    return content.splitlines()


async def async_mkdir(path: Path, parents: bool = True, exist_ok: bool = True) -> None:
    """
    异步创建目录。
    
    Args:
        path: 目录路径
        parents: 是否创建父目录（默认 True）
        exist_ok: 如果目录已存在是否忽略错误（默认 True）
    """
    if not AIOFILES_AVAILABLE:
        # 降级到 asyncio.to_thread
        import asyncio
        def _mkdir_sync():
            path.mkdir(parents=parents, exist_ok=exist_ok)
        await asyncio.to_thread(_mkdir_sync)
        return
    
    try:
        # aiofiles.os 没有直接的 mkdir，使用 asyncio.to_thread
        import asyncio
        def _mkdir_sync():
            path.mkdir(parents=parents, exist_ok=exist_ok)
        await asyncio.to_thread(_mkdir_sync)
    except Exception as e:
        logger.error(f"Error creating directory {path}: {e}")
        raise


async def async_write_csv(
    path: Path,
    rows: list[list],
    headers: Optional[list] = None,
    encoding: str = "utf-8",
    create_parents: bool = True,
) -> None:
    """
    异步写入 CSV 文件。
    
    Args:
        path: CSV 文件路径
        rows: 数据行列表（每行是一个列表）
        headers: 可选的表头列表
        encoding: 文件编码（默认 utf-8）
        create_parents: 是否自动创建父目录（默认 True）
        
    Raises:
        IOError: 如果写入失败
    """
    import csv
    import asyncio
    
    def _write_csv_sync():
        if create_parents:
            path.parent.mkdir(parents=True, exist_ok=True)
        
        with path.open("w", newline="", encoding=encoding) as f:
            writer = csv.writer(f)
            if headers:
                writer.writerow(headers)
            writer.writerows(rows)
    
    # 使用 asyncio.to_thread 包装同步 CSV 写入操作
    await asyncio.to_thread(_write_csv_sync)

