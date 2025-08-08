
# src/models/database/memory.py
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, JSON, Boolean, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ...config.database import Base

class Memory(Base):
    __tablename__ = "memories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    
    # Memory Content
    fact = Column(Text, nullable=False)
    context = Column(Text)
    memory_type = Column(String(20), default="personal")  # personal, preference, skill, goal
    category = Column(String(50))  # relationships, work, hobbies, etc.
    
    # Memory Metadata
    confidence = Column(Float, default=0.8)
    importance = Column(Float, default=0.5)  # How important is this memory
    relevance_tags = Column(ARRAY(String), default=[])
    
    # Embeddings for semantic search
    embedding = Column(ARRAY(Float))
    
    # Usage Statistics
    access_count = Column(Integer, default=1)
    last_accessed = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    
    # Validation
    is_validated = Column(Boolean, default=False)
    validation_source = Column(String(50))  # user_confirmation, ai_extraction, etc.
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("User", back_populates="memories")
    source_conversation = relationship("Conversation", back_populates="memories")
