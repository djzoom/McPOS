"""
Migration Script: Schedule Master Assets to Asset State Registry

Migrates asset data from schedule_master.json to Asset State Registry (ASR).
This script should be run once to migrate existing data.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List
from datetime import datetime

from ..services.schedule_service import load_schedule_master, get_channel_dir
from ..services.asset_service import get_asset_service
from ..services.asset_state_registry import AssetType, AssetState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_channel_assets(channel_id: str, dry_run: bool = False) -> Dict:
    """
    Migrate assets from schedule_master.json to ASR for a channel.
    
    Args:
        channel_id: Channel ID
        dry_run: If True, only report what would be migrated without actually migrating
    
    Returns:
        Migration report
    """
    logger.info(f"Starting migration for channel: {channel_id} (dry_run={dry_run})")
    
    schedule = load_schedule_master(channel_id)
    if not schedule:
        logger.warning(f"Schedule not found for channel: {channel_id}")
        return {
            "status": "error",
            "error": "Schedule not found",
            "channel_id": channel_id
        }
    
    episodes = schedule.get("episodes", [])
    logger.info(f"Found {len(episodes)} episodes to migrate")
    
    asset_service = get_asset_service(channel_id)
    
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    errors = []
    
    for episode_data in episodes:
        episode_id = episode_data.get("episode_id")
        if not episode_id:
            continue
        
        try:
            # First, scan filesystem to get current asset states
            if not dry_run:
                await asset_service.scan_and_update_episode_assets(episode_id)
            
            # Get assets from schedule_master.json
            assets = episode_data.get("assets", {})
            playlist_path = episode_data.get("playlist_path")
            
            # Migrate asset file paths to ASR
            asset_migrations = []
            
            # Map schedule_master.json keys to AssetType
            asset_mapping = {
                "audio": AssetType.AUDIO.value,
                "cover": AssetType.COVER.value,
                "timeline_csv": AssetType.TIMELINE_CSV.value,
                "description": AssetType.DESCRIPTION.value,
                "captions": AssetType.CAPTIONS.value,
                "video": AssetType.VIDEO.value,
                "render_complete_flag": AssetType.RENDER_COMPLETE_FLAG.value,
                "upload_log": AssetType.UPLOAD_LOG.value,
            }
            
            # Migrate assets from episode_data["assets"]
            for asset_key, asset_type in asset_mapping.items():
                file_path = assets.get(asset_key)
                if file_path:
                    asset_migrations.append({
                        "asset_type": asset_type,
                        "file_path": file_path,
                        "source": "schedule_master.json"
                    })
            
            # Migrate playlist_path
            if playlist_path:
                asset_migrations.append({
                    "asset_type": AssetType.PLAYLIST.value,
                    "file_path": playlist_path,
                    "source": "schedule_master.json"
                })
            
            if asset_migrations:
                if not dry_run:
                    # Update ASR with file paths from schedule_master.json
                    # Note: scan_and_update_episode_assets already updated states based on filesystem
                    # Here we just ensure file paths are recorded
                    for migration in asset_migrations:
                        asset_type = migration["asset_type"]
                        file_path = migration["file_path"]
                        
                        # Check if file exists
                        path = Path(file_path)
                        if path.exists():
                            await asset_service.registry.update_asset_state(
                                episode_id=episode_id,
                                asset_type=asset_type,
                                state=AssetState.COMPLETE.value,
                                file_path=file_path,
                                metadata={"migrated_from": "schedule_master.json"}
                            )
                        else:
                            # File doesn't exist, but record the path anyway
                            await asset_service.registry.update_asset_state(
                                episode_id=episode_id,
                                asset_type=asset_type,
                                state=AssetState.MISSING.value,
                                file_path=file_path,
                                metadata={"migrated_from": "schedule_master.json", "file_missing": True}
                            )
                
                migrated_count += 1
                logger.info(f"Migrated {len(asset_migrations)} assets for {episode_id}")
            else:
                skipped_count += 1
                logger.debug(f"No assets to migrate for {episode_id}")
        
        except Exception as e:
            error_count += 1
            error_msg = f"Error migrating {episode_id}: {e}"
            errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
    
    report = {
        "status": "completed" if error_count == 0 else "completed_with_errors",
        "channel_id": channel_id,
        "dry_run": dry_run,
        "total_episodes": len(episodes),
        "migrated": migrated_count,
        "skipped": skipped_count,
        "errors": error_count,
        "error_details": errors,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    logger.info(f"Migration completed: {migrated_count} migrated, {skipped_count} skipped, {error_count} errors")
    
    return report


async def main():
    """Main migration function"""
    import sys
    
    channel_id = sys.argv[1] if len(sys.argv) > 1 else "kat_lofi"
    dry_run = "--dry-run" in sys.argv
    
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    
    report = await migrate_channel_assets(channel_id, dry_run=dry_run)
    
    print(json.dumps(report, indent=2))
    
    if report["status"] == "completed_with_errors":
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

