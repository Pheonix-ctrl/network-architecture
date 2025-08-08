
# src/utils/formatters.py
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

def format_conversation_for_ai(
    messages: List[Dict[str, Any]],
    include_metadata: bool = False
) -> str:
    """Format conversation messages for AI processing"""
    
    formatted_messages = []
    
    for msg in messages:
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        timestamp = msg.get('timestamp')
        
        if include_metadata and timestamp:
            formatted_msg = f"[{timestamp}] {role.title()}: {content}"
        else:
            formatted_msg = f"{role.title()}: {content}"
        
        formatted_messages.append(formatted_msg)
    
    return "\n".join(formatted_messages)

def format_memories_for_context(
    memories: List[Dict[str, Any]],
    max_memories: int = 5
) -> str:
    """Format memories for AI context"""
    
    if not memories:
        return ""
    
    # Sort by confidence and take top memories
    sorted_memories = sorted(
        memories,
        key=lambda x: x.get('confidence', 0),
        reverse=True
    )[:max_memories]
    
    formatted_memories = []
    for memory in sorted_memories:
        fact = memory.get('fact', '')
        confidence = memory.get('confidence', 0)
        
        # Add confidence indicator
        if confidence >= 0.9:
            indicator = "⭐"
        elif confidence >= 0.8:
            indicator = "✨"
        elif confidence >= 0.7:
            indicator = "💫"
        else:
            indicator = ""
        
        formatted_memories.append(f"- {fact} {indicator}")
    
    return "What I remember about you:\n" + "\n".join(formatted_memories)

def format_mj_network_message(
    from_mj_id: str,
    from_username: str,
    content: str,
    filter_level: str,
    timestamp: datetime
) -> str:
    """Format MJ network message for display"""
    
    time_str = timestamp.strftime("%H:%M")
    filter_emoji = {
        "basic": "🔒",
        "moderate": "🔓",
        "full": "🔑",
        "stranger": "👤"
    }
    
    return f"{filter_emoji.get(filter_level, '❓')} [{time_str}] {from_username} (via MJ): {content}"

def format_api_response(
    success: bool,
    data: Any = None,
    message: str = None,
    error: str = None,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Format standardized API response"""
    
    response = {
        "success": success,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if success:
        if data is not None:
            response["data"] = data
        if message:
            response["message"] = message
    else:
        response["error"] = error or "An error occurred"
    
    if metadata:
        response["metadata"] = metadata
    
    return response

def format_websocket_message(
    message_type: str,
    data: Dict[str, Any],
    user_id: Optional[int] = None
) -> str:
    """Format WebSocket message"""
    
    message = {
        "type": message_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if user_id:
        message["user_id"] = user_id
    
    return json.dumps(message, default=str)

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def format_duration(seconds: int) -> str:
    """Format duration in human readable format"""
    
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
