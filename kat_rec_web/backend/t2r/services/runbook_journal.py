"""
Runbook Journal Service

Manages runbook execution journal for crash recovery.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def load_journal(journal_path: Path) -> Dict:
    """Load runbook journal"""
    if not journal_path.exists():
        return {"runs": []}
    
    try:
        with journal_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load journal: {e}")
        return {"runs": []}


def save_journal(journal_path: Path, journal_data: Dict) -> bool:
    """Save runbook journal atomically"""
    from ..utils.atomic_write import atomic_write_json
    return atomic_write_json(journal_path, journal_data)


def add_run_entry(
    journal_path: Path,
    run_id: str,
    episode_id: str,
    stage: str,
    status: str,
    message: str = "",
    error: Optional[str] = None,
    started_at: Optional[str] = None,
    ended_at: Optional[str] = None
) -> bool:
    """
    Add or update run entry in journal.
    
    Args:
        journal_path: Path to journal file
        run_id: Unique run identifier
        episode_id: Episode ID
        stage: Current stage
        status: "running" | "completed" | "failed"
        message: Status message
        error: Error message if failed
        started_at: ISO timestamp
        ended_at: ISO timestamp
    
    Returns:
        True if successful
    """
    journal = load_journal(journal_path)
    
    # Find existing run or create new
    run_entry = None
    for run in journal["runs"]:
        if run.get("run_id") == run_id:
            run_entry = run
            break
    
    if not run_entry:
        run_entry = {
            "run_id": run_id,
            "episode_id": episode_id,
            "created_at": started_at or datetime.utcnow().isoformat(),
            "stages": []
        }
        journal["runs"].append(run_entry)
    
    # Update or add stage entry
    stage_entry = {
        "stage": stage,
        "status": status,
        "message": message,
        "started_at": started_at or datetime.utcnow().isoformat(),
        "ended_at": ended_at
    }
    if error:
        stage_entry["error"] = error
        stage_entry["retry_point"] = stage  # Mark retry point
    
    # Find existing stage entry or append
    stage_found = False
    for existing_stage in run_entry["stages"]:
        if existing_stage.get("stage") == stage:
            existing_stage.update(stage_entry)
            stage_found = True
            break
    
    if not stage_found:
        run_entry["stages"].append(stage_entry)
    
    # Update run-level status
    run_entry["current_stage"] = stage
    run_entry["status"] = status
    run_entry["updated_at"] = datetime.utcnow().isoformat()
    
    # Keep only last 100 runs
    journal["runs"] = journal["runs"][-100:]
    
    return save_journal(journal_path, journal)


def get_run_status(journal_path: Path, run_id: str) -> Optional[Dict]:
    """Get run status from journal"""
    journal = load_journal(journal_path)
    for run in journal["runs"]:
        if run.get("run_id") == run_id:
            return run
    return None


def get_failed_runs(journal_path: Path) -> List[Dict]:
    """Get all failed runs that can be retried"""
    journal = load_journal(journal_path)
    failed = []
    for run in journal["runs"]:
        if run.get("status") == "failed":
            # Find retry point
            retry_point = None
            for stage in reversed(run.get("stages", [])):
                if stage.get("retry_point"):
                    retry_point = stage["retry_point"]
                    break
            if retry_point:
                failed.append({
                    "run_id": run["run_id"],
                    "episode_id": run["episode_id"],
                    "retry_point": retry_point,
                    "last_error": run.get("stages", [])[-1].get("error") if run.get("stages") else None,
                    "created_at": run.get("created_at")
                })
    return failed


def resume_from_run_id(journal_path: Path, run_id: str) -> Optional[Dict]:
    """
    Get run details for resume after crash.
    
    Returns run entry with retry_point if available.
    
    Args:
        journal_path: Path to journal file
        run_id: Run ID to resume
    
    Returns:
        Run entry with resume information, or None if not found
    """
    journal = load_journal(journal_path)
    for run in journal["runs"]:
        if run.get("run_id") == run_id:
            # Find last completed stage and retry point
            last_completed = None
            retry_point = None
            stages = run.get("stages", [])
            
            for stage in stages:
                if stage.get("status") == "completed":
                    last_completed = stage.get("stage")
                elif stage.get("retry_point"):
                    retry_point = stage.get("retry_point")
                    break
            
            return {
                **run,
                "last_completed_stage": last_completed,
                "retry_point": retry_point or last_completed,
                "resume_available": retry_point is not None or last_completed is not None
            }
    return None

