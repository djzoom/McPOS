"""
Track Model

Represents a single music track in the library.
Scanned from /library/songs/ directory.
"""
from sqlalchemy import Column, String, Integer, Float, DateTime
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from models.base import Base


class Track(Base):
    """SQLAlchemy model for Track"""
    __tablename__ = "tracks"
    
    id = Column(String, primary_key=True)  # filename or hash
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    title = Column(String, nullable=True)
    artist = Column(String, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    channel_id = Column(String, nullable=True)  # Future: multi-channel support
    discovered_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)


class TrackResponse(BaseModel):
    """API response model for Track"""
    id: str
    filename: str
    filepath: str
    title: Optional[str]
    artist: Optional[str]
    duration_seconds: Optional[float]
    file_size_bytes: Optional[int]
    discovered_at: datetime
    last_used_at: Optional[datetime]
    
    class Config:
        """Pydantic config"""
        from_attributes = True

