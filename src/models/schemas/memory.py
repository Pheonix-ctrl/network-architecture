# src/models/schemas/memory.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class MemoryBase(BaseModel):
    fact: str
    context: Optional[str] = None
    memory_type: str = "personal"
    category: Optional[str] = None

class MemoryCreate(MemoryBase):
    confidence: Optional[float] = Field(default=0.8, ge=0.0, le=1.0)
    importance: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)
    relevance_tags: Optional[List[str]] = []

class MemoryUpdate(BaseModel):
    fact: Optional[str] = None
    context: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    importance: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_validated: Optional[bool] = None

class MemoryResponse(MemoryBase):
    id: int
    confidence: float
    importance: float
    access_count: int
    relevance_tags: List[str]
    created_at: datetime
    last_accessed: datetime
    is_validated: bool
    
    class Config:
        from_attributes = True
