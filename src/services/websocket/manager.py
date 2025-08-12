# src/services/websocket/manager.py - Fixed WebSocket Manager

import logging
import json
from typing import Dict, Optional
from fastapi import WebSocket
from datetime import datetime

from ..memory.redis_client import redis_client

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.redis = redis_client

    async def connect(self, websocket: WebSocket, user_id: int):
        """Connect user WebSocket with proper error handling"""
        try:
            await websocket.accept()
            self.active_connections[user_id] = websocket
            
            # Store session in Redis (with error handling)
            try:
                await self._store_websocket_session(user_id)
            except Exception as e:
                logger.warning(f"Failed to store WebSocket session in Redis: {e}")
                # Continue without Redis - don't fail the connection
            
            logger.info(f"✅ User {user_id} connected via WebSocket")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect user {user_id}: {e}")
            raise

    async def disconnect(self, user_id: int):
        """Disconnect user WebSocket"""
        try:
            if user_id in self.active_connections:
                del self.active_connections[user_id]
                
                # Remove session from Redis (with error handling)
                try:
                    await self._remove_websocket_session(user_id)
                except Exception as e:
                    logger.warning(f"Failed to remove WebSocket session from Redis: {e}")
                
                logger.info(f"🔌 User {user_id} disconnected")
                
        except Exception as e:
            logger.error(f"Error disconnecting user {user_id}: {e}")

    async def send_personal_message(self, message: str, user_id: int):
        """Send message to specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
                return True
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                # Remove dead connection
                await self.disconnect(user_id)
                return False
        else:
            logger.warning(f"User {user_id} not connected")
            return False

    async def send_to_all(self, message: str):
        """Send message to all connected users"""
        disconnected_users = []
        
        for user_id, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            await self.disconnect(user_id)

    def get_connected_users(self) -> list:
        """Get list of connected user IDs"""
        return list(self.active_connections.keys())

    def is_user_connected(self, user_id: int) -> bool:
        """Check if user is connected"""
        return user_id in self.active_connections

    # Private methods for Redis session management
    async def _store_websocket_session(self, user_id: int):
        """Store WebSocket session info in Redis"""
        if not self.redis.is_connected:
            return False
            
        session_data = {
            "user_id": user_id,
            "connected_at": datetime.utcnow().isoformat(),
            "status": "active"
        }
        
        key = f"ws_session:{user_id}"
        return await self.redis.set(key, session_data, ttl=86400)  # 24 hours

    async def _remove_websocket_session(self, user_id: int):
        """Remove WebSocket session from Redis"""
        if not self.redis.is_connected:
            return False
            
        key = f"ws_session:{user_id}"
        return await self.redis.delete(key)

    async def get_session_info(self, user_id: int) -> Optional[dict]:
        """Get WebSocket session info from Redis"""
        if not self.redis.is_connected:
            return None
            
        key = f"ws_session:{user_id}"
        return await self.redis.get(key)

# Global connection manager instance
connection_manager = ConnectionManager()