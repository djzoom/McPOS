"""
File Service

Scans library directories for songs and images.
"""
import os
from pathlib import Path
from typing import List, Dict
from datetime import datetime


class FileService:
    """Service for file scanning and metadata extraction"""
    
    def __init__(self, library_root: str = "/app/library"):
        """Initialize file service"""
        self.library_root = Path(library_root)
        self.songs_dir = self.library_root / "songs"
        self.images_dir = self.library_root / "images"
    
    async def scan_songs(self) -> List[Dict]:
        """Scan songs directory and return track metadata"""
        tracks = []
        
        if not self.songs_dir.exists():
            return tracks
        
        # Supported audio formats
        audio_extensions = {".mp3", ".flac", ".wav", ".m4a", ".ogg"}
        
        for file_path in self.songs_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in audio_extensions:
                stat = file_path.stat()
                tracks.append({
                    "id": file_path.stem,
                    "filename": file_path.name,
                    "filepath": str(file_path.relative_to(self.library_root)),
                    "file_size_bytes": stat.st_size,
                    "discovered_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        return sorted(tracks, key=lambda x: x["filename"])
    
    async def scan_images(self) -> List[Dict]:
        """Scan images directory and return image metadata"""
        images = []
        
        if not self.images_dir.exists():
            return images
        
        # Supported image formats
        image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        
        for file_path in self.images_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                stat = file_path.stat()
                
                # Try to get image dimensions (basic, can be enhanced)
                width, height = None, None
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(file_path) as img:
                        width, height = img.size
                except Exception:
                    pass
                
                images.append({
                    "id": file_path.stem,
                    "filename": file_path.name,
                    "filepath": str(file_path.relative_to(self.library_root)),
                    "width": width,
                    "height": height,
                    "file_size_bytes": stat.st_size,
                    "discovered_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        return sorted(images, key=lambda x: x["filename"])

