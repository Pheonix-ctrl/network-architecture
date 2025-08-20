# src/models/database/mj_network.py
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, ARRAY, JSON, DECIMAL, TIME, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import BIGINT
from ...config.database import Base
import enum

# =====================================================
# 1. MJ REGISTRY MODEL
# =====================================================

class MJStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"
    BUSY = "busy"

class MJRegistry(Base):
    __tablename__ = "mj_registry"
    
    id = Column(BIGINT, primary_key=True, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    mj_instance_id = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(String(20), default=MJStatus.OFFLINE)
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Device & Technical Info
    device_info = Column(JSON, default={})
    capabilities = Column(JSON, default={"chat": True, "location": False, "voice": False})
    version = Column(String(50), default="1.0.0")
    
    # Location Data (Optional)
    latitude = Column(DECIMAL(10, 8), nullable=True)
    longitude = Column(DECIMAL(11, 8), nullable=True)
    location_enabled = Column(Boolean, default=False)
    location_updated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Statistics
    connection_count = Column(Integer, default=0)
    total_conversations = Column(Integer, default=0)
    total_messages_sent = Column(Integer, default=0)
    total_messages_received = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="mj_registry")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(status.in_(['online', 'offline', 'away', 'busy']), name='check_mj_status'),
    )

# =====================================================
# 2. RELATIONSHIPS MODEL
# =====================================================

class RelationshipStatus(str, enum.Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    MUTED = "muted"

class Relationship(Base):
    __tablename__ = "relationships"
    
    id = Column(BIGINT, primary_key=True, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    friend_user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationship Info
    relationship_type = Column(String(50), default="friend", index=True)
    custom_relationship_name = Column(String(100), nullable=True)
    
    # Privacy & Sharing Settings
    privacy_settings = Column(JSON, default={
        "share_mood": True,
        "share_activity": True,
        "share_health": False,
        "share_life_events": True,
        "share_work": True,
        "share_location": False,
        "custom_categories": {}
    })
    
    # Restrictions
    restricted_topics = Column(ARRAY(Text), default=[])
    can_respond_when_offline = Column(Boolean, default=True)
    
    # Status
    status = Column(String(20), default=RelationshipStatus.ACTIVE, index=True)
    trust_level = Column(DECIMAL(3, 2), default=0.50)
    
    # Interaction History
    last_interaction = Column(DateTime(timezone=True), nullable=True)
    total_mj_conversations = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="user_relationships")
    friend = relationship("User", foreign_keys=[friend_user_id], back_populates="friend_relationships")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(status.in_(['active', 'blocked', 'muted']), name='check_relationship_status'),
        CheckConstraint('trust_level >= 0 AND trust_level <= 1', name='check_trust_level'),
        CheckConstraint('user_id != friend_user_id', name='check_no_self_relationship'),
    )

# =====================================================
# 3. FRIEND REQUESTS MODEL
# =====================================================

class FriendRequestStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class DiscoveryMethod(str, enum.Enum):
    MANUAL = "manual"
    PHONE_SYNC = "phone_sync"
    NEARBY = "nearby"
    MAP = "map"
    SEARCH = "search"

class FriendRequest(Base):
    __tablename__ = "friend_requests"
    
    id = Column(BIGINT, primary_key=True, index=True)
    from_user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    to_user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Request Details
    request_message = Column(Text, nullable=True)
    suggested_relationship_type = Column(String(50), default="friend")
    discovery_method = Column(String(30), default=DiscoveryMethod.MANUAL)
    
    # Status & Timing
    status = Column(String(20), default=FriendRequestStatus.PENDING, index=True)
    expires_at = Column(DateTime(timezone=True), default=func.now() + func.make_interval(days=30))
    
    # Response
    response_message = Column(Text, nullable=True)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="sent_friend_requests")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="received_friend_requests")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(status.in_(['pending', 'accepted', 'rejected', 'expired', 'cancelled']), name='check_request_status'),
        CheckConstraint(discovery_method.in_(['manual', 'phone_sync', 'nearby', 'map', 'search']), name='check_discovery_method'),
        CheckConstraint('from_user_id != to_user_id', name='check_no_self_request'),
    )

