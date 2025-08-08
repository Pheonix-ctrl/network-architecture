
# src/models/schemas/chat.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class PersonalityMode(str, Enum):
    MJ = "mj"
    KALKI = "kalki"
    JUPITER = "jupiter"
    EDUCATIONAL = "educational"
    HEALTHCARE = "healthcare"

class ChatMessage(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    mode: Optional[PersonalityMode] = None

class ChatResponse(BaseModel):
    content: str
    mode: PersonalityMode
    response_time_ms: int
    tokens_used: int
    session_id: str
    similar_memories: List[Dict[str, Any]] = []

class WebSocketMessage(BaseModel):
    type: str  # message, mode_change, status, etc.
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)

