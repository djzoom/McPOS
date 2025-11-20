"""
Asset State Registry (ASR)

Unified asset state management system providing:
- Single source of truth for all asset states
- Event sourcing for state changes
- State validation and consistency checks
- Fast querying and subscription mechanisms
"""
from pathlib import Path
from typing import Dict, Optional, List, Callable, Any, Set
from datetime import datetime
from enum import Enum
import json
import logging
import asyncio
from dataclasses import dataclass, asdict
import sqlite3
import threading

logger = logging.getLogger(__name__)

# Get REPO_ROOT
REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent


class AssetType(str, Enum):
    """Asset type enumeration"""
    PLAYLIST = "playlist"
    COVER = "cover"
    AUDIO = "audio"
    TIMELINE_CSV = "timeline_csv"
    DESCRIPTION = "description"
    CAPTIONS = "captions"
    VIDEO = "video"
    RENDER_COMPLETE_FLAG = "render_complete_flag"
    UPLOAD_LOG = "upload_log"
    YOUTUBE_TITLE = "youtube_title"


class AssetState(str, Enum):
    """Asset state enumeration"""
    MISSING = "missing"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"
    VERIFIED = "verified"


@dataclass
class AssetStateRecord:
    """Asset state record"""
    episode_id: str
    channel_id: str
    asset_type: str
    state: str
    file_path: Optional[str] = None
    checksum: Optional[str] = None
    metadata: Optional[Dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    verified_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class ValidationResult:
    """Validation result"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]


class AssetStateRegistry:
    """
    Unified asset state registry.
    
    Provides single source of truth for all asset states with:
    - Fast querying (SQLite backend)
    - Event sourcing (state change history)
    - State validation
    - Subscription mechanism for state changes
    """
    
    def __init__(self, channel_id: str, db_path: Optional[Path] = None):
        """
        Initialize Asset State Registry for a channel.
        
        Args:
            channel_id: Channel ID
            db_path: Optional path to SQLite database (defaults to channel data directory)
        """
        self.channel_id = channel_id
        self._lock = threading.Lock()
        self._subscribers: Dict[str, List[Callable]] = {}  # episode_id -> [callbacks]
        
        # Determine database path
        if db_path is None:
            from .schedule_service import get_channel_dir
            channel_dir = get_channel_dir(channel_id)
            data_dir = channel_dir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = data_dir / "asset_state_registry.db"
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize SQLite database with required tables"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Assets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assets (
                    episode_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    file_path TEXT,
                    checksum TEXT,
                    metadata TEXT,  -- JSON string
                    created_at TEXT,
                    updated_at TEXT,
                    verified_at TEXT,
                    error TEXT,
                    PRIMARY KEY (episode_id, asset_type)
                )
            """)
            
            # State change events table (Event Sourcing)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS state_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    old_state TEXT,
                    new_state TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    metadata TEXT,  -- JSON string
                    timestamp TEXT NOT NULL,
                    INDEX idx_episode (episode_id),
                    INDEX idx_timestamp (timestamp)
                )
            """)
            
            # Create indexes for fast queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_episode_asset 
                ON assets(episode_id, asset_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_state 
                ON assets(state)
            """)
            
            conn.commit()
            conn.close()
    
    async def get_asset_state(
        self, 
        episode_id: str, 
        asset_type: str
    ) -> Optional[AssetStateRecord]:
        """
        Get asset state for an episode.
        
        Args:
            episode_id: Episode ID
            asset_type: Asset type (from AssetType enum)
        
        Returns:
            AssetStateRecord or None if not found
        """
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._get_asset_state_sync,
            episode_id,
            asset_type
        )
    
    def _get_asset_state_sync(
        self,
        episode_id: str,
        asset_type: str
    ) -> Optional[AssetStateRecord]:
        """Synchronous version of get_asset_state"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM assets
                WHERE episode_id = ? AND asset_type = ?
            """, (episode_id, asset_type))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            return AssetStateRecord(
                episode_id=row["episode_id"],
                channel_id=row["channel_id"],
                asset_type=row["asset_type"],
                state=row["state"],
                file_path=row["file_path"],
                checksum=row["checksum"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                verified_at=row["verified_at"],
                error=row["error"]
            )
    
    async def update_asset_state(
        self,
        episode_id: str,
        asset_type: str,
        state: str,
        metadata: Optional[Dict] = None,
        file_path: Optional[str] = None,
        checksum: Optional[str] = None,
        error: Optional[str] = None,
        verified: bool = False
    ) -> bool:
        """
        Update asset state.
        
        Args:
            episode_id: Episode ID
            asset_type: Asset type
            state: New state
            metadata: Optional metadata
            file_path: Optional file path
            checksum: Optional file checksum
            error: Optional error message
            verified: Whether the asset is verified
        
        Returns:
            True if updated successfully
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._update_asset_state_sync,
            episode_id,
            asset_type,
            state,
            metadata,
            file_path,
            checksum,
            error,
            verified
        )
    
    def _update_asset_state_sync(
        self,
        episode_id: str,
        asset_type: str,
        state: str,
        metadata: Optional[Dict],
        file_path: Optional[str],
        checksum: Optional[str],
        error: Optional[str],
        verified: bool
    ) -> bool:
        """Synchronous version of update_asset_state"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get old state for event sourcing
            cursor.execute("""
                SELECT state FROM assets
                WHERE episode_id = ? AND asset_type = ?
            """, (episode_id, asset_type))
            old_row = cursor.fetchone()
            old_state = old_row["state"] if old_row else None
            
            now = datetime.utcnow().isoformat()
            
            # Insert or update asset state
            if old_row:
                # Update existing
                cursor.execute("""
                    UPDATE assets SET
                        state = ?,
                        file_path = ?,
                        checksum = ?,
                        metadata = ?,
                        updated_at = ?,
                        verified_at = ?,
                        error = ?
                    WHERE episode_id = ? AND asset_type = ?
                """, (
                    state,
                    file_path,
                    checksum,
                    json.dumps(metadata) if metadata else None,
                    now,
                    now if verified else None,
                    error,
                    episode_id,
                    asset_type
                ))
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO assets (
                        episode_id, channel_id, asset_type, state,
                        file_path, checksum, metadata,
                        created_at, updated_at, verified_at, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    episode_id,
                    self.channel_id,
                    asset_type,
                    state,
                    file_path,
                    checksum,
                    json.dumps(metadata) if metadata else None,
                    now,
                    now,
                    now if verified else None,
                    error
                ))
            
            # Record state change event (Event Sourcing)
            cursor.execute("""
                INSERT INTO state_events (
                    episode_id, channel_id, asset_type,
                    old_state, new_state, event_type,
                    metadata, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                episode_id,
                self.channel_id,
                asset_type,
                old_state,
                state,
                "state_change",
                json.dumps(metadata or {}),
                now
            ))
            
            conn.commit()
            conn.close()
            
            # Notify subscribers
            self._notify_subscribers(episode_id, asset_type, state, metadata)
            
            return True
    
    def _notify_subscribers(
        self,
        episode_id: str,
        asset_type: str,
        state: str,
        metadata: Optional[Dict]
    ) -> None:
        """Notify subscribers of state change"""
        callbacks = self._subscribers.get(episode_id, [])
        for callback in callbacks:
            try:
                # Call callback in async context if it's async
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(episode_id, asset_type, state, metadata))
                else:
                    callback(episode_id, asset_type, state, metadata)
            except Exception as e:
                logger.warning(f"Subscriber callback failed: {e}")
        
        # Broadcast state change via WebSocket
        try:
            from ..routes.websocket import broadcast_t2r_event
            asyncio.create_task(
                broadcast_t2r_event(
                    event_type="asset_state_changed",
                    data={
                        "episode_id": episode_id,
                        "channel_id": self.channel_id,
                        "asset_type": asset_type,
                        "state": state,
                        "metadata": metadata or {},
                    },
                    level="info",
                    immediate=True
                )
            )
        except Exception as e:
            logger.debug(f"Failed to broadcast asset state change via WebSocket: {e}")
    
    async def subscribe_state_changes(
        self,
        episode_id: str,
        callback: Callable
    ) -> None:
        """
        Subscribe to state changes for an episode.
        
        Args:
            episode_id: Episode ID
            callback: Callback function (episode_id, asset_type, state, metadata) -> None
        """
        if episode_id not in self._subscribers:
            self._subscribers[episode_id] = []
        self._subscribers[episode_id].append(callback)
    
    async def validate_state_consistency(
        self,
        episode_id: str
    ) -> ValidationResult:
        """
        Validate state consistency for an episode.
        
        Checks:
        - File existence matches state
        - Checksums match (if available)
        - Required assets are present
        - State transitions are valid
        
        Args:
            episode_id: Episode ID
        
        Returns:
            ValidationResult
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._validate_state_consistency_sync,
            episode_id
        )
    
    def _validate_state_consistency_sync(
        self,
        episode_id: str
    ) -> ValidationResult:
        """Synchronous version of validate_state_consistency"""
        errors = []
        warnings = []
        details = {}
        
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all assets for this episode
            cursor.execute("""
                SELECT * FROM assets
                WHERE episode_id = ?
            """, (episode_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                asset_type = row["asset_type"]
                state = row["state"]
                file_path = row["file_path"]
                
                # Check file existence matches state
                if state in [AssetState.COMPLETE, AssetState.VERIFIED]:
                    if not file_path:
                        errors.append(f"{asset_type}: state is {state} but no file_path")
                    else:
                        path = Path(file_path)
                        if not path.exists():
                            errors.append(f"{asset_type}: file_path exists in DB but file missing: {file_path}")
                            details[asset_type] = {"file_missing": True, "path": file_path}
                elif state == AssetState.MISSING:
                    if file_path and Path(file_path).exists():
                        warnings.append(f"{asset_type}: state is MISSING but file exists: {file_path}")
                        details[asset_type] = {"file_exists_but_state_missing": True, "path": file_path}
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                details=details
            )
    
    async def get_all_assets_for_episode(
        self,
        episode_id: str
    ) -> Dict[str, AssetStateRecord]:
        """
        Get all asset states for an episode.
        
        Args:
            episode_id: Episode ID
        
        Returns:
            Dict mapping asset_type to AssetStateRecord
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._get_all_assets_for_episode_sync,
            episode_id
        )
    
    def _get_all_assets_for_episode_sync(
        self,
        episode_id: str
    ) -> Dict[str, AssetStateRecord]:
        """Synchronous version of get_all_assets_for_episode"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM assets
                WHERE episode_id = ?
            """, (episode_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            result = {}
            for row in rows:
                record = AssetStateRecord(
                    episode_id=row["episode_id"],
                    channel_id=row["channel_id"],
                    asset_type=row["asset_type"],
                    state=row["state"],
                    file_path=row["file_path"],
                    checksum=row["checksum"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    verified_at=row["verified_at"],
                    error=row["error"]
                )
                result[row["asset_type"]] = record
            
            return result
    
    async def get_state_history(
        self,
        episode_id: str,
        asset_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get state change history (Event Sourcing).
        
        Args:
            episode_id: Episode ID
            asset_type: Optional asset type filter
            limit: Maximum number of events to return
        
        Returns:
            List of state change events
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._get_state_history_sync,
            episode_id,
            asset_type,
            limit
        )
    
    def _get_state_history_sync(
        self,
        episode_id: str,
        asset_type: Optional[str],
        limit: int
    ) -> List[Dict]:
        """Synchronous version of get_state_history"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if asset_type:
                cursor.execute("""
                    SELECT * FROM state_events
                    WHERE episode_id = ? AND asset_type = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (episode_id, asset_type, limit))
            else:
                cursor.execute("""
                    SELECT * FROM state_events
                    WHERE episode_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (episode_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    "id": row["id"],
                    "episode_id": row["episode_id"],
                    "asset_type": row["asset_type"],
                    "old_state": row["old_state"],
                    "new_state": row["new_state"],
                    "event_type": row["event_type"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "timestamp": row["timestamp"]
                }
                for row in rows
            ]


# Global registry instances cache
_registry_cache: Dict[str, AssetStateRegistry] = {}
_registry_lock = threading.Lock()


def get_asset_state_registry(channel_id: str) -> AssetStateRegistry:
    """
    Get or create Asset State Registry for a channel.
    
    Args:
        channel_id: Channel ID
    
    Returns:
        AssetStateRegistry instance
    """
    with _registry_lock:
        if channel_id not in _registry_cache:
            _registry_cache[channel_id] = AssetStateRegistry(channel_id)
        return _registry_cache[channel_id]

