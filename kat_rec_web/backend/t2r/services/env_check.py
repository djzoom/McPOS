"""
Environment Check Service for T2R

Validates required directories and permissions at startup.
"""
import os
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


def check_directory(path: Path, name: str, auto_create: bool = False) -> Tuple[bool, str]:
    """
    Check if directory exists and is readable/writable.
    
    Args:
        path: Directory path to check
        name: Display name for error messages
        auto_create: If True, create directory if missing
    
    Returns:
        (is_valid, error_message)
    """
    if not path.exists():
        if auto_create:
            try:
                path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Auto-created {name}: {path}")
            except Exception as e:
                return False, f"Failed to create {name}: {path} - {e}"
        else:
            return False, f"{name} does not exist: {path}"
    
    if not path.is_dir():
        return False, f"{name} is not a directory: {path}"
    
    # Check read permission
    if not os.access(path, os.R_OK):
        return False, f"{name} is not readable: {path}"
    
    # Check write permission
    if not os.access(path, os.W_OK):
        return False, f"{name} is not writable: {path}"
    
    return True, ""


def check_required_paths() -> Tuple[bool, Dict[str, any]]:
    """
    Check all required paths from environment variables.
    
    Returns:
        (all_valid, details)
    """
    errors = []
    warnings = []
    paths_checked = {}
    
    # Get repo root
    repo_root = Path(__file__).parent.parent.parent.parent.parent
    
    # Check LIBRARY_ROOT (auto-create if missing)
    library_root = Path(os.getenv("LIBRARY_ROOT", str(repo_root / "library")))
    is_valid, error = check_directory(library_root, "LIBRARY_ROOT", auto_create=True)
    paths_checked["LIBRARY_ROOT"] = {
        "path": str(library_root),
        "exists": library_root.exists(),
        "valid": is_valid,
        "error": error if not is_valid else None
    }
    if not is_valid:
        errors.append(error)
    elif not library_root.exists():
        warnings.append(f"LIBRARY_ROOT does not exist (will be created): {library_root}")
    
    # Check OUTPUT_ROOT (auto-create if missing)
    output_root = Path(os.getenv("OUTPUT_ROOT", str(repo_root / "output")))
    is_valid, error = check_directory(output_root, "OUTPUT_ROOT", auto_create=True)
    paths_checked["OUTPUT_ROOT"] = {
        "path": str(output_root),
        "exists": output_root.exists(),
        "valid": is_valid,
        "error": error if not is_valid else None
    }
    if not is_valid:
        errors.append(error)
    
    # Check CONFIG_ROOT
    config_root = Path(os.getenv("CONFIG_ROOT", str(repo_root / "config")))
    is_valid, error = check_directory(config_root, "CONFIG_ROOT")
    paths_checked["CONFIG_ROOT"] = {
        "path": str(config_root),
        "exists": config_root.exists(),
        "valid": is_valid,
        "error": error if not is_valid else None
    }
    if not is_valid:
        errors.append(error)
    
    # Check DATA_ROOT (create if doesn't exist)
    data_root = Path(os.getenv("DATA_ROOT", str(repo_root / "data")))
    paths_checked["DATA_ROOT"] = {
        "path": str(data_root),
        "exists": data_root.exists(),
        "valid": True,  # Will be created if needed
        "error": None
    }
    if not data_root.exists():
        try:
            data_root.mkdir(parents=True, exist_ok=True)
            warnings.append(f"DATA_ROOT created: {data_root}")
        except Exception as e:
            errors.append(f"Failed to create DATA_ROOT: {e}")
    
    # Check schedule_master.json
    schedule_path = config_root / "schedule_master.json"
    paths_checked["schedule_master"] = {
        "path": str(schedule_path),
        "exists": schedule_path.exists(),
        "valid": True,  # Not required for startup
        "error": None
    }
    if not schedule_path.exists():
        warnings.append(f"schedule_master.json not found: {schedule_path}")
    
    return len(errors) == 0, {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "paths": paths_checked
    }

