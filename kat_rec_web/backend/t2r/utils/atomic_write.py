"""
Atomic File Writing Utilities

Provides atomic write operations using temporary files + rename.
"""
from pathlib import Path
import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def atomic_write_json(file_path: Path, data: Any, **kwargs) -> bool:
    """
    Atomically write JSON data to file.
    
    Uses temporary file + rename to ensure atomicity.
    
    Args:
        file_path: Target file path
        data: Data to serialize to JSON
        **kwargs: Additional arguments for json.dump
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create temporary file in same directory
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        
        # Write to temp file
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, **kwargs)
        
        # Atomic rename (POSIX-compliant)
        temp_path.replace(file_path)
        
        logger.debug(f"Atomically wrote JSON to {file_path}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to atomically write {file_path}: {e}")
        # Clean up temp file if exists
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        return False


def atomic_write_text(file_path: Path, content: str) -> bool:
    """
    Atomically write text content to file.
    
    Args:
        file_path: Target file path
        content: Text content to write
    
    Returns:
        True if successful, False otherwise
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        
        with temp_path.open("w", encoding="utf-8") as f:
            f.write(content)
        
        temp_path.replace(file_path)
        logger.debug(f"Atomically wrote text to {file_path}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to atomically write {file_path}: {e}")
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        return False