# =====================================================
# 4. MJ CONVERSATIONS MODEL
# =====================================================

class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    BLOCKED = "blocked"

class PrivacyLevel(str, enum.Enum):
    MINIMAL = "minimal"
    NORMAL = "normal"
    DETAILED = "detailed"

class MJConversation(Base):
    __tablename__ = "mj_conversations"
    
    id = Column(BIGINT, primary_key=True, index=True)
    
    # Participants (both users involved)
    user_a_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_b_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Conversation Metadata
    initiated_by_user_id = Column(BIGINT, ForeignKey("users.id"), nullable=False)
    conversation_topic = Column(String(200), nullable=True)
    
    # Status & Activity
    status = Column(String(20), default=ConversationStatus.ACTIVE, index=True)
    last_message_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    message_count = Column(Integer, default=0)
    
    # Privacy Context
    relationship_id = Column(BIGINT, ForeignKey("relationships.id"), nullable=True)
    privacy_level = Column(String(20), default=PrivacyLevel.NORMAL)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user_a = relationship("User", foreign_keys=[user_a_id], back_populates="mj_conversations_as_a")
    user_b = relationship("User", foreign_keys=[user_b_id], back_populates="mj_conversations_as_b")
    initiator = relationship("User", foreign_keys=[initiated_by_user_id])
    relationship = relationship("Relationship", back_populates="mj_conversations")
    messages = relationship("MJMessage", back_populates="conversation", cascade="all, delete-orphan")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(status.in_(['active', 'archived', 'blocked']), name='check_conversation_status'),
        CheckConstraint(privacy_level.in_(['minimal', 'normal', 'detailed']), name='check_privacy_level'),
        CheckConstraint('user_a_id != user_b_id', name='check_different_users'),
    )

# =====================================================
# 5. MJ MESSAGES MODEL
# =====================================================

class MessageType(str, enum.Enum):
    TEXT = "text"
    STATUS_UPDATE = "status_update"
    CHECK_IN = "check_in"
    QUESTION = "question"
    RESPONSE = "response"

class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class MJMessage(Base):
    __tablename__ = "mj_messages"
    
    id = Column(BIGINT, primary_key=True, index=True)
    conversation_id = Column(BIGINT, ForeignKey("mj_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Message Origin
    from_user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    to_user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Message Content
    message_content = Column(Text, nullable=False)
    message_type = Column(String(30), default=MessageType.TEXT)
    
    # AI Processing Info
    openai_prompt_used = Column(Text, nullable=True)
    openai_response_raw = Column(Text, nullable=True)
    privacy_settings_applied = Column(JSON, nullable=True)
    user_memories_used = Column(JSON, nullable=True)
    
    # Message Metadata
    tokens_used = Column(Integer, default=0)
    response_time_ms = Column(Integer, nullable=True)
    
    # Delivery Status
    delivery_status = Column(String(20), default=DeliveryStatus.PENDING, index=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    conversation = relationship("MJConversation", back_populates="messages")
    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="sent_mj_messages")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="received_mj_messages")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(message_type.in_(['text', 'status_update', 'check_in', 'question', 'response']), name='check_message_type'),
        CheckConstraint(delivery_status.in_(['pending', 'delivered', 'read', 'failed']), name='check_delivery_status'),
        CheckConstraint('from_user_id != to_user_id', name='check_different_message_users'),
    )

# =====================================================
# 6. PENDING MESSAGES MODEL
# =====================================================

class PendingMessageStatus(str, enum.Enum):
    QUEUED = "queued"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"

class PendingMessage(Base):
    __tablename__ = "pending_messages"
    
    id = Column(BIGINT, primary_key=True, index=True)
    message_id = Column(BIGINT, ForeignKey("mj_messages.id", ondelete="CASCADE"), nullable=False)
    recipient_user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Queue Status
    status = Column(String(20), default=PendingMessageStatus.QUEUED, index=True)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    
    # Timing
    queued_at = Column(DateTime(timezone=True), server_default=func.now())
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), default=func.now() + func.make_interval(days=7))
    next_attempt_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Error Handling
    last_error = Column(Text, nullable=True)
    
    # Relationships
    message = relationship("MJMessage", back_populates="pending_delivery")
    recipient = relationship("User", back_populates="pending_messages")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(status.in_(['queued', 'delivered', 'failed', 'expired']), name='check_pending_status'),
    )

