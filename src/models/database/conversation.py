
# src/models/database/conversation.py
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import enum
import uuid
from ...config.database import Base

class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class PersonalityMode(str, enum.Enum):
    MJ = "mj"
    KALKI = "kalki"
    JUPITER = "jupiter"
    EDUCATIONAL = "educational"
    HEALTHCARE = "healthcare"

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), default=uuid.uuid4, index=True)
    
    # Message Content
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    personality_mode = Column(Enum(PersonalityMode), default=PersonalityMode.MJ)
    
    # Metadata
    tokens_used = Column(Integer, default=0)
    response_time_ms = Column(Integer)
    embedding = Column(ARRAY(Float))  # Store embeddings directly
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    memories = relationship("Memory", back_populates="source_conversation")
