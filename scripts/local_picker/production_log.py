#!/usr/bin/env python3
# coding: utf-8
"""
生产日志管理系统

功能：
1. 追踪生产排播计划（每2日一期）
2. 记录歌库更新时间和规模
3. 生成基于排播日期的ID
4. 确保正式产出物的格式一致性
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# 生产日志文件路径
PRODUCTION_LOG_PATH = Path("config/production_log.json")

# 默认起始排播日期（系统当前日期）
def get_default_start_date() -> datetime:
    """获取默认起始日期：系统当前日期"""
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

DEFAULT_START_DATE = get_default_start_date()

# 排播间隔（天）
SCHEDULE_INTERVAL_DAYS = 2  # 每2日一期


@dataclass
class LibrarySnapshot:
    """歌库快照"""
    total_tracks: int
    updated_at: str  # ISO格式时间戳
    library_file: str  # 歌库文件路径


@dataclass
class ProductionRecord:
    """生产记录"""
    episode_id: str  # 排播日期格式：YYYYMMDD
    schedule_date: str  # 排播日期 ISO格式：YYYY-MM-DD
    episode_number: int  # 期数（从1开始）
    library_snapshot: LibrarySnapshot
    created_at: str  # 创建时间 ISO格式
    status: str  # pending / completed / failed
    output_dir: Optional[str] = None  # 输出目录路径
    title: Optional[str] = None  # 专辑标题
    track_count: Optional[int] = None  # 使用的曲目数


@dataclass
class ProductionLog:
    """生产日志"""
    start_date: str  # 起始排播日期
    schedule_interval_days: int  # 排播间隔
    records: List[Dict]  # 生产记录列表
    last_library_update: Optional[str] = None  # 最后歌库更新时间
    
    @classmethod
    def load(cls, path: Path = PRODUCTION_LOG_PATH) -> "ProductionLog":
        """从文件加载生产日志"""
        if not path.exists():
            return cls(
                start_date=DEFAULT_START_DATE.isoformat()[:10],  # YYYY-MM-DD
                schedule_interval_days=SCHEDULE_INTERVAL_DAYS,
                records=[],
            )
        
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)
        except Exception:
            # 如果文件损坏，创建新的
            return cls(
                start_date=DEFAULT_START_DATE.isoformat()[:10],
                schedule_interval_days=SCHEDULE_INTERVAL_DAYS,
                records=[],
            )
    
    def save(self, path: Path = PRODUCTION_LOG_PATH) -> None:
        """保存生产日志到文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
    
    def get_next_schedule_date(self) -> datetime:
        """获取下一个排播日期"""
        start = datetime.fromisoformat(self.start_date)
        
        if not self.records:
            return start
        
        # 找到最后一个已排播的记录
        last_date = start
        for record in self.records:
            if record.get("status") == "completed":
                last_date = datetime.fromisoformat(record["schedule_date"])
        
        # 下一个排播日期 = 最后完成日期 + 间隔
        next_date = last_date + timedelta(days=self.schedule_interval_days)
        return next_date
    
    def get_episode_number(self, schedule_date: datetime) -> int:
        """根据排播日期计算期数"""
        start = datetime.fromisoformat(self.start_date)
        days_diff = (schedule_date - start).days
        episode = (days_diff // self.schedule_interval_days) + 1
        return max(1, episode)
    
    def create_record(
        self,
        schedule_date: datetime,
        library_snapshot: LibrarySnapshot,
        status: str = "pending"
    ) -> ProductionRecord:
        """创建新的生产记录"""
        episode_number = self.get_episode_number(schedule_date)
        episode_id = schedule_date.strftime("%Y%m%d")
        
        record = ProductionRecord(
            episode_id=episode_id,
            schedule_date=schedule_date.isoformat()[:10],  # YYYY-MM-DD
            episode_number=episode_number,
            library_snapshot=library_snapshot,
            created_at=datetime.now().isoformat(),
            status=status,
        )
        
        # 添加到记录列表
        self.records.append(asdict(record))
        return record
    
    def find_record(self, episode_id: str) -> Optional[Dict]:
        """查找指定ID的记录"""
        for record in self.records:
            if record.get("episode_id") == episode_id:
                return record
        return None
    
    def update_record(
        self,
        episode_id: str,
        status: Optional[str] = None,
        output_dir: Optional[str] = None,
        title: Optional[str] = None,
        track_count: Optional[int] = None
    ) -> bool:
        """更新生产记录"""
        for record in self.records:
            if record.get("episode_id") == episode_id:
                if status:
                    record["status"] = status
                if output_dir:
                    record["output_dir"] = output_dir
                if title:
                    record["title"] = title
                if track_count:
                    record["track_count"] = track_count
                return True
        return False


def get_library_snapshot(tracklist_path: Path, track_count: Optional[int] = None) -> LibrarySnapshot:
    """获取当前歌库快照"""
    if track_count is None:
        # 如果未提供track_count，尝试读取（避免循环导入）
        try:
            import csv
            with tracklist_path.open("r", encoding="utf-8") as fh:
                reader = csv.reader(fh)
                next(reader, None)  # 跳过表头
                track_count = sum(1 for _ in reader)
        except Exception:
            track_count = 0
    
    # 获取文件修改时间作为更新时间
    mtime = tracklist_path.stat().st_mtime
    updated_at = datetime.fromtimestamp(mtime).isoformat()
    
    return LibrarySnapshot(
        total_tracks=track_count,
        updated_at=updated_at,
        library_file=str(tracklist_path),
    )


def get_production_id(
    log: Optional[ProductionLog] = None,
    schedule_date: Optional[datetime] = None,
    tracklist_path: Optional[Path] = None
) -> tuple[str, datetime, ProductionLog]:
    """
    获取生产ID（基于排播日期）
    
     Returns:
        (episode_id, schedule_date, production_log)
    """
    if log is None:
        log = ProductionLog.load()
    
    if schedule_date is None:
        schedule_date = log.get_next_schedule_date()
    
    episode_id = schedule_date.strftime("%Y%m%d")
    
    # 如果这个ID已经存在，检查是否需要处理冲突
    existing = log.find_record(episode_id)
    if existing:
        # 如果已有记录且已完成，需要生成下一个排播日期
        if existing.get("status") == "completed":
            schedule_date = log.get_next_schedule_date()
            episode_id = schedule_date.strftime("%Y%m%d")
    
    return episode_id, schedule_date, log


def sync_from_schedule_master(schedule_start_date: str, schedule_interval_days: int) -> bool:
    """
    从排播表同步信息到生产日志
    
    Args:
        schedule_start_date: 排播表的起始日期（YYYY-MM-DD格式）
        schedule_interval_days: 排播间隔（天）
    
    Returns:
        是否成功同步
    """
    try:
        production_log = ProductionLog.load()
        
        # 检查是否需要更新
        if (production_log.start_date != schedule_start_date or 
            production_log.schedule_interval_days != schedule_interval_days):
            
            old_start = production_log.start_date
            old_interval = production_log.schedule_interval_days
            
            production_log.start_date = schedule_start_date
            production_log.schedule_interval_days = schedule_interval_days
            production_log.save()
            
            print(f"✅ 生产日志已同步排播表信息：")
            if old_start != schedule_start_date:
                print(f"   起始日期：{old_start} -> {schedule_start_date}")
            if old_interval != schedule_interval_days:
                print(f"   排播间隔：{old_interval} 天 -> {schedule_interval_days} 天")
            return True
        else:
            # 无需更新
            return True
    except Exception as e:
        print(f"⚠️  同步生产日志失败: {e}")
        import traceback
        traceback.print_exc()
        return False