# =====================================================
# 7. SCHEDULED CHECKINS MODEL
# =====================================================

class FrequencyType(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

class CheckinType(str, enum.Enum):
    GENERAL = "general"
    MOOD = "mood"
    HEALTH = "health"
    WORK = "work"
    CUSTOM = "custom"

class ScheduledCheckin(Base):
    __tablename__ = "scheduled_checkins"
    
    id = Column(BIGINT, primary_key=True, index=True)
    
    # Participants
    user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Schedule Configuration
    checkin_name = Column(String(100), nullable=False)
    frequency_type = Column(String(20), nullable=False)
    frequency_value = Column(Integer, default=1)
    time_of_day = Column(TIME, nullable=True)
    timezone = Column(String(50), default="UTC")
    
    # Check-in Content
    checkin_message = Column(String(500), default="How are you doing?")
    checkin_type = Column(String(30), default=CheckinType.GENERAL)
    
    # Status & Execution
    is_active = Column(Boolean, default=True, index=True)
    next_checkin_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_checkin_at = Column(DateTime(timezone=True), nullable=True)
    total_checkins_sent = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="scheduled_checkins")
    target_user = relationship("User", foreign_keys=[target_user_id], back_populates="received_checkins")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(frequency_type.in_(['daily', 'weekly', 'monthly', 'custom']), name='check_frequency_type'),
        CheckConstraint(checkin_type.in_(['general', 'mood', 'health', 'work', 'custom']), name='check_checkin_type'),
        CheckConstraint('user_id != target_user_id', name='check_no_self_checkin'),
    )

# =====================================================
# 8. USER LOCATIONS MODEL
# =====================================================

class LocationSource(str, enum.Enum):
    GPS = "gps"
    NETWORK = "network"
    MANUAL = "manual"

class UserLocation(Base):
    __tablename__ = "user_locations"
    
    id = Column(BIGINT, primary_key=True, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # Location Data
    latitude = Column(DECIMAL(10, 8), nullable=False)
    longitude = Column(DECIMAL(11, 8), nullable=False)
    accuracy_meters = Column(Integer, nullable=True)
    
    # Location Context
    location_source = Column(String(30), default=LocationSource.GPS)
    is_current_location = Column(Boolean, default=True)
    
    # Privacy
    is_visible_on_map = Column(Boolean, default=True, index=True)
    visibility_radius_km = Column(Integer, nullable=True)  # NULL = visible globally
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), default=func.now() + func.make_interval(hours=12), index=True)
    
    # Relationships
    user = relationship("User", back_populates="location")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(location_source.in_(['gps', 'network', 'manual']), name='check_location_source'),
    )

# =====================================================
# UPDATE EXISTING USER MODEL TO ADD RELATIONSHIPS
# =====================================================

# NOTE: Add these relationships to your existing User model in src/models/database/user.py

"""
Add these relationships to your existing User class:

# MJ Network Relationships
mj_registry = relationship("MJRegistry", back_populates="user", uselist=False, cascade="all, delete-orphan")
location = relationship("UserLocation", back_populates="user", uselist=False, cascade="all, delete-orphan")

# Relationship Management
user_relationships = relationship("Relationship", foreign_keys="Relationship.user_id", back_populates="user", cascade="all, delete-orphan")
friend_relationships = relationship("Relationship", foreign_keys="Relationship.friend_user_id", back_populates="friend")

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
"""

# =====================================================
# ADD MISSING BACK RELATIONSHIPS
# =====================================================

# Add these to existing models:

# In Relationship model:
# mj_conversations = relationship("MJConversation", back_populates="relationship")

# In MJMessage model:
# pending_delivery = relationship("PendingMessage", back_populates="message", uselist=False)