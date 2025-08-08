# src/models/schemas/user.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    preferred_mode: Optional[str] = None
    voice_enabled: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    mj_instance_id: str
    preferred_mode: str
    is_active: bool
    is_online: bool
    created_at: datetime
    last_active: datetime
    
    class Config:
        from_attributes = True
