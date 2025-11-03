#!/usr/bin/env python3
# coding: utf-8
"""
结构化日志系统

功能：
1. 统一的日志格式（时间戳、期数ID、事件名、消息、可选堆栈）
2. 自动日志轮转（最大5MB，保留最近5个文件）
3. 与事件总线集成，自动记录所有事件
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# 配置日志目录
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = REPO_ROOT / "logs"
LOG_FILE = LOG_DIR / "system_events.log"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 5  # 保留最近5个日志文件


# 使用标准库的RotatingFileHandler，不需要自定义类


class StructuredLogger:
    """
    结构化日志记录器
    
    每个日志条目包含：
    - timestamp: ISO格式时间戳
    - episode_id: 期数ID（如果适用）
    - event_name: 事件名称
    - message: 日志消息
    - level: 日志级别
    - traceback: 错误堆栈（仅错误时）
    - metadata: 额外元数据（可选）
    """
    
    def __init__(self, log_file: Path = LOG_FILE):
        self.log_file = log_file
        self.log_dir = log_file.parent
        
        # 确保日志目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置标准logging
        self.logger = logging.getLogger("kat_records.system")
        self.logger.setLevel(logging.DEBUG)
        
        # 避免重复添加handler
        if not self.logger.handlers:
            # 文件处理器（带轮转）
            file_handler = logging.handlers.RotatingFileHandler(
                str(self.log_file),
                maxBytes=MAX_LOG_SIZE,
                backupCount=BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            
            # 格式化器（JSON格式，便于解析）
            formatter = StructuredFormatter()
            file_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            
            # 控制台处理器（简化格式）
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
    
    def log_event(
        self,
        event_name: str,
        message: str,
        episode_id: Optional[str] = None,
        level: str = "INFO",
        traceback: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        记录结构化事件
        
        Args:
            event_name: 事件名称（如 "remix.started", "video.render.completed"）
            message: 日志消息
            episode_id: 期数ID（如果适用）
            level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
            traceback: 错误堆栈（仅错误时）
            metadata: 额外元数据
        """
        log_level = getattr(logging, level.upper(), logging.INFO)
        
        # 构建日志记录字典
        log_record = {
            "timestamp": datetime.now().isoformat(),
            "event_name": event_name,
            "message": message,
            "level": level,
        }
        
        if episode_id:
            log_record["episode_id"] = episode_id
        
        if traceback:
            log_record["traceback"] = traceback
        
        if metadata:
            log_record["metadata"] = metadata
        
        # 记录日志（使用extra传递结构化数据）
        self.logger.log(log_level, message, extra={"structured": log_record})
    
    def debug(self, event_name: str, message: str, episode_id: Optional[str] = None, metadata: Optional[Dict] = None) -> None:
        """记录DEBUG级别事件"""
        self.log_event(event_name, message, episode_id, "DEBUG", metadata=metadata)
    
    def info(self, event_name: str, message: str, episode_id: Optional[str] = None, metadata: Optional[Dict] = None) -> None:
        """记录INFO级别事件"""
        self.log_event(event_name, message, episode_id, "INFO", metadata=metadata)
    
    def warning(self, event_name: str, message: str, episode_id: Optional[str] = None, metadata: Optional[Dict] = None) -> None:
        """记录WARNING级别事件"""
        self.log_event(event_name, message, episode_id, "WARNING", metadata=metadata)
    
    def error(
        self,
        event_name: str,
        message: str,
        episode_id: Optional[str] = None,
        traceback: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """记录ERROR级别事件"""
        self.log_event(event_name, message, episode_id, "ERROR", traceback=traceback, metadata=metadata)
    
    def critical(
        self,
        event_name: str,
        message: str,
        episode_id: Optional[str] = None,
        traceback: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """记录CRITICAL级别事件"""
        self.log_event(event_name, message, episode_id, "CRITICAL", traceback=traceback, metadata=metadata)


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器（输出JSON格式）"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON"""
        # 如果有structured数据，使用它
        if hasattr(record, 'structured'):
            return json.dumps(record.structured, ensure_ascii=False)
        
        # 否则构建标准格式
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加异常信息（如果有）
        if record.exc_info:
            import traceback
            log_data["traceback"] = traceback.format_exception(*record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


# 全局日志记录器单例
_logger: Optional[StructuredLogger] = None


def get_logger() -> StructuredLogger:
    """获取全局日志记录器实例"""
    global _logger
    if _logger is None:
        _logger = StructuredLogger()
    return _logger

