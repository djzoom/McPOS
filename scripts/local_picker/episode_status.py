#!/usr/bin/env python3
# coding: utf-8
"""
期数状态管理

定义和转换期数的各种状态
"""
from __future__ import annotations

# 状态定义（中文）
STATUS_待制作 = "待制作"  # 尚未开始制作
STATUS_制作中 = "制作中"  # 正在制作封面和音频
STATUS_上传中 = "上传中"  # 视频已生成，正在上传到YouTube
STATUS_排播完毕待播出 = "排播完毕待播出"  # 已上传，等待播出
STATUS_已完成 = "已完成"  # 已完成并播出
STATUS_已跳过 = "已跳过"  # 跳过该期

# 所有有效状态
ALL_STATUSES = [
    STATUS_待制作,
    STATUS_制作中,
    STATUS_上传中,
    STATUS_排播完毕待播出,
    STATUS_已完成,
    STATUS_已跳过,
]

# 向后兼容：旧状态到新状态的映射
LEGACY_STATUS_MAP = {
    "pending": STATUS_待制作,
    "completed": STATUS_已完成,
    "skipped": STATUS_已跳过,
}

# 新状态到旧状态的映射（用于兼容）
STATUS_TO_LEGACY = {
    STATUS_待制作: "pending",
    STATUS_制作中: "pending",
    STATUS_上传中: "pending",
    STATUS_排播完毕待播出: "pending",
    STATUS_已完成: "completed",
    STATUS_已跳过: "skipped",
}


def normalize_status(status: str) -> str:
    """
    规范化状态值
    
    将旧状态转换为新状态，确保状态一致性
    
    Args:
        status: 状态字符串（可能是旧状态或新状态）
    
    Returns:
        规范化的状态字符串
    """
    if not status:
        return STATUS_待制作
    
    status = status.strip()
    
    # 如果是旧状态，转换为新状态
    if status in LEGACY_STATUS_MAP:
        return LEGACY_STATUS_MAP[status]
    
    # 如果是新状态，直接返回
    if status in ALL_STATUSES:
        return status
    
    # 未知状态，默认为待制作
    return STATUS_待制作


def is_pending_status(status: str) -> bool:
    """
    判断是否是"待处理"状态（包括各种pending状态的变体）
    
    Args:
        status: 状态字符串
    
    Returns:
        是否是待处理状态
    """
    normalized = normalize_status(status)
    return normalized in [
        STATUS_待制作,
        STATUS_制作中,
        STATUS_上传中,
        STATUS_排播完毕待播出,
    ]


def is_completed_status(status: str) -> bool:
    """判断是否已完成"""
    return normalize_status(status) == STATUS_已完成


def is_skipped_status(status: str) -> bool:
    """判断是否已跳过"""
    return normalize_status(status) == STATUS_已跳过


def get_status_display(status: str) -> str:
    """
    获取状态的显示文本
    
    Args:
        status: 状态字符串
    
    Returns:
        显示文本
    """
    normalized = normalize_status(status)
    return normalized

