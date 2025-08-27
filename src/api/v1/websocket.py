# src/api/v1/websocket.py - COMPLETE WEBSOCKET WITH MJ NETWORK

import json
import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict

logger = logging.getLogger(__name__)
router = APIRouter()

class MJNetworkWebSocketManager:
    """Enhanced WebSocket manager for MJ Network features"""
    
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.user_sessions: Dict[int, dict] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """Connect user with MJ Network integration"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        
        # Initialize user session
        self.user_sessions[user_id] = {
            "connected_at": asyncio.get_event_loop().time(),
            "last_activity": asyncio.get_event_loop().time(),
            "mj_status": "online"
        }
        
        logger.info(f"✅ User {user_id} connected via WebSocket with MJ Network")
        
        # Notify about MJ Network features
        await self.send_system_message(user_id, {
            "type": "mj_network_status",
            "message": "🌐 MJ Network active - Your MJ can now communicate with friends' MJs",
            "features": ["mj_to_mj_chat", "friend_discovery", "offline_messaging", "status_updates"]
        })

    def disconnect(self, user_id: int):
        """Disconnect user from MJ Network"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
            
        logger.info(f"🔌 User {user_id} disconnected from MJ Network")

    async def send_personal_message(self, user_id: int, message: dict):
        """Send message to specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(json.dumps(message))
                return True
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                self.disconnect(user_id)
                return False
        return False

    async def send_system_message(self, user_id: int, system_data: dict):
        """Send system notification to user"""
        message = {
            "type": "system",
            "timestamp": asyncio.get_event_loop().time(),
            **system_data
        }
        return await self.send_personal_message(user_id, message)

    async def send_mj_network_message(self, user_id: int, from_user_id: int, from_username: str, content: str, conversation_id: int):
        """Send MJ-to-MJ network message to user"""
        message = {
            "type": "mj_network_message",
            "from_user_id": from_user_id,
            "from_username": from_username,
            "content": content,
            "conversation_id": conversation_id,
            "timestamp": asyncio.get_event_loop().time()
        }
        return await self.send_personal_message(user_id, message)

    async def notify_friend_request(self, user_id: int, request_data: dict):
        """Notify user of new friend request"""
        message = {
            "type": "friend_request",
            "data": request_data,
            "timestamp": asyncio.get_event_loop().time()
        }
        return await self.send_personal_message(user_id, message)

    async def notify_friend_online(self, user_id: int, friend_username: str, friend_user_id: int):
        """Notify user when friend comes online"""
        message = {
            "type": "friend_online",
            "friend_user_id": friend_user_id,
            "friend_username": friend_username,
            "message": f"🟢 {friend_username} is now online",
            "timestamp": asyncio.get_event_loop().time()
        }
        return await self.send_personal_message(user_id, message)

    async def broadcast_status_update(self, from_user_id: int, status_message: str, target_users: list):
        """Broadcast status update to multiple users"""
        message = {
            "type": "status_update",
            "from_user_id": from_user_id,
            "status_message": status_message,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        delivered_count = 0
        for user_id in target_users:
            if await self.send_personal_message(user_id, message):
                delivered_count += 1
        
        return delivered_count

    def is_user_online(self, user_id: int) -> bool:
        """Check if user is connected via WebSocket"""
        return user_id in self.active_connections

    def get_online_users(self) -> list:
        """Get list of currently connected user IDs"""
        return list(self.active_connections.keys())

# Global manager instance
mj_websocket_manager = MJNetworkWebSocketManager()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """Enhanced WebSocket endpoint with MJ Network features"""
    await mj_websocket_manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                message_type = message_data.get("type", "chat")
                
                # Handle different message types
                if message_type == "chat":
                    await handle_chat_message(websocket, user_id, message_data)
                
                elif message_type == "mj_talk_request":
                    await handle_mj_talk_request(websocket, user_id, message_data)
                
                elif message_type == "friend_request":
                    await handle_friend_request(websocket, user_id, message_data)
                
                elif message_type == "status_update":
                    await handle_status_update(websocket, user_id, message_data)
                
                elif message_type == "ping":
                    await mj_websocket_manager.send_personal_message(user_id, {"type": "pong"})
                
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from user {user_id}: {data}")
                await mj_websocket_manager.send_system_message(user_id, {
                    "type": "error",
                    "message": "Invalid message format"
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
        mj_websocket_manager.disconnect(user_id)
        
        # Update MJ status to offline
        await update_user_mj_status(user_id, "offline")
        
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for user {user_id}: {str(e)}")
        mj_websocket_manager.disconnect(user_id)

async def handle_chat_message(websocket: WebSocket, user_id: int, message_data: dict):
    """Handle regular user-to-MJ chat messages"""
    try:
        user_message = message_data.get("message", "")
        
        if not user_message.strip():
            return
        
        logger.info(f"💬 Chat message from user {user_id}: {user_message[:50]}...")
        
        # Process with existing MJ logic
        from ...main import process_styled_mj_message
        response = await process_styled_mj_message(user_message, user_id)
        
        # Send response
        await mj_websocket_manager.send_personal_message(user_id, {
            "type": "chat_response",
            "content": response,
            "timestamp": asyncio.get_event_loop().time()
        })
        
    except Exception as e:
        logger.error(f"Error handling chat message for user {user_id}: {e}")
        await mj_websocket_manager.send_system_message(user_id, {
            "type": "error",
            "message": "Failed to process chat message"
        })

async def handle_mj_talk_request(websocket: WebSocket, user_id: int, message_data: dict):
    """Handle MJ-to-MJ talk requests via WebSocket"""
    try:
        target_user_id = message_data.get("target_user_id")
        message_purpose = message_data.get("message_purpose", "Checking in")
        
        if not target_user_id:
            await mj_websocket_manager.send_system_message(user_id, {
                "type": "error",
                "message": "Target user ID required for MJ talk"
            })
            return
        
        logger.info(f"🤖 MJ talk request: User {user_id} -> User {target_user_id}")
        
        # Import and use MJ Communication Service
        from ...config.database import AsyncSessionLocal
        from ...services.mj_network.mj_communication import MJCommunicationService
        
        async with AsyncSessionLocal() as db:
            communication_service = MJCommunicationService(db)
            
            try:
                result = await communication_service.initiate_mj_conversation(
                    from_user_id=user_id,
                    to_user_id=target_user_id,
                    message_purpose=message_purpose,
                    conversation_topic=message_data.get("conversation_topic")
                )
                
                # Send confirmation to requesting user
                await mj_websocket_manager.send_personal_message(user_id, {
                    "type": "mj_talk_response",
                    "success": True,
                    "message": "Your MJ successfully sent the message!",
                    "conversation_id": result["conversation"].id,
                    "response_content": result["response_content"],
                    "target_online": result["target_user_online"]
                })
                
                # If target user is online, deliver message immediately
                if result["target_user_online"]:
                    target_username = await get_username_by_id(target_user_id)
                    sender_username = await get_username_by_id(user_id)
                    
                    await mj_websocket_manager.send_mj_network_message(
                        user_id=target_user_id,
                        from_user_id=user_id,
                        from_username=sender_username,
                        content=result["response_content"],
                        conversation_id=result["conversation"].id
                    )
                
                # Queue for offline delivery if needed
                if not result["target_user_online"]:
                    # This will be handled by the background task system
                    pass
                
            except ValueError as e:
                await mj_websocket_manager.send_system_message(user_id, {
                    "type": "mj_talk_error", 
                    "message": str(e)
                })
            
    except Exception as e:
        logger.error(f"Error handling MJ talk request for user {user_id}: {e}")
        await mj_websocket_manager.send_system_message(user_id, {
            "type": "error",
            "message": "Failed to process MJ talk request"
        })

async def handle_friend_request(websocket: WebSocket, user_id: int, message_data: dict):
    """Handle friend requests via WebSocket"""
    try:
        action = message_data.get("action")  # "send", "accept", "reject"
        
        if action == "send":
            target_user_id = message_data.get("target_user_id")
            request_message = message_data.get("message", "")
            
            from ...config.database import AsyncSessionLocal
            from ...services.mj_network.friend_management import FriendManagementService
            
            async with AsyncSessionLocal() as db:
                friend_service = FriendManagementService(db)
                
                try:
                    friend_request = await friend_service.send_friend_request(
                        from_user_id=user_id,
                        to_user_id=target_user_id,
                        request_message=request_message,
                        discovery_method="websocket"
                    )
                    
                    # Notify sender
                    await mj_websocket_manager.send_personal_message(user_id, {
                        "type": "friend_request_sent",
                        "target_user_id": target_user_id,
                        "request_id": friend_request.id,
                        "message": "Friend request sent successfully!"
                    })
                    
                    # Notify recipient if online
                    if mj_websocket_manager.is_user_online(target_user_id):
                        sender_username = await get_username_by_id(user_id)
                        await mj_websocket_manager.notify_friend_request(target_user_id, {
                            "request_id": friend_request.id,
                            "from_user_id": user_id,
                            "from_username": sender_username,
                            "message": request_message
                        })
                
                except ValueError as e:
                    await mj_websocket_manager.send_system_message(user_id, {
                        "type": "friend_request_error",
                        "message": str(e)
                    })
        
        elif action in ["accept", "reject"]:
            request_id = message_data.get("request_id")
            
            from ...config.database import AsyncSessionLocal
            from ...services.mj_network.friend_management import FriendManagementService
            
            async with AsyncSessionLocal() as db:
                friend_service = FriendManagementService(db)
                
                try:
                    if action == "accept":
                        result = await friend_service.accept_friend_request(
                            request_id=request_id,
                            accepting_user_id=user_id,
                            response_message=message_data.get("response_message")
                        )
                        
                        await mj_websocket_manager.send_personal_message(user_id, {
                            "type": "friend_request_accepted",
                            "message": "Friend request accepted! You are now connected.",
                            "new_friend_id": result["relationship"].friend_user_id
                        })
                    
                    else:  # reject
                        await friend_service.reject_friend_request(
                            request_id=request_id,
                            rejecting_user_id=user_id,
                            response_message=message_data.get("response_message")
                        )
                        
                        await mj_websocket_manager.send_personal_message(user_id, {
                            "type": "friend_request_rejected", 
                            "message": "Friend request rejected."
                        })
                
                except ValueError as e:
                    await mj_websocket_manager.send_system_message(user_id, {
                        "type": "friend_request_error",
                        "message": str(e)
                    })
        
    except Exception as e:
        logger.error(f"Error handling friend request for user {user_id}: {e}")

async def handle_status_update(websocket: WebSocket, user_id: int, message_data: dict):
    """Handle status updates via WebSocket"""
    try:
        status_message = message_data.get("status_message", "")
        target_users = message_data.get("target_users")  # Optional list of specific users
        
        from ...config.database import AsyncSessionLocal
        from ...services.mj_network.mj_communication import MJCommunicationService
        
        async with AsyncSessionLocal() as db:
            communication_service = MJCommunicationService(db)
            
            result = await communication_service.send_status_update(
                from_user_id=user_id,
                status_message=status_message,
                target_users=target_users
            )
            
            # Send confirmation
            await mj_websocket_manager.send_personal_message(user_id, {
                "type": "status_update_sent",
                "message": f"Status update sent to {result['successful_sends']} friends",
                "successful_sends": result["successful_sends"],
                "total_targets": result["total_targets"]
            })
            
            # Broadcast to online friends immediately via WebSocket
            online_targets = [uid for uid in (target_users or []) if mj_websocket_manager.is_user_online(uid)]
            if online_targets:
                sender_username = await get_username_by_id(user_id)
                delivered_count = await mj_websocket_manager.broadcast_status_update(
                    from_user_id=user_id,
                    status_message=f"{sender_username}: {status_message}",
                    target_users=online_targets
                )
                
                logger.info(f"📢 Status update delivered to {delivered_count} online friends")
        
    except Exception as e:
        logger.error(f"Error handling status update for user {user_id}: {e}")

async def update_user_mj_status(user_id: int, status: str):
    """Update user's MJ status in database"""
    try:
        from ...main import get_db_pool
        
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE mj_registry SET status = $1, last_seen = NOW() WHERE user_id = $2",
                    status, user_id
                )
                logger.info(f"Updated MJ status to {status} for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to update MJ status for user {user_id}: {e}")

async def get_username_by_id(user_id: int) -> str:
    """Get username by user ID"""
    try:
        from ...main import get_db_pool
        
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                username = await conn.fetchval(
                    "SELECT username FROM users WHERE id = $1",
                    user_id
                )
                return username or f"User_{user_id}"
        return f"User_{user_id}"
    except Exception as e:
        logger.error(f"Failed to get username for user {user_id}: {e}")
        return f"User_{user_id}"

# Export the manager for use in other parts of the application
__all__ = ["mj_websocket_manager", "router"]