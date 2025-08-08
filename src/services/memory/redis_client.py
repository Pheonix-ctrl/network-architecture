
# src/services/memory/redis_client.py
import aioredis
import json
from typing import List, Dict, Optional, Any
from datetime import timedelta
from ...config.settings import Settings
from ...models.schemas.memory import MemoryResponse

settings = Settings()

class RedisClient:
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = await aioredis.from_url(
                settings.REDIS_URL,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
        except Exception as e:
            print(f"Redis connection error: {e}")
            self.redis = None
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
    
    # Memory Caching
    async def cache_memories(
        self,
        user_id: int,
        query: str,
        memories: List[MemoryResponse],
        ttl: int = 3600  # 1 hour
    ):
        """Cache memory search results"""
        if not self.redis:
            return
        
        try:
            key = f"memories:{user_id}:{hash(query)}"
            value = json.dumps([memory.dict() for memory in memories])
            await self.redis.setex(key, ttl, value)
        except Exception as e:
            print(f"Redis cache error: {e}")
    
    async def get_cached_memories(
        self,
        user_id: int,
        query: str
    ) -> Optional[List[MemoryResponse]]:
        """Get cached memory search results"""
        if not self.redis:
            return None
        
        try:
            key = f"memories:{user_id}:{hash(query)}"
            cached = await self.redis.get(key)
            if cached:
                data = json.loads(cached)
                return [MemoryResponse(**item) for item in data]
        except Exception as e:
            print(f"Redis get error: {e}")
        
        return None
    
    async def invalidate_user_memory_cache(self, user_id: int):
        """Invalidate all cached memories for a user"""
        if not self.redis:
            return
        
        try:
            pattern = f"memories:{user_id}:*"
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
        except Exception as e:
            print(f"Redis invalidate error: {e}")
    
    # WebSocket Session Management
    async def store_websocket_session(
        self,
        user_id: int,
        session_id: str,
        connection_data: Dict[str, Any]
    ):
        """Store WebSocket session data"""
        if not self.redis:
            return
        
        try:
            key = f"ws_session:{user_id}:{session_id}"
            value = json.dumps(connection_data)
            await self.redis.setex(key, 3600, value)  # 1 hour TTL
        except Exception as e:
            print(f"Redis session store error: {e}")
    
    async def get_websocket_session(
        self,
        user_id: int,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get WebSocket session data"""
        if not self.redis:
            return None
        
        try:
            key = f"ws_session:{user_id}:{session_id}"
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"Redis session get error: {e}")
            return None
    
    # MJ Network Discovery
    async def register_mj_instance(
        self,
        mj_id: str,
        user_info: Dict[str, Any],
        ttl: int = 300  # 5 minutes
    ):
        """Register MJ instance for network discovery"""
        if not self.redis:
            return
        
        try:
            key = f"mj_network:{mj_id}"
            value = json.dumps({
                **user_info,
                "last_seen": datetime.now().isoformat(),
                "status": "online"
            })
            await self.redis.setex(key, ttl, value)
        except Exception as e:
            print(f"Redis MJ register error: {e}")
    
    async def discover_nearby_mjs(
        self,
        location_hash: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Discover nearby MJ instances"""
        if not self.redis:
            return []
        
        try:
            # This is a simplified version - in production you'd use geo-hashing
            pattern = f"mj_network:*"
            keys = await self.redis.keys(pattern)
            
            nearby_mjs = []
            for key in keys[:limit]:
                data = await self.redis.get(key)
                if data:
                    nearby_mjs.append(json.loads(data))
            
            return nearby_mjs
        except Exception as e:
            print(f"Redis MJ discovery error: {e}")
            return []
