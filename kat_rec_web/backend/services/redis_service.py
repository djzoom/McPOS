"""
Redis Service

Manages Redis connection for queue and cache.
"""
import redis.asyncio as redis
from typing import Optional
import json


class RedisService:
    """Redis service for queue and cache management"""
    
    def __init__(self, redis_url: str):
        """Initialize Redis service"""
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        self.client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        print(f"✅ Connected to Redis at {self.redis_url}")
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            await self.client.close()
            print("👋 Disconnected from Redis")
    
    async def ping(self) -> bool:
        """Check Redis connection"""
        try:
            if self.client:
                await self.client.ping()
                return True
        except Exception:
            pass
        return False
    
    # Queue operations
    async def enqueue_upload(self, channel_id: str, task_data: dict) -> str:
        """Add upload task to queue"""
        task_id = f"upload:{channel_id}:{task_data.get('episode_id', 'unknown')}"
        await self.client.lpush("upload_queue", json.dumps({
            "task_id": task_id,
            "channel_id": channel_id,
            **task_data
        }))
        return task_id
    
    async def get_queue_status(self) -> dict:
        """Get queue status"""
        queue_length = await self.client.llen("upload_queue")
        return {
            "queue_length": queue_length,
            "queue_name": "upload_queue"
        }
    
    # Cache operations
    async def cache_set(self, key: str, value: dict, ttl: int = 3600):
        """Set cache value"""
        await self.client.setex(
            key,
            ttl,
            json.dumps(value)
        )
    
    async def cache_get(self, key: str) -> Optional[dict]:
        """Get cache value"""
        value = await self.client.get(key)
        if value:
            return json.loads(value)
        return None

