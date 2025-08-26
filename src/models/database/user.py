# src/models/database/user.py - FIXED: Updated to use NetworkRelationship

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, BigInteger, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ...config.database import Base
import enum

# Define the PersonalityMode enum to match your database exactly
class PersonalityMode(enum.Enum):
    mj = "mj"
    kalki = "kalki"
    jupiter = "jupiter"
    educational = "educational"
    healthcare = "healthcare"

class User(Base):
    __tablename__ = "users"
    
    # Exact columns that exist in Supabase
    id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    mj_instance_id = Column(String(50), unique=True, index=True)
    preferred_mode = Column(Enum(PersonalityMode, name="personality_mode"), default=PersonalityMode.mj)
    is_online = Column(Boolean, default=False)
    last_active = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # EXISTING RELATIONSHIPS (keep the simple Relationship for basic relationships)
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")  
    relationships = relationship("Relationship", back_populates="user", cascade="all, delete-orphan")  # Simple relationship
    
    # MJ NETWORK RELATIONSHIPS - FIXED: Updated names to avoid conflicts
    mj_registry = relationship("MJRegistry", back_populates="user", uselist=False, cascade="all, delete-orphan")
    location = relationship("UserLocation", back_populates="user", uselist=False, cascade="all, delete-orphan")

    # Network Relationship Management - FIXED: Use NetworkRelationship and new names
    user_network_relationships = relationship("NetworkRelationship", foreign_keys="NetworkRelationship.user_id", back_populates="user", cascade="all, delete-orphan")
    friend_network_relationships = relationship("NetworkRelationship", foreign_keys="NetworkRelationship.friend_user_id", back_populates="friend")

    # Friend Requests
    sent_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.from_user_id", back_populates="from_user", cascade="all, delete-orphan")
    received_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.to_user_id", back_populates="to_user", cascade="all, delete-orphan")

    # MJ Conversations
    mj_conversations_as_a = relationship("MJConversation", foreign_keys="MJConversation.user_a_id", back_populates="user_a")
    mj_conversations_as_b = relationship("MJConversation", foreign_keys="MJConversation.user_b_id", back_populates="user_b")

    # MJ Messages
    sent_mj_messages = relationship("MJMessage", foreign_keys="MJMessage.from_user_id", back_populates="from_user")
    received_mj_messages = relationship("MJMessage", foreign_keys="MJMessage.to_user_id", back_populates="to_user")

    # Pending Messages
    pending_messages = relationship("PendingMessage", back_populates="recipient", cascade="all, delete-orphan")

    # Scheduled Check-ins
    scheduled_checkins = relationship("ScheduledCheckin", foreign_keys="ScheduledCheckin.user_id", back_populates="user", cascade="all, delete-orphan")
    received_checkins = relationship("ScheduledCheckin", foreign_keys="ScheduledCheckin.target_user_id", back_populates="target_user")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"