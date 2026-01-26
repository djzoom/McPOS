#!/usr/bin/env python3
"""
Fix images library path to use legacy assets/design/images location.

Updates the database to point to the correct images directory.
"""
import sys
import asyncio
from pathlib import Path

# Bootstrap path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root / "kat_rec_web" / "backend"))

# 导入日志工具
try:
    from utils_logging import setup_logging, logger
    setup_logging()
except ImportError:
    # 降级到标准库 logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)

from services.database import AsyncSessionLocal, init_db
from services.channel_service import ChannelService
from models.channel import ChannelLibraryConfig
from sqlalchemy import select
from services.file_service import get_repo_root


async def fix_images_path():
    """Update images path to legacy location"""
    await init_db()
    async with AsyncSessionLocal() as session:
        service = ChannelService(session)
        repo_root = get_repo_root()
        legacy_images = repo_root / 'assets' / 'design' / 'images'
        
        result = await session.execute(
            select(ChannelLibraryConfig).where(ChannelLibraryConfig.channel_id == 'kat_lofi')
        )
        config = result.scalar_one_or_none()
        if config:
            old_path = config.images_path
            config.images_path = str(legacy_images)
            await session.commit()
            logger.info(f"Updated images path: {old_path} -> {config.images_path}", event_name="fix_images_path.updated", metadata={"old_path": old_path, "new_path": config.images_path})
            logger.info(f'✅ Updated images path')
            logger.info(f'   旧路径: {old_path}')
            logger.info(f'   新路径: {config.images_path}')
        else:
            await service.ensure_library_config('kat_lofi', images_path=str(legacy_images))
            await session.commit()
            logger.info(f"Created config with images path: {legacy_images}", event_name="fix_images_path.created", metadata={"path": str(legacy_images)})
            logger.info(f'✅ Created config with images path: {legacy_images}')


if __name__ == "__main__":
    asyncio.run(fix_images_path())

