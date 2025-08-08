
# src/models/schemas/network.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class MJDiscoveryRequest(BaseModel):
    discoverer_id: str
    discoverer_name: str
    discovery_method: str  # bluetooth, wifi, nearby
    signal_strength: Optional[float] = None

class MJConnectionRequest(BaseModel):
    requester_mj_id: str
    requester_user_name: str
    target_mj_id: str
    relationship_type: Optional[str] = None
    message: Optional[str] = None

class MJConnectionResponse(BaseModel):
    approved: bool
    relationship_type: Optional[str] = None
    share_level: str = "basic"
    message: Optional[str] = None

class MJTalkRequest(BaseModel):
    from_mj_id: str
    to_mj_id: str
    content: str
    context_level: str = "basic"  # basic, moderate, full
    
class MJTalkResponse(BaseModel):
    success: bool
    response: Optional[str] = None
    filtered_content: Optional[str] = None  # What was actually shared
    error: Optional[str] = None