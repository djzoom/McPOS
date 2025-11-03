"""
Channel Model

Represents a single channel (e.g., kat_lofi) with its configuration,
OAuth tokens, assets, and logs. Designed for scalability to 10-100 channels.
"""
from sqlalchemy import Column, String, DateTime, JSON, Boolean
from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel
from models.base import Base


class Channel(Base):
    """SQLAlchemy model for Channel"""
    __tablename__ = "channels"
    
    id = Column(String, primary_key=True)  # e.g., "kat_lofi"
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    config = Column(JSON, nullable=False)  # ChannelConfig as JSON
    oauth_tokens = Column(JSON, nullable=True)  # YouTube OAuth tokens
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class ChannelConfig(BaseModel):
    """Pydantic model for channel configuration"""
    youtube_channel_id: Optional[str] = None
    playlist_id: Optional[str] = None
    upload_privacy: str = "unlisted"  # private, unlisted, public
    schedule_interval_days: int = 2
    library_paths: Dict[str, str] = {
        "songs": "/library/songs",
        "images": "/library/images"
    }
    
    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "youtube_channel_id": "UCxxxxxxxxxxxxx",
                "playlist_id": "PLxxxxxxxxxxxxx",
                "upload_privacy": "unlisted",
                "schedule_interval_days": 2,
                "library_paths": {
                    "songs": "/library/songs",
                    "images": "/library/images"
                }
            }
        }


class ChannelResponse(BaseModel):
    """API response model for Channel"""
    id: str
    name: str
    description: Optional[str]
    config: ChannelConfig
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        """Pydantic config"""
        from_attributes = True

