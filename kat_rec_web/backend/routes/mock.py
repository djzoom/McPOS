"""
Mock API Routes for Development

Provides mock data endpoints for frontend development when real services are unavailable.
"""
from fastapi import APIRouter
from typing import List, Dict
from datetime import datetime, timedelta
import random

router = APIRouter()

# Mock data generators


def generate_mock_song(index: int) -> Dict:
    """Generate a mock song entry"""
    return {
        "id": f"song_{index:04d}",
        "filename": f"track_{index:04d}.mp3",
        "filepath": f"songs/track_{index:04d}.mp3",
        "file_size_bytes": random.randint(2_000_000, 10_000_000),  # 2-10 MB
        "discovered_at": (
            datetime.now() - timedelta(days=random.randint(0, 30))
        ).isoformat(),
        "duration_seconds": random.randint(120, 300),  # 2-5 minutes
        "title": f"Track {index}",
    }


def generate_mock_image(index: int) -> Dict:
    """Generate a mock image entry"""
    dimensions = [
        (1920, 1080),
        (2560, 1440),
        (3840, 2160),
        (1280, 720),
    ]
    width, height = random.choice(dimensions)
    return {
        "id": f"image_{index:04d}",
        "filename": f"image_{index:04d}.png",
        "filepath": f"images/image_{index:04d}.png",
        "file_size_bytes": random.randint(500_000, 5_000_000),  # 0.5-5 MB
        "width": width,
        "height": height,
        "discovered_at": (
            datetime.now() - timedelta(days=random.randint(0, 30))
        ).isoformat(),
    }


def generate_mock_episode(index: int) -> Dict:
    """Generate a mock episode entry"""
    # 更真实的状态分布：大部分已完成，少数待处理
    if index < 7:
        status = "completed"
    elif index == 7:
        status = "remixing"
    elif index == 8:
        status = "pending"
    else:
        status = "error"

    episode_date = datetime.now() + timedelta(days=index)
    return {
        "episode_id": episode_date.strftime("%Y%m%d"),
        "episode_number": index + 1,
        "schedule_date": episode_date.strftime("%Y-%m-%d"),
        "title": f"Episode {index + 1}",
        "status": status,
        "image_path": f"/assets/design/images/image_{index % 100:04d}.png",
        "tracks_used": [f"Track {i}" for i in range(random.randint(20, 30))],
        "starting_track": f"Track {random.randint(1, 10)}",
        "metadata_updated_at": datetime.now().isoformat(),
    }


def generate_mock_channel(index: int) -> Dict:
    """Generate a mock channel entry"""
    is_active = index < 8  # 前8个频道活跃
    task_statuses = ["pending", "processing", "uploading", "completed", "failed"]
    task_status = random.choice(task_statuses) if is_active else None

    return {
        "id": f"CH-{index + 1:03d}",
        "name": f"Channel {chr(65 + index)}",  # A, B, C...
        "description": f"频道 {index + 1} 描述信息",
        "isActive": is_active,
        "currentTask": {
            "id": f"task_{index}",
            "status": task_status,
            "progress": random.randint(0, 100) if task_status else None,
        } if task_status else None,
        "nextSchedule": (datetime.now() + timedelta(hours=index * 2)).isoformat(),
        "queueCount": random.randint(0, 10) if is_active else 0,
        "lastUpdate": (datetime.now() - timedelta(minutes=random.randint(0, 60))).isoformat(),
    }


# Mock endpoints


@router.get("/songs")
async def mock_list_songs() -> List[Dict]:
    """
    Mock endpoint for listing songs
    
    Returns 20 mock song entries for development.
    """
    return [generate_mock_song(i) for i in range(1, 21)]


@router.get("/images")
async def mock_list_images() -> List[Dict]:
    """
    Mock endpoint for listing images
    
    Returns 15 mock image entries for development.
    """
    return [generate_mock_image(i) for i in range(1, 16)]


@router.get("/episodes")
async def mock_list_episodes() -> Dict:
    """
    Mock endpoint for listing episodes
    
    Returns mock episode data matching the metrics/episodes format.
    """
    episodes = [generate_mock_episode(i) for i in range(10)]
    return {
        "episodes": episodes,
        "total": len(episodes),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/summary")
async def mock_summary(period: str = "24h") -> Dict:
    """
    Mock endpoint for metrics summary
    
    Returns mock summary data for Mission Control dashboard.
    """
    return {
        "global_state": {
            "total_episodes": 10,
            "completed": 7,
            "error": 1,
            "remixing": 1,
            "rendering": 1,
            "pending": 0,
        },
        "stages": {
            "remixing": {"avg_duration": 120, "count": 5},
            "rendering": {"avg_duration": 300, "count": 5},
            "uploading": {"avg_duration": 60, "count": 7},
        },
        "period": period,
    }


@router.get("/events")
async def mock_events(limit: int = 20) -> Dict:
    """
    Mock endpoint for recent events
    
    Returns mock event stream data.
    """
    events = []
    for i in range(min(limit, 20)):
        event_time = datetime.now() - timedelta(minutes=i * 5)
        events.append({
            "timestamp": event_time.isoformat(),
            "stage": random.choice(["remixing", "rendering", "uploading"]),
            "status": random.choice(["completed", "failed", "started"]),
            "episode_id": f"202511{10+i:02d}",
        })

    return {
        "events": events,
        "count": len(events),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/channels")
async def mock_list_channels() -> List[Dict]:
    """
    Mock endpoint for listing channels
    
    Returns 10 mock channel entries for development.
    """
    return [generate_mock_channel(i) for i in range(10)]

