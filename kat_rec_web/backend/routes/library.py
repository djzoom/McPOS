"""
Library Routes

API endpoints for music and image library management.
"""
from fastapi import APIRouter
from typing import List, Dict
from services.file_service import FileService

router = APIRouter()

# Initialize file service
file_service = FileService()


@router.get("/songs")
async def list_songs() -> List[Dict]:
    """
    List all songs in the library
    
    Scans /library/songs/ directory and returns metadata.
    Future: filter by channel_id query param.
    """
    tracks = await file_service.scan_songs()
    return tracks


@router.get("/images")
async def list_images() -> List[Dict]:
    """
    List all images in the library
    
    Scans /library/images/ directory and returns metadata.
    Future: filter by channel_id query param.
    """
    images = await file_service.scan_images()
    return images

