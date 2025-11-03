"""
SRT Inspection and Fix Routes for T2R

Detect and fix SRT subtitle issues (overlaps, gaps, encoding).
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import logging
import os

from ..services.srt_service import (
    parse_srt_file, inspect_srt, fix_srt_overlaps,
    format_srt_diff, save_srt_file
)
from routes.websocket import broadcast_t2r_event

router = APIRouter()
logger = logging.getLogger(__name__)

# Get paths from environment
REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
OUTPUT_ROOT = Path(os.getenv("OUTPUT_ROOT", str(REPO_ROOT / "output")))


def _safe_path(root: Path, user_path: str) -> Path:
    """Validate and resolve path to prevent directory traversal"""
    p = (root / user_path).resolve()
    root_resolved = root.resolve()
    if not str(p).startswith(str(root_resolved)):
        raise HTTPException(status_code=400, detail="Invalid path")
    return p


class SRTInspectRequest(BaseModel):
    episode_id: Optional[str] = None
    file_path: Optional[str] = None


class SRTFixRequest(BaseModel):
    episode_id: str
    strategy: str  # "clip", "shift", "merge"
    dry_run: bool = True


@router.post("/srt/inspect")
async def inspect_srt_endpoint(request: SRTInspectRequest) -> Dict:
    """
    Inspect SRT file for issues.
    
    Checks:
    - Overlapping subtitles
    - Gaps in timeline
    - Encoding issues
    
    Returns:
        {
            "status": "ok",
            "summary": Dict,
            "issues": List[Dict],
            "stats": Dict,
            "errors": List[str]
        }
    """
    logger.info(f"Inspecting SRT for episode {request.episode_id} or path {request.file_path}")
    
    errors = []
    file_path = None
    
    # Determine file path
    if request.file_path:
        # Use safe path validation to prevent directory traversal
        file_path = _safe_path(OUTPUT_ROOT, request.file_path)
    elif request.episode_id:
        # Try to find SRT file in output directory
        possible_paths = [
            OUTPUT_ROOT / request.episode_id / f"{request.episode_id}.srt",
            OUTPUT_ROOT / f"{request.episode_id}.srt",
            OUTPUT_ROOT / request.episode_id / "sub.srt",
        ]
        for path in possible_paths:
            if path.exists():
                file_path = path
                break
        
        if not file_path:
            errors.append(f"SRT file not found for episode {request.episode_id}")
    
    if not file_path or not file_path.exists():
        return {
            "status": "error",
            "errors": errors or [f"SRT file not found: {file_path}"],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # Parse and inspect
    subtitles = parse_srt_file(file_path)
    if not subtitles:
        return {
            "status": "error",
            "errors": [f"Failed to parse SRT file: {file_path}"],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    inspection_result = inspect_srt(subtitles)
    
    return {
        "status": "ok",
        "summary": {
            "file_path": str(file_path),
            "total_subtitles": len(subtitles),
            "issues_found": len(inspection_result["issues"])
        },
        "issues": inspection_result["issues"],
        "stats": inspection_result["stats"],
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/srt/fix")
async def fix_srt_endpoint(request: SRTFixRequest) -> Dict:
    """
    Fix SRT file issues using specified strategy.
    
    Strategies:
    - clip: Clip overlapping segments
    - shift: Shift timestamps to remove gaps
    - merge: Merge overlapping subtitles
    
    Returns:
        {
            "status": "ok",
            "summary": Dict,
            "fixed": bool,
            "diff": str (if dry_run),
            "changes": List[Dict],
            "output_path": str (if not dry_run),
            "errors": List[str]
        }
    """
    logger.info(f"Fixing SRT for episode {request.episode_id} with strategy {request.strategy}")
    
    errors = []
    
    # Find SRT file
    possible_paths = [
        OUTPUT_ROOT / request.episode_id / f"{request.episode_id}.srt",
        OUTPUT_ROOT / f"{request.episode_id}.srt",
        OUTPUT_ROOT / request.episode_id / "sub.srt",
    ]
    file_path = None
    for path in possible_paths:
        if path.exists():
            file_path = path
            break
    
    if not file_path:
        return {
            "status": "error",
            "errors": [f"SRT file not found for episode {request.episode_id}"],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # Parse file
    subtitles = parse_srt_file(file_path)
    if not subtitles:
        return {
            "status": "error",
            "errors": [f"Failed to parse SRT file: {file_path}"],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # Fix issues
    fixed_subtitles, changes = fix_srt_overlaps(subtitles, request.strategy)
    
    if request.dry_run:
        diff = format_srt_diff(fixed_subtitles, changes)
        return {
            "status": "ok",
            "summary": {
                "file_path": str(file_path),
                "strategy": request.strategy,
                "changes_count": len(changes)
            },
            "fixed": False,
            "diff": diff,
            "changes": changes,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat()
        }
    else:
        # Save fixed file
        output_path = file_path.parent / f"{file_path.stem}_fixed.srt"
        success = save_srt_file(fixed_subtitles, output_path)
        
        if success:
            # Broadcast fix event
            await broadcast_t2r_event("fix_applied", {
                "episode_id": request.episode_id,
                "srt_fix": {
                    "strategy": request.strategy,
                    "changes_count": len(changes),
                    "output_path": str(output_path)
                }
            }, level="info")
        
        return {
            "status": "ok" if success else "error",
            "summary": {
                "file_path": str(file_path),
                "strategy": request.strategy,
                "changes_count": len(changes)
            },
            "fixed": success,
            "changes": changes,
            "output_path": str(output_path) if success else None,
            "errors": errors if success else [f"Failed to save fixed SRT file"],
            "timestamp": datetime.utcnow().isoformat()
        }

