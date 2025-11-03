"""
Retry Manager for T2R

Manages retry policies and exponential backoff for runbook stages.
"""
import json
import asyncio
from pathlib import Path
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

# Default retry policy path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
RETRY_POLICY_PATH = Path(__file__).parent.parent / "config" / "retry_policy.json"


def load_retry_policy(policy_path: Path = RETRY_POLICY_PATH) -> Dict:
    """Load retry policy from JSON file"""
    if not policy_path.exists():
        logger.warning(f"Retry policy not found: {policy_path}, using defaults")
        return {
            "default_retries": 1,
            "max_retries": 5,
            "backoff_multiplier": 2,
            "backoff_base_seconds": 1,
            "stages": {}
        }
    
    try:
        with policy_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("retry_policy", {})
    except Exception as e:
        logger.error(f"Failed to load retry policy: {e}")
        return {
            "default_retries": 1,
            "max_retries": 5,
            "backoff_multiplier": 2,
            "backoff_base_seconds": 1,
            "stages": {}
        }


def get_stage_retries(stage: str, policy: Optional[Dict] = None) -> int:
    """Get retry count for a stage"""
    if policy is None:
        policy = load_retry_policy()
    
    stage_config = policy.get("stages", {}).get(stage, {})
    return stage_config.get("retries", policy.get("default_retries", 1))


def get_backoff_seconds(stage: str, attempt: int, policy: Optional[Dict] = None) -> float:
    """Calculate backoff seconds for a retry attempt"""
    if policy is None:
        policy = load_retry_policy()
    
    stage_config = policy.get("stages", {}).get(stage, {})
    base = stage_config.get("backoff_seconds", policy.get("backoff_base_seconds", 1))
    multiplier = policy.get("backoff_multiplier", 2)
    
    # Exponential backoff: base * (multiplier ^ attempt)
    return base * (multiplier ** (attempt - 1))


async def execute_with_retry(
    stage: str,
    func,
    *args,
    max_retries: Optional[int] = None,
    policy: Optional[Dict] = None,
    **kwargs
) -> tuple[bool, Optional[Exception]]:
    """
    Execute function with retry logic.
    
    Args:
        stage: Stage name for policy lookup
        func: Async function to execute
        *args, **kwargs: Arguments for func
        max_retries: Override max retries (uses policy if None)
        policy: Override retry policy (loads from file if None)
    
    Returns:
        (success: bool, error: Optional[Exception])
    """
    if policy is None:
        policy = load_retry_policy()
    
    retries = get_stage_retries(stage, policy)
    if max_retries is not None:
        retries = max_retries
    
    last_error = None
    
    for attempt in range(1, retries + 2):  # +2 because attempt 1 is not a retry
        try:
            result = await func(*args, **kwargs)
            if attempt > 1:
                logger.info(f"Stage {stage} succeeded on attempt {attempt}")
            return True, None
        except Exception as e:
            last_error = e
            logger.warning(f"Stage {stage} failed on attempt {attempt}/{retries + 1}: {e}")
            
            if attempt <= retries:
                backoff = get_backoff_seconds(stage, attempt, policy)
                logger.info(f"Retrying {stage} after {backoff}s (attempt {attempt + 1})")
                await asyncio.sleep(backoff)
            else:
                logger.error(f"Stage {stage} failed after {retries + 1} attempts")
    
    return False, last_error

