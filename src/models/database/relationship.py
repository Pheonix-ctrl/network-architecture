
# src/models/database/relationship.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ...config.database import Base

class Relationship(Base):
    __tablename__ = "relationships"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Related Person Info
    contact_name = Column(String(100), nullable=False)
    contact_mj_id = Column(String(100))  # Their MJ instance ID if they have one
    relationship_type = Column(String(20))  # parent, sibling, friend, colleague, etc.
    
    # Privacy Settings for MJ-to-MJ communication
    share_level = Column(String(20), default="basic")  # basic, moderate, full
    restricted_topics = Column(JSON, default=list)  # Topics to filter out
    
    # Connection Status
    is_connected = Column(Boolean, default=False)  # Are their MJs connected?
    last_interaction = Column(DateTime(timezone=True))
    trust_level = Column(Float, default=0.5)  # How much to trust their MJ
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="relationships")

