# src/api/v1/websocket.py - Simplified Working Version

import json
import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict

logger = logging.getLogger(__name__)
router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected via WebSocket")

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"User {user_id} disconnected")

    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")
                self.disconnect(user_id)

manager = ConnectionManager()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            try:
                # Import your existing chat processing function
                from ...api.v1.chat import process_user_message  # Adjust import path as needed
                
                # Process the message
                response = await process_user_message(
                    user_id=user_id,
                    message=message_data.get("message", ""),
                    mode=message_data.get("mode", "mj")
                )
                
                # 🚨 FIX: Handle response properly based on its type
                response_data = None
                
                if response is None:
                    # Handle None response
                    response_data = {
                        "content": "I'm having trouble responding right now. Please try again.",
                        "mode": "mj",
                        "error": "None response"
                    }
                    
                elif isinstance(response, dict):
                    # Already a dictionary
                    response_data = response
                    
                elif hasattr(response, 'model_dump'):
                    # Pydantic v2 model
                    response_data = response.model_dump()
                    
                elif hasattr(response, 'dict'):
                    # Pydantic v1 model  
                    response_data = response.dict()
                    
                elif hasattr(response, 'content'):
                    # Has content attribute
                    response_data = {
                        "content": response.content,
                        "mode": getattr(response, 'mode', 'mj'),
                        "routing_info": getattr(response, 'routing_info', {}),
                        "timestamp": getattr(response, 'timestamp', None),
                        "tokens_used": getattr(response, 'tokens_used', 0)
                    }
                    
                else:
                    # Fallback: treat as string
                    response_data = {
                        "content": str(response),
                        "mode": "mj"
                    }
                
                # Ensure content exists and isn't empty
                if not response_data.get("content") or not response_data["content"].strip():
                    response_data["content"] = "I'm having trouble finding the right words... can you try asking again?"
                
                # Debug logging
                logger.info(f"WebSocket response for user {user_id}: {type(response)} -> {response_data.get('content', '')[:100]}...")
                
                # Send response back to client
                await manager.send_personal_message(
                    json.dumps({
                        "type": "chat_response",
                        "data": response_data
                    }),
                    user_id
                )
                
            except Exception as e:
                logger.error(f"WebSocket processing error for user {user_id}: {str(e)}")
                logger.error(f"Response object type: {type(response) if 'response' in locals() else 'undefined'}")
                
                # Send error response to client
                error_response = {
                    "type": "error",
                    "data": {
                        "content": "Sorry, I encountered an error processing your message. Please try again.",
                        "mode": "mj",
                        "error": str(e)
                    }
                }
                
                await manager.send_personal_message(
                    json.dumps(error_response),
                    user_id
                )
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
        manager.disconnect(user_id)
        
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for user {user_id}: {str(e)}")
        manager.disconnect(user_id)