"""
Plan and Run Routes for T2R

Generate recipes and execute runbooks for episode creation.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import logging
import json
import os
import hashlib
import asyncio
from pathlib import Path

from routes.websocket import broadcast_t2r_event
from ..services.schedule_service import load_schedule_master
from ..services.runbook_journal import add_run_entry, get_run_status, resume_from_run_id
from ..services.retry_manager import load_retry_policy, execute_with_retry
from ..utils.atomic_write import atomic_write_json

router = APIRouter()
logger = logging.getLogger(__name__)

# Use resolve() for stable path calculation
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
DATA_ROOT = Path(os.getenv("DATA_ROOT", str(REPO_ROOT / "data")))
ASSET_INDEX_PATH = DATA_ROOT / "asset_usage_index.json"
RUN_JOURNAL_PATH = DATA_ROOT / "run_journal.json"


def compute_recipe_hash(episode_id: str, schedule_date: str, image_path: Optional[str]) -> str:
    """Compute hash for recipe to ensure idempotency"""
    content = f"{episode_id}:{schedule_date}:{image_path or ''}"
    return hashlib.md5(content.encode()).hexdigest()[:8]


class PlanRequest(BaseModel):
    episode_id: str
    start_date: Optional[str] = None
    avoid_duplicates: bool = True
    seo_template: bool = True


class RunRequest(BaseModel):
    episode_id: str
    recipe_path: Optional[str] = None
    stages: List[str] = ["remix", "render", "upload", "verify"]
    dry_run: bool = False


@router.post("/plan")
async def plan_episode(request: PlanRequest) -> Dict:
    """
    Generate episode recipe with duplicate avoidance and SEO template.
    
    Returns:
        {
            "status": "ok",
            "summary": Dict,
            "recipe": Dict,
            "recipe_json_path": str,
            "cli_command": str,
            "errors": List[str]
        }
    """
    logger.info(f"Planning episode {request.episode_id}")
    
    errors = []
    
    # Load schedule master
    schedule = load_schedule_master()
    episode_info = None
    if schedule:
        for ep in schedule.get("episodes", []):
            if ep.get("episode_id") == request.episode_id:
                episode_info = ep
                break
    
    if not episode_info:
        errors.append(f"Episode {request.episode_id} not found in schedule")
    
    # Load asset usage index for duplicate avoidance
    asset_usage = {}
    if ASSET_INDEX_PATH.exists() and request.avoid_duplicates:
        try:
            with ASSET_INDEX_PATH.open("r", encoding="utf-8") as f:
                asset_usage = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load asset usage index: {e}")
    
    # Generate recipe
    schedule_date = request.start_date or episode_info.get("schedule_date") or datetime.now().strftime("%Y-%m-%d")
    image_path = episode_info.get("image_path") if episode_info else None
    
    recipe = {
        "episode_id": request.episode_id,
        "schedule_date": schedule_date,
        "stages": ["remix", "render", "upload", "verify"],
        "assets": {
            "image": image_path,
            "tracks": []  # Will be populated by remix stage
        },
        "seo": {
            "title_template": "[60min 170BPM] Ambient Music | {episode_id}",
            "description_template": "Ambient music mix for {episode_id}. CC0 Public Domain."
        } if request.seo_template else {},
        "avoid_duplicates": request.avoid_duplicates,
        "duplicate_checks": {
            "images_used": list(asset_usage.get("images", {}).keys()) if request.avoid_duplicates else [],
            "songs_used": []  # Could be expanded
        }
    }
    
    # Save recipe atomically with hash for idempotency
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    recipe_hash = compute_recipe_hash(request.episode_id, schedule_date, image_path)
    recipe_path = DATA_ROOT / f"{request.episode_id}-{recipe_hash}.json"
    
    if not atomic_write_json(recipe_path, recipe):
        errors.append(f"Failed to save recipe: {recipe_path}")
    
    # Generate CLI command
    cli_command = f"python scripts/local_picker/create_mixtape.py --episode-id {request.episode_id} --recipe {recipe_path}"
    
    return {
        "status": "ok" if not errors else "error",
        "summary": {
            "episode_id": request.episode_id,
            "recipe_saved": len(errors) == 0
        },
        "recipe": recipe,
        "recipe_json_path": str(recipe_path) if len(errors) == 0 else None,
        "cli_command": cli_command,
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat()
    }


async def _execute_stage(stage: str, episode_id: str, recipe_path: Optional[str] = None):
    """
    Execute a single runbook stage.
    
    This is a placeholder - in production, would call actual CLI scripts.
    """
    logger.info(f"Executing stage {stage} for episode {episode_id}")
    # Simulate work (remove in production)
    await asyncio.sleep(0.5)
    
    # Simulate occasional failures for testing
    import random
    if random.random() < 0.1:  # 10% failure rate for testing
        raise Exception(f"Simulated failure in {stage} stage")


async def execute_runbook_stages(
    run_id: str,
    episode_id: str,
    stages: List[str],
    recipe_path: Optional[str] = None,
    resume_from: Optional[str] = None
):
    """
    Background task to execute runbook stages with retry logic and error handling.
    
    This runs asynchronously using asyncio.create_task() and updates journal + broadcasts WS events.
    """
    total_stages = len(stages)
    retry_policy = load_retry_policy()
    
    try:
        # Initialize run in journal
        add_run_entry(
            RUN_JOURNAL_PATH,
            run_id,
            episode_id,
            "planning",
            "running",
            "Runbook started" if not resume_from else f"Runbook resuming from {resume_from}",
            started_at=datetime.utcnow().isoformat()
        )
        
        # Broadcast start
        await broadcast_t2r_event("runbook_stage_update", {
            "run_id": run_id,
            "episode_id": episode_id,
            "stage": "planning",
            "progress": 0,
            "message": "Runbook started" if not resume_from else f"Resuming from {resume_from}"
        }, level="info", immediate=True)
        
        # Determine start index if resuming
        start_idx = 0
        if resume_from:
            try:
                start_idx = stages.index(resume_from)
            except ValueError:
                logger.warning(f"Resume point {resume_from} not found in stages, starting from beginning")
        
        # Execute each stage with retry logic
        for idx in range(start_idx, len(stages)):
            stage = stages[idx]
            stage_start = datetime.utcnow().isoformat()
            
            # Calculate progress: use (idx + 1) for better UX
            progress = int(((idx + 1) / total_stages) * 100)
            
            # Update journal: stage started
            add_run_entry(
                RUN_JOURNAL_PATH,
                run_id,
                episode_id,
                stage,
                "running",
                f"Executing {stage} stage",
                started_at=stage_start
            )
            
            # Broadcast stage start
            await broadcast_t2r_event("runbook_stage_update", {
                "run_id": run_id,
                "episode_id": episode_id,
                "stage": stage,
                "progress": progress,
                "message": f"Executing {stage} stage"
            }, level="info")
            
            # Execute stage with retry
            success, error = await execute_with_retry(
                stage,
                _execute_stage,
                stage,
                episode_id,
                recipe_path,
                policy=retry_policy
            )
            
            if not success:
                # Stage failed after retries
                stage_end = datetime.utcnow().isoformat()
                error_msg = str(error) if error else "Unknown error"
                
                add_run_entry(
                    RUN_JOURNAL_PATH,
                    run_id,
                    episode_id,
                    stage,
                    "failed",
                    f"{stage} stage failed: {error_msg}",
                    error=error_msg,
                    started_at=stage_start,
                    ended_at=stage_end
                )
                
                # Broadcast error
                await broadcast_t2r_event("runbook_error", {
                    "run_id": run_id,
                    "episode_id": episode_id,
                    "stage": stage,
                    "error": error_msg,
                    "retry_point": stage
                }, level="error", immediate=True)
                
                # Mark run as failed
                add_run_entry(
                    RUN_JOURNAL_PATH,
                    run_id,
                    episode_id,
                    "failed",
                    "failed",
                    f"Runbook failed at {stage} stage",
                    error=error_msg,
                    started_at=datetime.utcnow().isoformat(),
                    ended_at=datetime.utcnow().isoformat()
                )
                return
            
            # Stage succeeded
            stage_end = datetime.utcnow().isoformat()
            add_run_entry(
                RUN_JOURNAL_PATH,
                run_id,
                episode_id,
                stage,
                "completed",
                f"{stage} stage completed",
                started_at=stage_start,
                ended_at=stage_end
            )
        
        # Final completion
        add_run_entry(
            RUN_JOURNAL_PATH,
            run_id,
            episode_id,
            "completed",
            "completed",
            "Runbook completed successfully",
            started_at=datetime.utcnow().isoformat(),
            ended_at=datetime.utcnow().isoformat()
        )
        
        await broadcast_t2r_event("runbook_stage_update", {
            "run_id": run_id,
            "episode_id": episode_id,
            "stage": "completed",
            "progress": 100,
            "message": "Runbook completed"
        }, level="info", immediate=True)
        
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f"Unexpected error in runbook execution: {e}", exc_info=True)
        await broadcast_t2r_event("runbook_error", {
            "run_id": run_id,
            "episode_id": episode_id,
            "error": str(e),
            "message": "Unexpected error in runbook execution"
        }, level="error", immediate=True)
        
        add_run_entry(
            RUN_JOURNAL_PATH,
            run_id,
            episode_id,
            "failed",
            "failed",
            f"Runbook failed with unexpected error: {e}",
            error=str(e),
            started_at=datetime.utcnow().isoformat(),
            ended_at=datetime.utcnow().isoformat()
        )


@router.post("/run")
async def run_episode(request: RunRequest) -> Dict:
    """
    Execute runbook for episode creation.
    
    Stages:
    - remix: Audio mixing
    - render: Video rendering
    - upload: Upload to platform
    - verify: Post-upload verification
    
    Returns:
        {
            "status": "ok",
            "summary": Dict,
            "run_id": str,
            "current_stage": str,
            "progress": float,
            "errors": List[str]
        }
    """
    logger.info(f"Running episode {request.episode_id} with stages {request.stages}")
    
    run_id = f"run_{request.episode_id}_{int(datetime.utcnow().timestamp())}"
    
    if request.dry_run:
        await broadcast_t2r_event("runbook_stage_update", {
            "run_id": run_id,
            "episode_id": request.episode_id,
            "stage": "completed",
            "progress": 100,
            "message": "Dry run completed"
        })
        
        return {
            "status": "ok",
            "summary": {
                "run_id": run_id,
                "dry_run": True
            },
            "run_id": run_id,
            "dry_run": True,
            "stages": request.stages,
            "message": "Dry run completed - no actual execution",
            "errors": [],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # Check if resuming from a previous run
    resume_from = None
    if request.episode_id:
        resume_info = resume_from_run_id(RUN_JOURNAL_PATH, run_id)
        if resume_info and resume_info.get("resume_available"):
            resume_from = resume_info.get("retry_point")
            logger.info(f"Resuming run {run_id} from stage: {resume_from}")
    
    # Start background task using asyncio.create_task() (true non-blocking)
    task = asyncio.create_task(
        execute_runbook_stages(
            run_id,
            request.episode_id,
            request.stages,
            request.recipe_path,
            resume_from=resume_from
        )
    )
    # Store task reference for potential cancellation (optional)
    logger.debug(f"Started runbook task: {run_id}")
    
    # Return immediately with run_id
    return {
        "status": "ok",
        "summary": {
            "run_id": run_id,
            "background": True,
            "stages": request.stages
        },
        "run_id": run_id,
        "current_stage": "planning",
        "progress": 0,
        "stages": request.stages,
        "message": "Runbook queued for execution",
        "errors": [],
        "timestamp": datetime.utcnow().isoformat()
    }

