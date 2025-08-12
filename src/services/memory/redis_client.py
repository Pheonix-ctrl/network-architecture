# src/services/memory/redis_client.py - Add missing WebSocket methods

import redis
import logging
from typing import Optional, Any
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.host = host
        self.port = port
        self.db = db
        self.client: Optional[redis.Redis] = None
        self.is_connected = False
        
    async def connect(self):
        """Connect to Redis with proper error handling"""
        try:
            self.client = redis.Redis(
                host=self.host, 
                port=self.port, 
                db=self.db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Test connection
            self.client.ping()
            self.is_connected = True
            logger.info(f"✅ Redis connected successfully at {self.host}:{self.port}")
            return True
            
        except redis.ConnectionError as e:
            logger.warning(f"Redis connection failed: {e}")
            logger.info("🔄 Continuing without Redis caching...")
            self.is_connected = False
            self.client = None
            return False
            
        except Exception as e:
            logger.error(f"Unexpected Redis error: {e}")
            self.is_connected = False
            self.client = None
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis with fallback"""
        if not self.is_connected or not self.client:
            return None
            
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Redis GET error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in Redis with fallback"""
        if not self.is_connected or not self.client:
            return False
            
        try:
            self.client.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.warning(f"Redis SET error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        if not self.is_connected or not self.client:
            return False
            
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis DELETE error for key {key}: {e}")
            return False
    
    # ADD THESE MISSING WEBSOCKET METHODS:
    async def store_websocket_session(self, user_id: int, session_data: dict = None) -> bool:
        """Store WebSocket session information"""
        if not self.is_connected:
            return False
            
        try:
            if not session_data:
                session_data = {
                    "user_id": user_id,
                    "connected_at": datetime.utcnow().isoformat(),
                    "status": "active"
                }
            
            key = f"ws_session:{user_id}"
            return await self.set(key, session_data, ttl=86400)  # 24 hours
            
        except Exception as e:
            logger.warning(f"Failed to store WebSocket session for user {user_id}: {e}")
            return False
    
    async def remove_websocket_session(self, user_id: int) -> bool:
        """Remove WebSocket session"""
        if not self.is_connected:
            return False
            
        try:
            key = f"ws_session:{user_id}"
            return await self.delete(key)
            
        except Exception as e:
            logger.warning(f"Failed to remove WebSocket session for user {user_id}: {e}")
            return False
    
    async def get_websocket_session(self, user_id: int) -> Optional[dict]:
        """Get WebSocket session information"""
        if not self.is_connected:
            return None
            
        try:
            key = f"ws_session:{user_id}"
            return await self.get(key)
            
        except Exception as e:
            logger.warning(f"Failed to get WebSocket session for user {user_id}: {e}")
            return None
    
    def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            try:
                self.client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")
            finally:
                self.client = None
                self.is_connected = False

# Global Redis client instance
redis_client = RedisClient()

# Startup function for FastAPI
async def init_redis():
    """Initialize Redis connection at startup"""
    success = await redis_client.connect()
    if success:
        print("✅ Redis connected")
    else:
        print("⚠️ Redis unavailable - running without caching")
    return success