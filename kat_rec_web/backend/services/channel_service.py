"""
Channel Service

Manages channel operations and default channel creation.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.channel import Channel, ChannelConfig
import os


class ChannelService:
    """Service for channel operations"""
    
    def __init__(self, session: AsyncSession):
        """Initialize channel service"""
        self.session = session
        self.default_channel_id = os.getenv("CHANNEL_ID", "kat_lofi")
    
    async def ensure_default_channel(self):
        """Ensure default channel exists"""
        # Check if channel exists
        result = await self.session.execute(
            select(Channel).where(Channel.id == self.default_channel_id)
        )
        channel = result.scalar_one_or_none()
        
        if not channel:
            # Create default channel
            default_config = ChannelConfig(
                upload_privacy="unlisted",
                schedule_interval_days=2,
                library_paths={
                    "songs": "/library/songs",
                    "images": "/library/images"
                }
            )
            
            channel = Channel(
                id=self.default_channel_id,
                name="Kat Records Lo-Fi",
                description="Default Kat Records channel",
                config=default_config.dict(),
                is_active=True
            )
            self.session.add(channel)
            await self.session.flush()
            print(f"✅ Created default channel: {self.default_channel_id}")
        else:
            print(f"✅ Default channel exists: {self.default_channel_id}")
    
    async def get_channel(self, channel_id: str = None) -> Channel:
        """Get channel by ID (defaults to default channel)"""
        target_id = channel_id or self.default_channel_id
        
        result = await self.session.execute(
            select(Channel).where(Channel.id == target_id)
        )
        channel = result.scalar_one_or_none()
        
        if not channel:
            raise ValueError(f"Channel not found: {target_id}")
        
        return channel

