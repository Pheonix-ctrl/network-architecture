# src/models/database/user.py - Fixed version
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, BigInteger, Enum
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
    # Use the exact enum name from your database
    preferred_mode = Column(Enum(PersonalityMode, name="personality_mode"), default=PersonalityMode.mj)
    is_online = Column(Boolean, default=False)
    last_active = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # TEMPORARILY REMOVED: Relationships that are causing the SQLAlchemy error
    # We'll add these back once we create the other model files
    # conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    # memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")  
    # relationships = relationship("Relationship", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"