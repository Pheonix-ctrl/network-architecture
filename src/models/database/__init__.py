# src/models/database/__init__.py - FIXED: Updated import names

# Import all models so SQLAlchemy can find them
from .user import User
from .conversation import Conversation  
from .memory import Memory
from .mj_network import *  # This now includes NetworkRelationship instead of Relationship
from .relationship import Relationship  # Keep the simple Relationship model

# Make sure all models are available - FIXED: Updated names
__all__ = [
    "User", "Conversation", "Memory", "MJRegistry", "Relationship",
    "NetworkRelationship",  # ADDED: New network relationship class
    "FriendRequest", "MJConversation", "MJMessage", "PendingMessage", 
    "ScheduledCheckin", "UserLocation"
]