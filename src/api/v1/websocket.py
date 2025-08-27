# src/api/v1/websocket.py - USER-TO-MJ CHAT ONLY (MJ-to-MJ uses HTTP API)

import json
import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
import traceback
import time

logger = logging.getLogger(__name__)
router = APIRouter()

class UserMJWebSocketManager:
    """WebSocket manager for USER-to-MJ conversations ONLY"""
    
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.user_sessions: Dict[int, dict] = {}
        self.connection_stats: Dict[str, Any] = {
            "total_connections": 0,
            "current_connections": 0,
            "messages_processed": 0,
            "errors_count": 0,
            "start_time": datetime.utcnow()
        }
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Start background tasks
        self._start_background_tasks()

    def _start_background_tasks(self):
        """Start background maintenance tasks"""
        if not self.heartbeat_task:
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        if not self.cleanup_task:
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _heartbeat_loop(self):
        """Send periodic heartbeat to detect dead connections"""
        while True:
            try:
                await asyncio.sleep(30)  # Every 30 seconds
                
                dead_connections = []
                for user_id, websocket in self.active_connections.items():
                    try:
                        # Send ping
                        await websocket.send_text(json.dumps({
                            "type": "ping",
                            "timestamp": time.time()
                        }))
                    except Exception as e:
                        logger.warning(f"Dead connection detected for user {user_id}: {e}")
                        dead_connections.append(user_id)
                
                # Clean up dead connections
                for user_id in dead_connections:
                    self.disconnect(user_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                await asyncio.sleep(5)

    async def _cleanup_loop(self):
        """Clean up old session data"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                current_time = time.time()
                stale_sessions = []
                
                for user_id, session in self.user_sessions.items():
                    # Remove sessions older than 1 hour with no activity
                    if current_time - session.get("last_activity", 0) > 3600:
                        stale_sessions.append(user_id)
                
                for user_id in stale_sessions:
                    if user_id not in self.active_connections:
                        logger.info(f"Cleaning up stale session for user {user_id}")
                        del self.user_sessions[user_id]
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(30)

    async def connect(self, websocket: WebSocket, user_id: int):
        """Connect user for USER-to-MJ chat"""
        try:
            await websocket.accept()
            self.active_connections[user_id] = websocket
            
            # Update statistics
            self.connection_stats["total_connections"] += 1
            self.connection_stats["current_connections"] = len(self.active_connections)
            
            # Initialize user session for USER-to-MJ chat
            self.user_sessions[user_id] = {
                "user_id": user_id,
                "connected_at": time.time(),
                "last_activity": time.time(),
                "status": "online",
                "messages_sent": 0,
                "messages_received": 0,
                "personality_mode": "mj",
                "session_preferences": {
                    "notifications_enabled": True,
                    "typing_indicators": True
                },
                "rate_limit": {
                    "messages": 0,
                    "window_start": time.time(),
                    "limit_per_minute": 30
                }
            }
            
            logger.info(f"✅ User {user_id} connected for USER-to-MJ chat")
            
            # Update MJ status to online
            await self._update_user_mj_status(user_id, "online")
            
            # Send welcome message
            await self.send_personal_message(user_id, {
                "type": "connection_established",
                "message": "🤖 Connected to your MJ! Ready to chat.",
                "features": [
                    "regular_chat",
                    "personality_modes", 
                    "memory_system",
                    "real_time_responses"
                ],
                "note": "MJ-to-MJ network communication uses HTTP API",
                "session_id": f"ws_{user_id}_{int(time.time())}",
                "timestamp": time.time()
            })
            
            # Deliver any queued notifications from MJ network (sent via HTTP API)
            await self._deliver_pending_notifications(user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect user {user_id}: {e}")
            self.connection_stats["errors_count"] += 1
            return False

    def disconnect(self, user_id: int, reason: str = "normal"):
        """Disconnect user from USER-to-MJ chat"""
        try:
            # Update session if exists
            if user_id in self.user_sessions:
                session = self.user_sessions[user_id]
                session["disconnected_at"] = time.time()
                session["disconnect_reason"] = reason
                session["status"] = "offline"
                
                # Log session stats
                duration = session.get("disconnected_at", 0) - session.get("connected_at", 0)
                logger.info(
                    f"USER-to-MJ session stats for user {user_id}: "
                    f"Duration: {duration:.1f}s, "
                    f"Messages sent: {session.get('messages_sent', 0)}, "
                    f"Messages received: {session.get('messages_received', 0)}"
                )
            
            # Remove active connection
            if user_id in self.active_connections:
                del self.active_connections[user_id]
            
            # Update statistics
            self.connection_stats["current_connections"] = len(self.active_connections)
            
            logger.info(f"🔌 User {user_id} disconnected from USER-to-MJ chat ({reason})")
            
            # Update MJ status to offline (background task)
            asyncio.create_task(self._update_user_mj_status(user_id, "offline"))
            
        except Exception as e:
            logger.error(f"Error during disconnect for user {user_id}: {e}")

    async def send_personal_message(self, user_id: int, message: dict) -> bool:
        """Send message to specific user"""
        if user_id not in self.active_connections:
            logger.debug(f"User {user_id} not connected - message not delivered")
            return False
        
        try:
            # Add standard fields
            if "timestamp" not in message:
                message["timestamp"] = time.time()
            
            # Send message
            websocket = self.active_connections[user_id]
            await websocket.send_text(json.dumps(message, default=str))
            
            # Update session stats
            if user_id in self.user_sessions:
                self.user_sessions[user_id]["messages_received"] += 1
                self.user_sessions[user_id]["last_activity"] = time.time()
            
            return True
            
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for user {user_id} during message send")
            self.disconnect(user_id, "websocket_disconnect")
            return False
        
        except Exception as e:
            logger.error(f"Failed to send message to user {user_id}: {e}")
            self.disconnect(user_id, "send_error")
            self.connection_stats["errors_count"] += 1
            return False

    async def send_typing_indicator(self, user_id: int, is_typing: bool, typing_user: str = "MJ") -> bool:
        """Send typing indicator"""
        if user_id not in self.user_sessions:
            return False
        
        # Check user preferences
        session = self.user_sessions[user_id]
        if not session.get("session_preferences", {}).get("typing_indicators", True):
            return False
        
        message = {
            "type": "typing_indicator",
            "is_typing": is_typing,
            "typing_user": typing_user,
            "timestamp": time.time()
        }
        
        return await self.send_personal_message(user_id, message)

    async def notify_mj_network_message_received(self, user_id: int, from_user_id: int, from_username: str, content: str, conversation_id: int) -> bool:
        """
        Notify user that they received a MJ network message
        This is called from the HTTP API when delivering MJ-to-MJ messages
        """
        if not self.is_user_online(user_id):
            return False
        
        message = {
            "type": "mj_network_message_notification",
            "from_user_id": from_user_id,
            "from_username": from_username,
            "content": content,
            "conversation_id": conversation_id,
            "notification_text": f"📨 {from_username}'s MJ says: {content}",
            "timestamp": time.time()
        }
        
        success = await self.send_personal_message(user_id, message)
        if success:
            logger.info(f"📨 Notified user {user_id} of MJ network message from {from_username}")
        
        return success

    async def notify_friend_request_received(self, user_id: int, from_user_id: int, from_username: str, request_message: str, request_id: int) -> bool:
        """
        Notify user of friend request
        Called from HTTP API when friend request is sent
        """
        if not self.is_user_online(user_id):
            return False
        
        message = {
            "type": "friend_request_notification",
            "from_user_id": from_user_id,
            "from_username": from_username,
            "request_message": request_message,
            "request_id": request_id,
            "notification_text": f"👥 {from_username} sent you a friend request: {request_message}",
            "timestamp": time.time()
        }
        
        success = await self.send_personal_message(user_id, message)
        if success:
            logger.info(f"👥 Notified user {user_id} of friend request from {from_username}")
        
        return success

    async def notify_friend_request_accepted(self, user_id: int, accepted_by_username: str) -> bool:
        """Notify user that their friend request was accepted"""
        if not self.is_user_online(user_id):
            return False
        
        message = {
            "type": "friend_request_accepted_notification",
            "accepted_by_username": accepted_by_username,
            "notification_text": f"✅ {accepted_by_username} accepted your friend request!",
            "timestamp": time.time()
        }
        
        return await self.send_personal_message(user_id, message)

    async def notify_status_update(self, user_id: int, from_username: str, status_message: str) -> bool:
        """Notify user of status update from friend"""
        if not self.is_user_online(user_id):
            return False
        
        message = {
            "type": "status_update_notification",
            "from_username": from_username,
            "status_message": status_message,
            "notification_text": f"📢 {from_username}: {status_message}",
            "timestamp": time.time()
        }
        
        return await self.send_personal_message(user_id, message)

    async def _deliver_pending_notifications(self, user_id: int):
        """Deliver any queued notifications when user comes online"""
        try:
            # This would check database for pending notifications
            # For now, just send a welcome back message
            from ...main import get_db_pool
            
            pool = await get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    # Check for pending MJ network messages
                    pending_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM pending_messages WHERE recipient_user_id = $1 AND status = 'queued'",
                        user_id
                    )
                    
                    if pending_count > 0:
                        await self.send_personal_message(user_id, {
                            "type": "pending_messages_notification",
                            "count": pending_count,
                            "message": f"📬 You have {pending_count} pending MJ messages from your network",
                            "timestamp": time.time()
                        })
        
        except Exception as e:
            logger.error(f"Error delivering pending notifications for user {user_id}: {e}")

    async def _update_user_mj_status(self, user_id: int, status: str):
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
                    logger.debug(f"🔄 MJ status updated to {status} for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to update MJ status for user {user_id}: {e}")

    async def _check_rate_limit(self, user_id: int) -> bool:
        """Check if user is within rate limits"""
        if user_id not in self.user_sessions:
            return True
        
        session = self.user_sessions[user_id]
        rate_limit = session["rate_limit"]
        current_time = time.time()
        
        # Reset window if needed
        if current_time - rate_limit["window_start"] > 60:
            rate_limit["messages"] = 0
            rate_limit["window_start"] = current_time
        
        # Check limit
        if rate_limit["messages"] >= rate_limit["limit_per_minute"]:
            return False
        
        rate_limit["messages"] += 1
        return True

    def is_user_online(self, user_id: int) -> bool:
        """Check if user is connected via WebSocket"""
        return user_id in self.active_connections

    def get_online_users(self) -> List[int]:
        """Get list of currently connected user IDs"""
        return list(self.active_connections.keys())

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics"""
        current_time = datetime.utcnow()
        uptime = current_time - self.connection_stats["start_time"]
        
        return {
            **self.connection_stats,
            "uptime_seconds": int(uptime.total_seconds()),
            "online_users": len(self.active_connections),
            "session_count": len(self.user_sessions)
        }

    async def shutdown(self):
        """Gracefully shutdown WebSocket manager"""
        logger.info("Shutting down WebSocket manager...")
        
        # Cancel background tasks
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        # Disconnect all users
        for user_id in list(self.active_connections.keys()):
            self.disconnect(user_id, "shutdown")
        
        logger.info("WebSocket manager shutdown complete")

# Global manager instance
user_mj_websocket_manager = UserMJWebSocketManager()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """WebSocket endpoint for USER-to-MJ chat ONLY"""
    await user_mj_websocket_manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                message_type = message_data.get("type", "chat")
                
                # Handle different message types
                if message_type == "chat":
                    await handle_user_chat_message(websocket, user_id, message_data)
                
                elif message_type == "ping":
                    await user_mj_websocket_manager.send_personal_message(user_id, {
                        "type": "pong",
                        "timestamp": time.time()
                    })
                
                elif message_type == "set_preferences":
                    await handle_set_preferences(user_id, message_data)
                
                elif message_type == "get_status":
                    await handle_get_status(user_id)
                
                else:
                    logger.warning(f"Unknown message type from user {user_id}: {message_type}")
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from user {user_id}: {data}")
                await user_mj_websocket_manager.send_personal_message(user_id, {
                    "type": "error",
                    "message": "Invalid message format - please send valid JSON"
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
        user_mj_websocket_manager.disconnect(user_id)
        
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for user {user_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        user_mj_websocket_manager.disconnect(user_id)

async def handle_user_chat_message(websocket: WebSocket, user_id: int, message_data: dict):
    """Handle regular user-to-MJ chat messages"""
    try:
        user_message = message_data.get("message", "")
        
        if not user_message.strip():
            return
        
        # Check rate limit
        if not await user_mj_websocket_manager._check_rate_limit(user_id):
            await user_mj_websocket_manager.send_personal_message(user_id, {
                "type": "rate_limit_exceeded",
                "message": "You're sending messages too quickly. Please slow down.",
                "timestamp": time.time()
            })
            return
        
        logger.info(f"💬 User {user_id} to MJ: {user_message[:50]}...")
        
        # Update session stats
        if user_id in user_mj_websocket_manager.user_sessions:
            user_mj_websocket_manager.user_sessions[user_id]["messages_sent"] += 1
        
        user_mj_websocket_manager.connection_stats["messages_processed"] += 1
        
        # Send typing indicator
        await user_mj_websocket_manager.send_typing_indicator(user_id, True)
        
        # Process with existing MJ logic (import from main.py)
        from ...main import process_styled_mj_message
        mj_response = await process_styled_mj_message(user_message, user_id)
        
        # Stop typing indicator
        await user_mj_websocket_manager.send_typing_indicator(user_id, False)
        
        # Send MJ response
        await user_mj_websocket_manager.send_personal_message(user_id, {
            "type": "chat_response",
            "content": mj_response,
            "mode": "mj",  # This would come from the classifier
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"Error handling chat message for user {user_id}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        await user_mj_websocket_manager.send_typing_indicator(user_id, False)
        await user_mj_websocket_manager.send_personal_message(user_id, {
            "type": "error",
            "message": "Sorry, I had trouble processing that message. Please try again.",
            "timestamp": time.time()
        })
        
        user_mj_websocket_manager.connection_stats["errors_count"] += 1

async def handle_set_preferences(user_id: int, message_data: dict):
    """Handle user preference updates"""
    try:
        preferences = message_data.get("preferences", {})
        
        if user_id in user_mj_websocket_manager.user_sessions:
            session = user_mj_websocket_manager.user_sessions[user_id]
            session["session_preferences"].update(preferences)
            
            await user_mj_websocket_manager.send_personal_message(user_id, {
                "type": "preferences_updated",
                "preferences": session["session_preferences"],
                "message": "Your preferences have been updated",
                "timestamp": time.time()
            })
            
            logger.info(f"Updated preferences for user {user_id}: {preferences}")
    
    except Exception as e:
        logger.error(f"Error updating preferences for user {user_id}: {e}")

async def handle_get_status(user_id: int):
    """Handle status request"""
    try:
        session = user_mj_websocket_manager.user_sessions.get(user_id, {})
        
        status_info = {
            "type": "status_response",
            "user_id": user_id,
            "connected_at": session.get("connected_at", 0),
            "messages_sent": session.get("messages_sent", 0),
            "messages_received": session.get("messages_received", 0),
            "personality_mode": session.get("personality_mode", "mj"),
            "preferences": session.get("session_preferences", {}),
            "timestamp": time.time()
        }
        
        await user_mj_websocket_manager.send_personal_message(user_id, status_info)
    
    except Exception as e:
        logger.error(f"Error getting status for user {user_id}: {e}")

# =====================================================
# NOTIFICATION FUNCTIONS FOR HTTP API INTEGRATION
# =====================================================

async def notify_user_of_mj_message(user_id: int, from_user_id: int, from_username: str, message_content: str, conversation_id: int) -> bool:
    """
    Notify user of MJ network message received via HTTP API
    Called from the MJ Network HTTP API when delivering messages
    """
    return await user_mj_websocket_manager.notify_mj_network_message_received(
        user_id=user_id,
        from_user_id=from_user_id,
        from_username=from_username,
        content=message_content,
        conversation_id=conversation_id
    )

async def notify_user_of_friend_request(user_id: int, from_user_id: int, from_username: str, request_message: str, request_id: int) -> bool:
    """
    Notify user of friend request via WebSocket
    Called from HTTP API when friend request is sent
    """
    return await user_mj_websocket_manager.notify_friend_request_received(
        user_id=user_id,
        from_user_id=from_user_id,
        from_username=from_username,
        request_message=request_message,
        request_id=request_id
    )

async def notify_user_of_friend_request_accepted(user_id: int, accepted_by_username: str) -> bool:
    """Notify user that their friend request was accepted"""
    return await user_mj_websocket_manager.notify_friend_request_accepted(
        user_id=user_id,
        accepted_by_username=accepted_by_username
    )

async def notify_user_of_status_update(user_id: int, from_username: str, status_message: str) -> bool:
    """Notify user of status update from friend"""
    return await user_mj_websocket_manager.notify_status_update(
        user_id=user_id,
        from_username=from_username,
        status_message=status_message
    )

async def get_online_users() -> List[int]:
    """Get list of users currently online via WebSocket"""
    return user_mj_websocket_manager.get_online_users()

async def is_user_online_websocket(user_id: int) -> bool:
    """Check if user is online via WebSocket"""
    return user_mj_websocket_manager.is_user_online(user_id)

async def get_websocket_stats() -> Dict[str, Any]:
    """Get WebSocket connection statistics"""
    return user_mj_websocket_manager.get_connection_stats()

# WebSocket status endpoint
@router.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket statistics"""
    return await get_websocket_stats()

# Export the manager and notification functions for use in HTTP APIs
__all__ = [
    "user_mj_websocket_manager", 
    "router",
    "notify_user_of_mj_message",
    "notify_user_of_friend_request", 
    "notify_user_of_friend_request_accepted",
    "notify_user_of_status_update",
    "get_online_users",
    "is_user_online_websocket",
    "get_websocket_stats"
]