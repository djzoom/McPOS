"""
Image Model

Represents a single image in the library.
Scanned from /library/images/ directory.
"""
from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from models.base import Base


class Image(Base):
    """SQLAlchemy model for Image"""
    __tablename__ = "images"
    
    id = Column(String, primary_key=True)  # filename or hash
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    channel_id = Column(String, nullable=True)  # Future: multi-channel support
    discovered_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)


class ImageResponse(BaseModel):
    """API response model for Image"""
    id: str
    filename: str
    filepath: str
    width: Optional[int]
    height: Optional[int]
    file_size_bytes: Optional[int]
    discovered_at: datetime
    last_used_at: Optional[datetime]
    
    class Config:
        """Pydantic config"""
        from_attributes = True

