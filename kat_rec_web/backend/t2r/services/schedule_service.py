"""
Schedule Service for T2R

Manages schedule_master.json, locking, and conflict detection.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
SCHEDULE_MASTER_PATH = REPO_ROOT / "config" / "schedule_master.json"
OUTPUT_DIR = REPO_ROOT / "output"
ASSET_USAGE_INDEX_PATH = REPO_ROOT / "data" / "asset_usage_index.json"
LOCK_DATE_THRESHOLD = "2025-11-02"  # Lock episodes from this date onwards


def load_schedule_master() -> Optional[Dict]:
    """Load schedule_master.json"""
    if not SCHEDULE_MASTER_PATH.exists():
        logger.warning(f"Schedule master not found: {SCHEDULE_MASTER_PATH}")
        return None
    
    try:
        with SCHEDULE_MASTER_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load schedule master: {e}")
        return None


def save_schedule_master(data: Dict) -> bool:
    """Save schedule_master.json atomically"""
    from ..utils.atomic_write import atomic_write_json
    return atomic_write_json(SCHEDULE_MASTER_PATH, data)


def scan_and_lock() -> Dict:
    """
    Scan schedule and output directory, lock published episodes.
    
    Returns:
        {
            "locked_count": int,
            "new_episodes": int,
            "conflicts": List[Dict],
            "asset_usage": Dict,
            "timestamp": str
        }
    """
    schedule = load_schedule_master()
    if not schedule:
        return {
            "locked_count": 0,
            "new_episodes": 0,
            "conflicts": [],
            "asset_usage": {},
            "error": "Schedule master not found"
        }
    
    episodes = schedule.get("episodes", [])
    locked_count = 0
    conflicts = []
    asset_usage = {}
    
    # Load existing asset usage index
    if ASSET_USAGE_INDEX_PATH.exists():
        try:
            with ASSET_USAGE_INDEX_PATH.open("r", encoding="utf-8") as f:
                asset_usage = json.load(f)
        except Exception:
            asset_usage = {}
    else:
        asset_usage = {"images": {}, "songs": {}, "episodes": {}}
    
    # Check output directory for published episodes
    output_files = {}
    if OUTPUT_DIR.exists():
        for file_path in OUTPUT_DIR.glob("*"):
            if file_path.is_file():
                # Extract episode_id from filename (e.g., "20251103_video.mp4" -> "20251103")
                parts = file_path.stem.split("_")
                if parts and len(parts[0]) == 8 and parts[0].isdigit():
                    episode_id = parts[0]
                    output_files[episode_id] = str(file_path)
    
    # Process episodes
    for episode in episodes:
        episode_id = episode.get("episode_id")
        schedule_date = episode.get("schedule_date", "")
        current_status = episode.get("status", "待制作")
        
        # Lock if published (has output file or after threshold date)
        should_lock = False
        lock_reason = None
        
        if episode_id in output_files:
            should_lock = True
            lock_reason = f"Output file exists: {output_files[episode_id]}"
        elif schedule_date >= LOCK_DATE_THRESHOLD and current_status in ["已完成", "排播完毕待播出"]:
            should_lock = True
            lock_reason = f"Published after {LOCK_DATE_THRESHOLD}"
        
        if should_lock and current_status != "已锁定":
            episode["status"] = "已锁定"
            episode["locked_at"] = datetime.utcnow().isoformat()
            episode["lock_reason"] = lock_reason
            locked_count += 1
        
        # Track asset usage
        image_path = episode.get("image_path")
        if image_path:
            if image_path not in asset_usage["images"]:
                asset_usage["images"][image_path] = []
            asset_usage["images"][image_path].append(episode_id)
        
        # Check for conflicts
        if image_path and len(asset_usage["images"].get(image_path, [])) > 1:
            conflicts.append({
                "type": "image_reuse",
                "asset": image_path,
                "episodes": asset_usage["images"][image_path],
                "severity": "warning"
            })
        
        # Track episode in asset usage
        if episode_id:
            asset_usage["episodes"][episode_id] = {
                "schedule_date": schedule_date,
                "status": episode.get("status"),
                "image_path": image_path,
                "output_file": output_files.get(episode_id)
            }
    
    # Save updated schedule
    save_schedule_master(schedule)
    
    # Save asset usage index atomically
    from ..utils.atomic_write import atomic_write_json
    atomic_write_json(ASSET_USAGE_INDEX_PATH, asset_usage)
    
    return {
        "locked_count": locked_count,
        "new_episodes": len(output_files) - len([e for e in episodes if e.get("status") == "已锁定"]),
        "conflicts": conflicts,
        "asset_usage": {
            "total_images": len(asset_usage.get("images", {})),
            "total_episodes": len(asset_usage.get("episodes", {})),
            "duplicate_images": len([k for k, v in asset_usage.get("images", {}).items() if len(v) > 1])
        },
        "timestamp": datetime.utcnow().isoformat()
    }

