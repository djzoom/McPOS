"""
Channels Routes

API endpoints for channel management.
Ready for multi-channel expansion via channel_id query param.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from services.database import get_db
from services.channel_service import ChannelService
from models.channel import ChannelResponse, ChannelConfig
import json

router = APIRouter()


@router.get("/channel", response_model=ChannelResponse)
async def get_channel(
    channel_id: Optional[str] = Query(None, description="Channel ID (defaults to current channel)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get channel information
    
    Returns the current channel (default) or specified channel.
    Future: supports multi-channel by passing channel_id query param.
    """
    channel_service = ChannelService(db)
    channel = await channel_service.get_channel(channel_id)
    
    # Parse config JSON
    config_dict = channel.config if isinstance(channel.config, dict) else json.loads(channel.config)
    config = ChannelConfig(**config_dict)
    
    return ChannelResponse(
        id=channel.id,
        name=channel.name,
        description=channel.description,
        config=config,
        is_active=channel.is_active,
        created_at=channel.created_at,
        updated_at=channel.updated_at
    )

