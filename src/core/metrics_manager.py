#!/usr/bin/env python3
# coding: utf-8
"""
指标收集管理器

功能：
1. 跟踪每个阶段的耗时（remix, render, upload）
2. 统计成功/失败率
3. 计算平均耗时、吞吐量、每日总数
4. 持久化指标到 data/metrics.json（追加模式，每日轮转）
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加项目路径
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root / "src") not in sys.path:
    sys.path.insert(0, str(_repo_root / "src"))


class MetricsManager:
    """
    指标收集管理器
    
    功能：
    - 记录阶段事件（开始/完成/失败）
    - 计算阶段耗时
    - 统计成功率和失败率
    - 提供聚合查询接口
    """
    
    def __init__(self, metrics_file: Optional[Path] = None):
        """
        初始化指标管理器
        
        Args:
            metrics_file: 指标文件路径（默认：data/metrics.json）
        """
        if metrics_file is None:
            metrics_file = _repo_root / "data" / "metrics.json"
        
        self.metrics_file = metrics_file
        self.metrics_dir = metrics_file.parent
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存中的阶段开始时间记录（用于计算耗时）
        self._stage_starts: Dict[str, Dict[str, float]] = defaultdict(dict)  # {episode_id: {stage: timestamp}}
        
        # 当日指标缓存
        self._daily_cache: Optional[Dict] = None
        self._cache_date: Optional[str] = None
    
    def _get_today_str(self) -> str:
        """获取今天的日期字符串（YYYY-MM-DD）"""
        return datetime.now().strftime("%Y-%m-%d")
    
    def _load_metrics(self) -> Dict:
        """加载指标文件"""
        if not self.metrics_file.exists():
            return {
                "events": [],
                "daily_stats": {},
                "summary": {
                    "total_episodes": 0,
                    "completed": 0,
                    "failed": 0,
                    "in_progress": 0,
                }
            }
        
        try:
            with self.metrics_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # 如果文件损坏，返回空结构
            return {
                "events": [],
                "daily_stats": {},
                "summary": {}
            }
    
    def _save_metrics(self, metrics: Dict) -> bool:
        """保存指标文件（原子性写入）"""
        try:
            # 确保目录存在
            self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 原子性写入
            temp_file = self.metrics_file.with_suffix(".json.tmp")
            with temp_file.open("w", encoding="utf-8") as f:
                json.dump(metrics, f, ensure_ascii=False, indent=2)
            
            temp_file.replace(self.metrics_file)
            return True
        except Exception as e:
            print(f"❌ 保存指标文件失败: {e}")
            return False
    
    def _rotate_if_needed(self, metrics: Dict) -> Dict:
        """
        如果跨日，轮转指标（保留最近30天的数据）
        
        Args:
            metrics: 当前指标数据
        
        Returns:
            处理后的指标数据
        """
        today = self._get_today_str()
        cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        # 过滤事件（保留最近30天）
        events = metrics.get("events", [])
        filtered_events = [
            e for e in events
            if e.get("timestamp", "")[:10] >= cutoff_date
        ]
        
        # 过滤每日统计（保留最近30天）
        daily_stats = metrics.get("daily_stats", {})
        filtered_daily_stats = {
            date: stats
            for date, stats in daily_stats.items()
            if date >= cutoff_date
        }
        
        return {
            "events": filtered_events,
            "daily_stats": filtered_daily_stats,
            "summary": metrics.get("summary", {})
        }
    
    def record_stage_start(self, episode_id: str, stage: str) -> None:
        """
        记录阶段开始
        
        Args:
            episode_id: 期数ID
            stage: 阶段名称（remix, render, upload等）
        """
        self._stage_starts[episode_id][stage] = datetime.now().timestamp()
    
    def record_event(
        self,
        stage: str,
        status: str,
        duration: Optional[float] = None,
        episode_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        记录阶段事件
        
        Args:
            stage: 阶段名称（remix, render, upload等）
            status: 状态（started, completed, failed）
            duration: 耗时（秒），如果为None且status为completed/failed，自动计算
            episode_id: 期数ID（可选）
            error_message: 错误消息（仅status=failed时）
        """
        now = datetime.now()
        timestamp = now.isoformat()
        
        # 如果duration为None且状态为completed/failed，尝试从内存中计算
        if duration is None and status in ("completed", "failed") and episode_id:
            if episode_id in self._stage_starts and stage in self._stage_starts[episode_id]:
                start_time = self._stage_starts[episode_id][stage]
                duration = now.timestamp() - start_time
                # 清除开始时间记录
                del self._stage_starts[episode_id][stage]
                if not self._stage_starts[episode_id]:
                    del self._stage_starts[episode_id]
        
        # 创建事件记录
        event = {
            "timestamp": timestamp,
            "stage": stage,
            "status": status,
            "episode_id": episode_id,
        }
        
        if duration is not None:
            event["duration"] = round(duration, 2)
        
        if error_message:
            event["error_message"] = error_message
        
        # 加载现有指标
        metrics = self._load_metrics()
        
        # 追加事件（最多保留10000条）
        events = metrics.get("events", [])
        events.append(event)
        if len(events) > 10000:
            events = events[-10000:]  # 保留最近10000条
        
        metrics["events"] = events
        
        # 更新当日统计
        today = self._get_today_str()
        if "daily_stats" not in metrics:
            metrics["daily_stats"] = {}
        
        if today not in metrics["daily_stats"]:
            metrics["daily_stats"][today] = {
                "total_events": 0,
                "completed": 0,
                "failed": 0,
                "total_duration": 0.0,
                "stages": defaultdict(lambda: {"count": 0, "total_duration": 0.0, "failed": 0})
            }
        
        daily = metrics["daily_stats"][today]
        daily["total_events"] += 1
        
        if status == "completed":
            daily["completed"] += 1
        elif status == "failed":
            daily["failed"] += 1
        
        if duration is not None:
            daily["total_duration"] += duration
            if stage not in daily["stages"]:
                daily["stages"][stage] = {"count": 0, "total_duration": 0.0, "failed": 0}
            stage_stats = daily["stages"][stage]
            stage_stats["count"] += 1
            stage_stats["total_duration"] += duration
            if status == "failed":
                stage_stats["failed"] += 1
        
        # 更新汇总统计
        if "summary" not in metrics:
            metrics["summary"] = {
                "total_episodes": 0,
                "completed": 0,
                "failed": 0,
                "in_progress": 0,
            }
        
        # 轮转（如果需要）
        metrics = self._rotate_if_needed(metrics)
        
        # 保存
        self._save_metrics(metrics)
    
    def get_summary(self, period: str = "24h") -> Dict:
        """
        获取聚合指标摘要
        
        Args:
            period: 时间 period ("24h", "7d", "30d", "all")
        
        Returns:
            聚合指标字典
        """
        metrics = self._load_metrics()
        now = datetime.now()
        
        # 计算时间范围
        if period == "24h":
            cutoff = now - timedelta(hours=24)
        elif period == "7d":
            cutoff = now - timedelta(days=7)
        elif period == "30d":
            cutoff = now - timedelta(days=30)
        else:  # "all"
            cutoff = datetime.min
        
        cutoff_iso = cutoff.isoformat()
        
        # 过滤事件
        events = [
            e for e in metrics.get("events", [])
            if e.get("timestamp", "") >= cutoff_iso
        ]
        
        # 统计
        total_events = len(events)
        completed = sum(1 for e in events if e.get("status") == "completed")
        failed = sum(1 for e in events if e.get("status") == "failed")
        in_progress = sum(1 for e in events if e.get("status") == "started")
        
        # 计算平均耗时
        durations = [e.get("duration", 0) for e in events if e.get("duration") is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        
        # 按阶段统计
        stage_stats = defaultdict(lambda: {"count": 0, "completed": 0, "failed": 0, "total_duration": 0.0})
        
        for event in events:
            stage = event.get("stage", "unknown")
            status = event.get("status")
            duration = event.get("duration", 0)
            
            stage_stats[stage]["count"] += 1
            if status == "completed":
                stage_stats[stage]["completed"] += 1
            elif status == "failed":
                stage_stats[stage]["failed"] += 1
            
            if duration:
                stage_stats[stage]["total_duration"] += duration
        
        # 计算阶段平均耗时
        for stage, stats in stage_stats.items():
            if stats["completed"] > 0:
                stats["avg_duration"] = round(
                    stats["total_duration"] / stats["completed"],
                    2
                )
            else:
                stats["avg_duration"] = 0.0
        
        return {
            "period": period,
            "total_events": total_events,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "success_rate": round(completed / total_events * 100, 2) if total_events > 0 else 0.0,
            "failure_rate": round(failed / total_events * 100, 2) if total_events > 0 else 0.0,
            "avg_duration": round(avg_duration, 2),
            "stages": dict(stage_stats),
            "timestamp": now.isoformat()
        }
    
    def get_episode_metrics(self, episode_id: str) -> Dict:
        """
        获取特定期数的指标
        
        Args:
            episode_id: 期数ID
        
        Returns:
            期数指标字典
        """
        metrics = self._load_metrics()
        
        # 过滤该期数的事件
        events = [
            e for e in metrics.get("events", [])
            if e.get("episode_id") == episode_id
        ]
        
        # 按阶段分组
        stage_events = defaultdict(list)
        for event in events:
            stage = event.get("stage", "unknown")
            stage_events[stage].append(event)
        
        # 计算每个阶段的统计
        stage_stats = {}
        for stage, stage_evts in stage_events.items():
            completed_evts = [e for e in stage_evts if e.get("status") == "completed"]
            failed_evts = [e for e in stage_evts if e.get("status") == "failed"]
            
            durations = [e.get("duration", 0) for e in completed_evts if e.get("duration") is not None]
            
            stage_stats[stage] = {
                "total_runs": len(stage_evts),
                "completed": len(completed_evts),
                "failed": len(failed_evts),
                "avg_duration": round(sum(durations) / len(durations), 2) if durations else None,
            }
        
        return {
            "episode_id": episode_id,
            "stages": stage_stats,
            "total_events": len(events),
            "latest_event": events[-1] if events else None
        }
    
    def get_recent_events(self, limit: int = 50) -> List[Dict]:
        """
        获取最近的事件
        
        Args:
            limit: 返回数量限制
        
        Returns:
            事件列表（按时间倒序）
        """
        metrics = self._load_metrics()
        events = metrics.get("events", [])
        return events[-limit:][::-1]  # 最近N条，倒序


# 全局指标管理器单例
_metrics_manager: Optional[MetricsManager] = None


def get_metrics_manager() -> MetricsManager:
    """获取全局指标管理器实例"""
    global _metrics_manager
    if _metrics_manager is None:
        _metrics_manager = MetricsManager()
    return _metrics_manager

