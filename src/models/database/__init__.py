# Import all models so SQLAlchemy can find them
from .user import User
from .conversation import Conversation  
from .memory import Memory
from .mj_network import *
from .relationship import Relationship

# Make sure all models are available
__all__ = [
    "User", "Conversation", "Memory", "MJRegistry", "Relationship",
    "FriendRequest", "MJConversation", "MJMessage", "PendingMessage", 
    "ScheduledCheckin", "UserLocation"
]