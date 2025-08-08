
# src/services/websocket/manager.py
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional, Any
import json
import asyncio
from datetime import datetime
from ...models.schemas.chat import WebSocketMessage, PersonalityMode
from ...services.memory.redis_client import RedisClient

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}  # user_id -> websocket
        self.user_sessions: Dict[int, Dict[str, Any]] = {}  # user_id -> session_data
        self.redis = RedisClient()
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Accept WebSocket connection and register user"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        
        # Initialize session data
        self.user_sessions[user_id] = {
            "connected_at": datetime.now(),
            "current_mode": PersonalityMode.MJ,
            "last_activity": datetime.now(),
            "message_count": 0
        }
        
        # Store session in Redis
        await self.redis.store_websocket_session(
            user_id=user_id,
            session_id=f"ws_{user_id}_{datetime.now().timestamp()}",
            connection_data=self.user_sessions[user_id]
        )
        
        # Send connection confirmation
        await self.send_personal_message(user_id, {
            "type": "connection",
            "status": "connected",
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        })
    
    def disconnect(self, user_id: int):
        """Remove user connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
    
    async def send_personal_message(self, user_id: int, data: Dict[str, Any]):
        """Send message to specific user"""
        if user_id in self.active_connections:
            try:
                message = WebSocketMessage(
                    type=data.get("type", "message"),
                    data=data
                )
                await self.active_connections[user_id].send_text(message.json())
                
                # Update activity
                if user_id in self.user_sessions:
                    self.user_sessions[user_id]["last_activity"] = datetime.now()
                    self.user_sessions[user_id]["message_count"] += 1
                    
            except Exception as e:
                print(f"Error sending message to user {user_id}: {e}")
                self.disconnect(user_id)
    
    async def send_mode_change(self, user_id: int, new_mode: PersonalityMode, reason: str):
        """Send mode change notification"""
        await self.send_personal_message(user_id, {
            "type": "mode_change",
            "new_mode": new_mode.value,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        
        # Update session
        if user_id in self.user_sessions:
            self.user_sessions[user_id]["current_mode"] = new_mode
    
    async def send_typing_indicator(self, user_id: int, is_typing: bool = True):
        """Send typing indicator"""
        await self.send_personal_message(user_id, {
            "type": "typing",
            "is_typing": is_typing,
            "timestamp": datetime.now().isoformat()
        })
    
    async def send_memory_update(self, user_id: int, memory_info: Dict[str, Any]):
        """Send memory extraction/update notification"""
        await self.send_personal_message(user_id, {
            "type": "memory_update",
            "memory": memory_info,
            "timestamp": datetime.now().isoformat()
        })
    
    async def send_mj_network_event(self, user_id: int, event_data: Dict[str, Any]):
        """Send MJ network related events"""
        await self.send_personal_message(user_id, {
            "type": "mj_network",
            "event": event_data,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_user_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user session data"""
        return self.user_sessions.get(user_id)
    
    async def broadcast_to_all(self, data: Dict[str, Any]):
        """Broadcast message to all connected users"""
        message = WebSocketMessage(
            type=data.get("type", "broadcast"),
            data=data
        )
        
        disconnected_users = []
        for user_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message.json())
            except Exception as e:
                print(f"Error broadcasting to user {user_id}: {e}")
                disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            self.disconnect(user_id)
    
    def get_connected_users(self) -> List[int]:
        """Get list of currently connected user IDs"""
        return list(self.active_connections.keys())
    
    def is_user_connected(self, user_id: int) -> bool:
        """Check if user is currently connected"""
        return user_id in self.active_connections
