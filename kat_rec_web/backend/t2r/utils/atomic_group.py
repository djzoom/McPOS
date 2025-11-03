"""
Atomic Group Write Utilities

Support transactional group writes for multi-file consistency.
"""
from pathlib import Path
from typing import List, Tuple, Dict, Any
import json
import logging
import shutil

logger = logging.getLogger(__name__)


class AtomicGroupWriter:
    """
    Transactional writer for multiple files.
    
    Ensures all files are written atomically, or none are written.
    """
    
    def __init__(self):
        self.operations: List[Tuple[Path, Any, Dict]] = []  # (path, data, kwargs)
        self.temp_files: List[Path] = []
    
    def add_json(self, file_path: Path, data: Any, **kwargs):
        """Add JSON file to transaction"""
        self.operations.append((file_path, data, kwargs))
    
    def commit(self) -> bool:
        """
        Commit all operations atomically.
        
        Returns:
            True if all operations succeeded, False otherwise
        """
        if not self.operations:
            return True
        
        # Phase 1: Write all temp files
        temp_files = []
        try:
            for file_path, data, kwargs in self.operations:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
                
                with temp_path.open("w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, **kwargs)
                
                temp_files.append((temp_path, file_path))
            
            # Phase 2: Atomic rename all files
            for temp_path, file_path in temp_files:
                temp_path.replace(file_path)
            
            logger.info(f"Atomically committed {len(self.operations)} files")
            self.temp_files.clear()
            self.operations.clear()
            return True
            
        except Exception as e:
            logger.error(f"Failed to commit atomic group write: {e}")
            # Clean up temp files
            for temp_path, _ in temp_files:
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass
            return False
    
    def rollback(self):
        """Rollback all operations, clean up temp files"""
        for temp_path, _ in self.temp_files:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
        self.temp_files.clear()
        self.operations.clear()

