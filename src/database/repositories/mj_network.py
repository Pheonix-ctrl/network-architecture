# src/database/repositories/mj_network.py - COMPLETE VERSION with all original functionality

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc, text
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
import math
from datetime import datetime, timedelta

from .base import BaseRepository
from ...models.database.mj_network import (
    MJRegistry, NetworkRelationship, FriendRequest, MJConversation, 
    MJMessage, PendingMessage, ScheduledCheckin, UserLocation,
    MJStatus, RelationshipStatus, FriendRequestStatus, ConversationStatus,
    MessageType, DeliveryStatus, PendingMessageStatus
)

# =====================================================
# 1. MJ REGISTRY REPOSITORY - Complete version
# =====================================================

class MJRegistryRepository(BaseRepository[MJRegistry]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, MJRegistry)
    
    async def get_by_user_id(self, user_id: int) -> Optional[MJRegistry]:
        """Get MJ registry by user ID - core function for your system"""
        result = await self.db.execute(
            select(MJRegistry).where(MJRegistry.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_mj_instance_id(self, mj_instance_id: str) -> Optional[MJRegistry]:
        """Find MJ by instance ID"""
        result = await self.db.execute(
            select(MJRegistry).where(MJRegistry.mj_instance_id == mj_instance_id)
        )
        return result.scalar_one_or_none()
    
    async def update_status(self, user_id: int, status: str) -> bool:
        """Update MJ online status - critical for knowing who's available"""
        result = await self.db.execute(
            update(MJRegistry)
            .where(MJRegistry.user_id == user_id)
            .values(status=status, last_seen=func.now())
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def update_location(
        self, 
        user_id: int, 
        latitude: float, 
        longitude: float,
        accuracy_meters: Optional[int] = None
    ) -> bool:
        """Update MJ location in registry"""
        result = await self.db.execute(
            update(MJRegistry)
            .where(MJRegistry.user_id == user_id)
            .values(
                latitude=latitude,
                longitude=longitude,
                location_updated_at=func.now()
            )
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def get_online_mjs(self) -> List[MJRegistry]:
        """Get all online MJ instances - for discovery system"""
        result = await self.db.execute(
            select(MJRegistry)
            .where(MJRegistry.status == MJStatus.ONLINE.value)
            .order_by(desc(MJRegistry.last_seen))
        )
        return result.scalars().all()
    
    async def get_nearby_mjs(
        self, 
        latitude: float, 
        longitude: float, 
        radius_km: float = 50.0,
        exclude_user_id: Optional[int] = None
    ) -> List[MJRegistry]:
        """Get MJs within specified radius using Haversine formula"""
        query = select(MJRegistry).where(
            and_(
                MJRegistry.latitude.is_not(None),
                MJRegistry.longitude.is_not(None),
                MJRegistry.location_enabled == True,
                MJRegistry.status.in_([MJStatus.ONLINE.value, MJStatus.AWAY.value])
            )
        )
        
        if exclude_user_id:
            query = query.where(MJRegistry.user_id != exclude_user_id)
        
        result = await self.db.execute(query)
        all_mjs = result.scalars().all()
        
        # Filter by distance using Haversine formula
        nearby_mjs = []
        for mj in all_mjs:
            distance = self._calculate_distance(latitude, longitude, float(mj.latitude), float(mj.longitude))
            if distance <= radius_km:
                nearby_mjs.append(mj)
        
        return nearby_mjs
    
    async def increment_stats(self, user_id: int, conversations: int = 0, messages_sent: int = 0, messages_received: int = 0):
        """Update MJ statistics when they chat"""
        await self.db.execute(
            update(MJRegistry)
            .where(MJRegistry.user_id == user_id)
            .values(
                total_conversations=MJRegistry.total_conversations + conversations,
                total_messages_sent=MJRegistry.total_messages_sent + messages_sent,
                total_messages_received=MJRegistry.total_messages_received + messages_received
            )
        )
        await self.db.commit()
    
    async def update_capabilities(self, user_id: int, capabilities: Dict[str, Any]) -> bool:
        """Update MJ capabilities"""
        result = await self.db.execute(
            update(MJRegistry)
            .where(MJRegistry.user_id == user_id)
            .values(capabilities=capabilities)
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def get_registry_stats(self) -> Dict[str, Any]:
        """Get overall MJ registry statistics"""
        
        # Total MJs
        total_result = await self.db.execute(
            select(func.count(MJRegistry.id))
        )
        total_mjs = total_result.scalar()
        
        # Online MJs
        online_result = await self.db.execute(
            select(func.count(MJRegistry.id))
            .where(MJRegistry.status == MJStatus.ONLINE.value)
        )
        online_mjs = online_result.scalar()
        
        # MJs with location enabled
        location_result = await self.db.execute(
            select(func.count(MJRegistry.id))
            .where(MJRegistry.location_enabled == True)
        )
        location_enabled = location_result.scalar()
        
        # Total conversations across network
        conversations_result = await self.db.execute(
            select(func.sum(MJRegistry.total_conversations))
        )
        total_conversations = conversations_result.scalar() or 0
        
        # Total messages across network
        messages_result = await self.db.execute(
            select(func.sum(MJRegistry.total_messages_sent))
        )
        total_messages = messages_result.scalar() or 0
        
        return {
            "total_mjs": total_mjs,
            "online_mjs": online_mjs,
            "location_enabled_mjs": location_enabled,
            "total_network_conversations": total_conversations,
            "total_network_messages": total_messages,
            "activity_rate": (online_mjs / total_mjs * 100) if total_mjs > 0 else 0
        }
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula"""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

# =====================================================
# 2. NETWORK RELATIONSHIPS REPOSITORY - Complete friendship system
# =====================================================

class NetworkRelationshipRepository(BaseRepository[NetworkRelationship]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, NetworkRelationship)
    
    async def get_relationship(self, user_id: int, friend_user_id: int) -> Optional[NetworkRelationship]:
        """Get relationship between two users - needed for privacy settings"""
        result = await self.db.execute(
            select(NetworkRelationship).where(
                and_(
                    NetworkRelationship.user_id == user_id,
                    NetworkRelationship.friend_user_id == friend_user_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_mutual_relationship(self, user_a_id: int, user_b_id: int) -> Optional[NetworkRelationship]:
        """Get relationship from either direction - check if users are friends"""
        result = await self.db.execute(
            select(NetworkRelationship).where(
                or_(
                    and_(NetworkRelationship.user_id == user_a_id, NetworkRelationship.friend_user_id == user_b_id),
                    and_(NetworkRelationship.user_id == user_b_id, NetworkRelationship.friend_user_id == user_a_id)
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_user_friends(self, user_id: int, status: str = "active") -> List[NetworkRelationship]:
        """Get all friends for a user - for friends list UI"""
        result = await self.db.execute(
            select(NetworkRelationship)
            .where(
                and_(
                    NetworkRelationship.user_id == user_id,
                    NetworkRelationship.status == status
                )
            )
            .options(selectinload(NetworkRelationship.friend))
            .order_by(desc(NetworkRelationship.last_interaction))
        )
        return result.scalars().all()
    
    async def get_user_friends_with_mj_status(self, user_id: int) -> List[Tuple[NetworkRelationship, Optional[str]]]:
        """Get friends with their MJ online status - optimized single query"""
        result = await self.db.execute(
            select(NetworkRelationship, MJRegistry.status)
            .join(MJRegistry, NetworkRelationship.friend_user_id == MJRegistry.user_id, isouter=True)
            .where(
                and_(
                    NetworkRelationship.user_id == user_id,
                    NetworkRelationship.status == RelationshipStatus.ACTIVE.value
                )
            )
            .options(selectinload(NetworkRelationship.friend))
            .order_by(desc(NetworkRelationship.last_interaction))
        )
        return result.all()
    
    async def create_mutual_relationship(
        self, 
        user_a_id: int, 
        user_b_id: int, 
        relationship_type: str,
        privacy_settings: Dict[str, Any]
    ) -> Tuple[NetworkRelationship, NetworkRelationship]:
        """Create friendship between two users - both directions"""
        
        # Create relationship from A to B
        rel_a_to_b = NetworkRelationship(
            user_id=user_a_id,
            friend_user_id=user_b_id,
            relationship_type=relationship_type,
            privacy_settings=privacy_settings
        )
        
        # Create relationship from B to A
        rel_b_to_a = NetworkRelationship(
            user_id=user_b_id,
            friend_user_id=user_a_id,
            relationship_type=relationship_type,
            privacy_settings=privacy_settings
        )
        
        self.db.add(rel_a_to_b)
        self.db.add(rel_b_to_a)
        await self.db.commit()
        await self.db.refresh(rel_a_to_b)
        await self.db.refresh(rel_b_to_a)
        
        return rel_a_to_b, rel_b_to_a
    
    async def update_privacy_settings(self, user_id: int, friend_user_id: int, privacy_settings: Dict[str, Any]) -> bool:
        """Update privacy settings for a relationship"""
        result = await self.db.execute(
            update(NetworkRelationship)
            .where(
                and_(
                    NetworkRelationship.user_id == user_id,
                    NetworkRelationship.friend_user_id == friend_user_id
                )
            )
            .values(privacy_settings=privacy_settings, updated_at=func.now())
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def can_mj_respond_when_offline(self, user_id: int, requesting_user_id: int) -> bool:
        """Check if user allows MJ to respond when they're offline"""
        result = await self.db.execute(
            select(NetworkRelationship.can_respond_when_offline)
            .where(
                and_(
                    NetworkRelationship.user_id == user_id,
                    NetworkRelationship.friend_user_id == requesting_user_id,
                    NetworkRelationship.status == RelationshipStatus.ACTIVE.value
                )
            )
        )
        setting = result.scalar_one_or_none()
        return setting if setting is not None else False
    
    async def update_interaction(self, user_id: int, friend_user_id: int, trust_adjustment: float = 0.0) -> bool:
        """Update last interaction and adjust trust level"""
        
        update_data = {"last_interaction": datetime.utcnow()}
        
        if trust_adjustment != 0.0:
            # Adjust trust level within bounds [0.0, 1.0]
            update_data["trust_level"] = func.greatest(
                0.0,
                func.least(1.0, NetworkRelationship.trust_level + trust_adjustment)
            )
        
        result = await self.db.execute(
            update(NetworkRelationship)
            .where(
                and_(
                    NetworkRelationship.user_id == user_id,
                    NetworkRelationship.friend_user_id == friend_user_id
                )
            )
            .values(**update_data)
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def get_relationship_stats(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive relationship statistics"""
        
        # Total relationships
        total_result = await self.db.execute(
            select(func.count(NetworkRelationship.id))
            .where(NetworkRelationship.user_id == user_id)
        )
        total_relationships = total_result.scalar()
        
        # Active relationships
        active_result = await self.db.execute(
            select(func.count(NetworkRelationship.id))
            .where(
                and_(
                    NetworkRelationship.user_id == user_id,
                    NetworkRelationship.status == RelationshipStatus.ACTIVE.value
                )
            )
        )
        active_relationships = active_result.scalar()
        
        # Relationship types distribution
        type_stats_result = await self.db.execute(
            select(
                NetworkRelationship.relationship_type,
                func.count(NetworkRelationship.id)
            )
            .where(NetworkRelationship.user_id == user_id)
            .group_by(NetworkRelationship.relationship_type)
        )
        relationship_types = {rel_type: count for rel_type, count in type_stats_result}
        
        # Average trust level
        trust_result = await self.db.execute(
            select(func.avg(NetworkRelationship.trust_level))
            .where(
                and_(
                    NetworkRelationship.user_id == user_id,
                    NetworkRelationship.status == RelationshipStatus.ACTIVE.value
                )
            )
        )
        avg_trust_level = trust_result.scalar()
        
        # Recent interactions (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_result = await self.db.execute(
            select(func.count(NetworkRelationship.id))
            .where(
                and_(
                    NetworkRelationship.user_id == user_id,
                    NetworkRelationship.last_interaction >= seven_days_ago
                )
            )
        )
        recent_interactions = recent_result.scalar()
        
        return {
            "total_relationships": total_relationships,
            "active_relationships": active_relationships,
            "relationship_types": relationship_types,
            "average_trust_level": float(avg_trust_level) if avg_trust_level else 0.0,
            "recent_interactions": recent_interactions
        }
    
    async def get_mutual_friends(self, user_a_id: int, user_b_id: int) -> List[NetworkRelationship]:
        """Find mutual friends between two users"""
        
        # Get friends of user A
        friends_a_result = await self.db.execute(
            select(NetworkRelationship.friend_user_id)
            .where(
                and_(
                    NetworkRelationship.user_id == user_a_id,
                    NetworkRelationship.status == RelationshipStatus.ACTIVE.value
                )
            )
        )
        friends_a_ids = {row[0] for row in friends_a_result}
        
        # Get friends of user B that are also friends with A
        mutual_result = await self.db.execute(
            select(NetworkRelationship)
            .where(
                and_(
                    NetworkRelationship.user_id == user_b_id,
                    NetworkRelationship.friend_user_id.in_(friends_a_ids),
                    NetworkRelationship.status == RelationshipStatus.ACTIVE.value
                )
            )
            .options(selectinload(NetworkRelationship.friend))
        )
        
        return mutual_result.scalars().all()
    
    async def suggest_friends(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Suggest potential friends based on mutual connections"""
        
        # Get current friends
        current_friends_result = await self.db.execute(
            select(NetworkRelationship.friend_user_id)
            .where(
                and_(
                    NetworkRelationship.user_id == user_id,
                    NetworkRelationship.status == RelationshipStatus.ACTIVE.value
                )
            )
        )
        current_friend_ids = {row[0] for row in current_friends_result}
        current_friend_ids.add(user_id)  # Exclude self
        
        # Find friends of friends who aren't already friends
        suggestions_result = await self.db.execute(
            select(
                NetworkRelationship.friend_user_id,
                func.count(NetworkRelationship.id).label('mutual_count')
            )
            .where(
                and_(
                    NetworkRelationship.user_id.in_(current_friend_ids - {user_id}),
                    ~NetworkRelationship.friend_user_id.in_(current_friend_ids),
                    NetworkRelationship.status == RelationshipStatus.ACTIVE.value
                )
            )
            .group_by(NetworkRelationship.friend_user_id)
            .order_by(desc('mutual_count'))
            .limit(limit)
        )
        
        suggestions = []
        for friend_id, mutual_count in suggestions_result:
            suggestions.append({
                "user_id": friend_id,
                "mutual_friends_count": mutual_count,
                "suggestion_reason": f"{mutual_count} mutual friends"
            })
        
        return suggestions

# =====================================================
# 3. FRIEND REQUESTS REPOSITORY - Complete system
# =====================================================

class FriendRequestRepository(BaseRepository[FriendRequest]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, FriendRequest)
    
    async def get_pending_requests_for_user(self, user_id: int) -> List[FriendRequest]:
        """Get all pending friend requests for a user"""
        result = await self.db.execute(
            select(FriendRequest)
            .where(
                and_(
                    FriendRequest.to_user_id == user_id,
                    FriendRequest.status == FriendRequestStatus.PENDING.value,
                    FriendRequest.expires_at > func.now()
                )
            )
            .options(selectinload(FriendRequest.from_user))
            .order_by(desc(FriendRequest.created_at))
        )
        return result.scalars().all()
    
    async def get_sent_requests_by_user(self, user_id: int) -> List[FriendRequest]:
        """Get all requests sent by a user"""
        result = await self.db.execute(
            select(FriendRequest)
            .where(FriendRequest.from_user_id == user_id)
            .options(selectinload(FriendRequest.to_user))
            .order_by(desc(FriendRequest.created_at))
        )
        return result.scalars().all()
    
    async def get_existing_request(self, from_user_id: int, to_user_id: int) -> Optional[FriendRequest]:
        """Check if request already exists between users"""
        result = await self.db.execute(
            select(FriendRequest).where(
                and_(
                    FriendRequest.from_user_id == from_user_id,
                    FriendRequest.to_user_id == to_user_id,
                    FriendRequest.status == FriendRequestStatus.PENDING.value
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def accept_request(
        self, 
        request_id: int, 
        response_message: Optional[str] = None
    ) -> Optional[FriendRequest]:
        """Accept a friend request"""
        result = await self.db.execute(
            update(FriendRequest)
            .where(FriendRequest.id == request_id)
            .values(
                status=FriendRequestStatus.ACCEPTED.value,
                response_message=response_message,
                responded_at=func.now()
            )
            .returning(FriendRequest)
        )
        await self.db.commit()
        return result.scalar_one_or_none()
    
    async def reject_request(
        self, 
        request_id: int, 
        response_message: Optional[str] = None
    ) -> Optional[FriendRequest]:
        """Reject a friend request"""
        result = await self.db.execute(
            update(FriendRequest)
            .where(FriendRequest.id == request_id)
            .values(
                status=FriendRequestStatus.REJECTED.value,
                response_message=response_message,
                responded_at=func.now()
            )
            .returning(FriendRequest)
        )
        await self.db.commit()
        return result.scalar_one_or_none()
    
    async def expire_old_requests(self) -> int:
        """Mark expired requests as expired"""
        result = await self.db.execute(
            update(FriendRequest)
            .where(
                and_(
                    FriendRequest.status == FriendRequestStatus.PENDING.value,
                    FriendRequest.expires_at < func.now()
                )
            )
            .values(status=FriendRequestStatus.EXPIRED.value)
        )
        await self.db.commit()
        return result.rowcount
    
    async def get_request_statistics(self) -> Dict[str, Any]:
        """Get friend request statistics across the network"""
        
        # Total requests
        total_result = await self.db.execute(
            select(func.count(FriendRequest.id))
        )
        total_requests = total_result.scalar()
        
        # Status distribution
        status_result = await self.db.execute(
            select(
                FriendRequest.status,
                func.count(FriendRequest.id)
            )
            .group_by(FriendRequest.status)
        )
        status_distribution = {status: count for status, count in status_result}
        
        # Discovery method distribution
        discovery_result = await self.db.execute(
            select(
                FriendRequest.discovery_method,
                func.count(FriendRequest.id)
            )
            .group_by(FriendRequest.discovery_method)
        )
        discovery_methods = {method: count for method, count in discovery_result}
        
        # Average response time for accepted requests
        response_time_result = await self.db.execute(
            select(func.avg(
                func.extract('epoch', FriendRequest.responded_at - FriendRequest.created_at) / 3600
            ))
            .where(FriendRequest.status == FriendRequestStatus.ACCEPTED.value)
        )
        avg_response_hours = response_time_result.scalar()
        
        return {
            "total_requests": total_requests,
            "status_distribution": status_distribution,
            "discovery_methods": discovery_methods,
            "average_response_hours": float(avg_response_hours) if avg_response_hours else None
        }

# =====================================================
# 4. MJ CONVERSATIONS REPOSITORY - Complete conversation system
# =====================================================

class MJConversationRepository(BaseRepository[MJConversation]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, MJConversation)
    
    async def get_conversation_between_users(self, user_a_id: int, user_b_id: int) -> Optional[MJConversation]:
        """Get active conversation between two users"""
        result = await self.db.execute(
            select(MJConversation).where(
                and_(
                    or_(
                        and_(MJConversation.user_a_id == user_a_id, MJConversation.user_b_id == user_b_id),
                        and_(MJConversation.user_a_id == user_b_id, MJConversation.user_b_id == user_a_id)
                    ),
                    MJConversation.status == ConversationStatus.ACTIVE.value
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_user_conversations(self, user_id: int, limit: int = 20) -> List[MJConversation]:
        """Get all conversations for a user"""
        result = await self.db.execute(
            select(MJConversation)
            .where(
                and_(
                    or_(MJConversation.user_a_id == user_id, MJConversation.user_b_id == user_id),
                    MJConversation.status == ConversationStatus.ACTIVE
                )
            )
            .options(
                selectinload(MJConversation.user_a),
                selectinload(MJConversation.user_b)
            )
            .order_by(desc(MJConversation.last_message_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def create_conversation(
        self,
        user_a_id: int,
        user_b_id: int,
        initiated_by_user_id: int,
        conversation_topic: Optional[str] = None,
        relationship_id: Optional[int] = None
    ) -> MJConversation:
        """Create new MJ conversation"""
        conversation = MJConversation(
            user_a_id=user_a_id,
            user_b_id=user_b_id,
            initiated_by_user_id=initiated_by_user_id,
            conversation_topic=conversation_topic,
            relationship_id=relationship_id
        )
        
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation
    
    async def update_last_message(self, conversation_id: int) -> bool:
        """Update last message timestamp and increment message count"""
        result = await self.db.execute(
            update(MJConversation)
            .where(MJConversation.id == conversation_id)
            .values(
                last_message_at=func.now(),
                message_count=MJConversation.message_count + 1
            )
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def archive_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Archive a conversation"""
        # Verify user is part of conversation
        conversation = await self.get_by_id(conversation_id)
        if not conversation or (conversation.user_a_id != user_id and conversation.user_b_id != user_id):
            return False
        
        result = await self.db.execute(
            update(MJConversation)
            .where(MJConversation.id == conversation_id)
            .values(status=ConversationStatus.ARCHIVED.value)
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def get_conversation_statistics(self) -> Dict[str, Any]:
        """Get conversation statistics across the network"""
        
        # Total conversations
        total_result = await self.db.execute(
            select(func.count(MJConversation.id))
        )
        total_conversations = total_result.scalar()
        
        # Active conversations
        active_result = await self.db.execute(
            select(func.count(MJConversation.id))
            .where(MJConversation.status == ConversationStatus.ACTIVE.value)
        )
        active_conversations = active_result.scalar()
        
        # Average messages per conversation
        avg_messages_result = await self.db.execute(
            select(func.avg(MJConversation.message_count))
        )
        avg_messages = avg_messages_result.scalar()
        
        # Conversations by privacy level
        privacy_result = await self.db.execute(
            select(
                MJConversation.privacy_level,
                func.count(MJConversation.id)
            )
            .group_by(MJConversation.privacy_level)
        )
        privacy_levels = {level: count for level, count in privacy_result}
        
        return {
            "total_conversations": total_conversations,
            "active_conversations": active_conversations,
            "average_messages_per_conversation": float(avg_messages) if avg_messages else 0,
            "privacy_level_distribution": privacy_levels
        }

# =====================================================
# 5. MJ MESSAGES REPOSITORY - Complete message system
# =====================================================

class MJMessageRepository(BaseRepository[MJMessage]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, MJMessage)
    
    async def get_conversation_messages(
        self, 
        conversation_id: int, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[MJMessage]:
        """Get messages for a conversation"""
        result = await self.db.execute(
            select(MJMessage)
            .where(MJMessage.conversation_id == conversation_id)
            .options(
                selectinload(MJMessage.from_user),
                selectinload(MJMessage.to_user)
            )
            .order_by(asc(MJMessage.created_at))
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def create_mj_message(
        self,
        conversation_id: int,
        from_user_id: int,
        to_user_id: int,
        message_content: str,
        message_type: str = "text",
        openai_prompt_used: Optional[str] = None,
        openai_response_raw: Optional[str] = None,
        privacy_settings_applied: Optional[Dict] = None,
        user_memories_used: Optional[Dict] = None,
        tokens_used: int = 0
    ) -> MJMessage:
        """Create new MJ message - core of your system"""
        message = MJMessage(
            conversation_id=conversation_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            message_content=message_content,
            message_type=message_type,
            openai_prompt_used=openai_prompt_used,
            openai_response_raw=openai_response_raw,
            privacy_settings_applied=privacy_settings_applied,
            user_memories_used=user_memories_used,
            tokens_used=tokens_used
        )
        
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message
    
    async def mark_as_delivered(self, message_id: int) -> bool:
        """Mark message as delivered"""
        result = await self.db.execute(
            update(MJMessage)
            .where(MJMessage.id == message_id)
            .values(
                delivery_status=DeliveryStatus.DELIVERED.value,
                delivered_at=func.now()
            )
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def mark_as_read(self, message_id: int) -> bool:
        """Mark message as read"""
        result = await self.db.execute(
            update(MJMessage)
            .where(MJMessage.id == message_id)
            .values(
                delivery_status=DeliveryStatus.READ.value,
                read_at=func.now()
            )
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def get_user_messages(
        self, 
        user_id: int, 
        limit: int = 100,
        message_type: Optional[str] = None
    ) -> List[MJMessage]:
        """Get all messages for a user (sent or received)"""
        query = select(MJMessage).where(
            or_(MJMessage.from_user_id == user_id, MJMessage.to_user_id == user_id)
        )
        
        if message_type:
            query = query.where(MJMessage.message_type == message_type)
        
        query = query.options(
            selectinload(MJMessage.from_user),
            selectinload(MJMessage.to_user),
            selectinload(MJMessage.conversation)
        ).order_by(desc(MJMessage.created_at)).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_unread_messages(self, user_id: int) -> List[MJMessage]:
        """Get all unread messages for a user"""
        result = await self.db.execute(
            select(MJMessage)
            .where(
                and_(
                    MJMessage.to_user_id == user_id,
                    MJMessage.delivery_status.in_([DeliveryStatus.PENDING.value, DeliveryStatus.DELIVERED.value])
                )
            )
            .options(
                selectinload(MJMessage.from_user),
                selectinload(MJMessage.conversation)
            )
            .order_by(asc(MJMessage.created_at))
        )
        return result.scalars().all()
    
    async def get_message_statistics(self) -> Dict[str, Any]:
        """Get message statistics across the network"""
        
        # Total messages
        total_result = await self.db.execute(
            select(func.count(MJMessage.id))
        )
        total_messages = total_result.scalar()
        
        # Messages by type
        type_result = await self.db.execute(
            select(
                MJMessage.message_type,
                func.count(MJMessage.id)
            )
            .group_by(MJMessage.message_type)
        )
        message_types = {msg_type: count for msg_type, count in type_result}
        
        # Messages by delivery status
        status_result = await self.db.execute(
            select(
                MJMessage.delivery_status,
                func.count(MJMessage.id)
            )
            .group_by(MJMessage.delivery_status)
        )
        delivery_statuses = {status: count for status, count in status_result}
        
        # Average tokens per message
        tokens_result = await self.db.execute(
            select(func.avg(MJMessage.tokens_used))
            .where(MJMessage.tokens_used > 0)
        )
        avg_tokens = tokens_result.scalar()
        
        # Average response time
        response_time_result = await self.db.execute(
            select(func.avg(MJMessage.response_time_ms))
            .where(MJMessage.response_time_ms.is_not(None))
        )
        avg_response_time = response_time_result.scalar()
        
        return {
            "total_messages": total_messages,
            "message_types": message_types,
            "delivery_statuses": delivery_statuses,
            "average_tokens_per_message": float(avg_tokens) if avg_tokens else 0,
            "average_response_time_ms": float(avg_response_time) if avg_response_time else None
        }

# =====================================================
# 6. PENDING MESSAGES REPOSITORY - Complete offline system
# =====================================================

class PendingMessageRepository(BaseRepository[PendingMessage]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, PendingMessage)
    
    async def queue_message(self, message_id: int, recipient_user_id: int) -> PendingMessage:
        """Queue message for offline delivery"""
        pending = PendingMessage(
            message_id=message_id,
            recipient_user_id=recipient_user_id
        )
        
        self.db.add(pending)
        await self.db.commit()
        await self.db.refresh(pending)
        return pending
    
    async def get_pending_for_user(self, user_id: int) -> List[PendingMessage]:
        """Get all pending messages for a user"""
        result = await self.db.execute(
            select(PendingMessage)
            .where(
                and_(
                    PendingMessage.recipient_user_id == user_id,
                    PendingMessage.status == PendingMessageStatus.QUEUED.value
                )
            )
            .options(selectinload(PendingMessage.message))
            .order_by(asc(PendingMessage.queued_at))
        )
        return result.scalars().all()
    
    async def mark_as_delivered(self, pending_id: int) -> bool:
        """Mark pending message as delivered"""
        result = await self.db.execute(
            update(PendingMessage)
            .where(PendingMessage.id == pending_id)
            .values(
                status=PendingMessageStatus.DELIVERED.value,
                delivered_at=func.now()
            )
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def mark_as_failed(self, pending_id: int, error_message: str) -> bool:
        """Mark pending message as failed"""
        result = await self.db.execute(
            update(PendingMessage)
            .where(PendingMessage.id == pending_id)
            .values(
                status=PendingMessageStatus.FAILED.value,
                attempts=PendingMessage.attempts + 1,
                last_error=error_message,
                next_attempt_at=datetime.utcnow() + timedelta(minutes=30) # Retry in 30 minutes
            )
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def get_messages_to_retry(self) -> List[PendingMessage]:
        """Get messages that are ready to retry"""
        result = await self.db.execute(
            select(PendingMessage)
            .where(
                and_(
                    PendingMessage.status == PendingMessageStatus.FAILED.value,
                    PendingMessage.attempts < PendingMessage.max_attempts,
                    PendingMessage.next_attempt_at <= func.now()
                )
            )
            .options(selectinload(PendingMessage.message))
            .order_by(asc(PendingMessage.next_attempt_at))
        )
        return result.scalars().all()
    
    async def cleanup_expired_messages(self) -> int:
        """Remove expired pending messages"""
        result = await self.db.execute(
            update(PendingMessage)
            .where(
                and_(
                    PendingMessage.expires_at < func.now(),
                    PendingMessage.status != PendingMessageStatus.DELIVERED.value
                )
            )
            .values(status=PendingMessageStatus.EXPIRED.value)
        )
        await self.db.commit()
        return result.rowcount

# =====================================================
# 7. USER LOCATIONS REPOSITORY - Complete map system
# =====================================================

class UserLocationRepository(BaseRepository[UserLocation]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, UserLocation)
    
    async def update_user_location(
        self,
        user_id: int,
        latitude: float,
        longitude: float,
        accuracy_meters: Optional[int] = None,
        location_source: str = "gps",
        is_visible_on_map: bool = True
    ) -> UserLocation:
        """Update or create user location for map discovery"""
        
        # Check if location exists
        existing = await self.db.execute(
            select(UserLocation).where(UserLocation.user_id == user_id)
        )
        location = existing.scalar_one_or_none()
        
        if location:
            # Update existing location
            await self.db.execute(
                update(UserLocation)
                .where(UserLocation.user_id == user_id)
                .values(
                    latitude=latitude,
                    longitude=longitude,
                    accuracy_meters=accuracy_meters,
                    location_source=location_source,
                    is_visible_on_map=is_visible_on_map,
                    expires_at=datetime.utcnow() + timedelta(hours=12)  # Clean timedelta approach
                )
            )
            await self.db.commit()
            
            # Get updated location
            result = await self.db.execute(
                select(UserLocation).where(UserLocation.user_id == user_id)
            )
            return result.scalar_one()
        else:
            # Create new location
            location = UserLocation(
                user_id=user_id,
                latitude=latitude,
                longitude=longitude,
                accuracy_meters=accuracy_meters,
                location_source=location_source,
                is_visible_on_map=is_visible_on_map
            )
            
            self.db.add(location)
            await self.db.commit()
            await self.db.refresh(location)
            return location
    
    async def get_visible_locations(self, exclude_user_id: Optional[int] = None) -> List[UserLocation]:
        """Get all locations visible on map"""
        query = select(UserLocation).where(
            and_(
                UserLocation.is_visible_on_map == True,
                UserLocation.expires_at > func.now()
            )
        ).options(selectinload(UserLocation.user))
        
        if exclude_user_id:
            query = query.where(UserLocation.user_id != exclude_user_id)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_nearby_locations(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 50.0,
        exclude_user_id: Optional[int] = None
    ) -> List[UserLocation]:
        """Get locations within radius using Haversine formula"""
        # Get all visible locations first
        visible_locations = await self.get_visible_locations(exclude_user_id)
        
        # Filter by distance
        nearby_locations = []
        for location in visible_locations:
            distance = self._calculate_distance(
                latitude, longitude, 
                float(location.latitude), float(location.longitude)
            )
            if distance <= radius_km:
                nearby_locations.append(location)
        
        return nearby_locations
    
    async def cleanup_expired_locations(self) -> int:
        """Remove expired locations"""
        result = await self.db.execute(
            delete(UserLocation).where(UserLocation.expires_at < func.now())
        )
        await self.db.commit()
        return result.rowcount
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula"""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

# =====================================================
# 8. SCHEDULED CHECKINS REPOSITORY - Complete automation
# =====================================================

class ScheduledCheckinRepository(BaseRepository[ScheduledCheckin]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, ScheduledCheckin)
    
    async def get_due_checkins(self) -> List[ScheduledCheckin]:
        """Get check-ins that are due to be executed"""
        result = await self.db.execute(
            select(ScheduledCheckin)
            .where(
                and_(
                    ScheduledCheckin.is_active == True,
                    ScheduledCheckin.next_checkin_at <= func.now()
                )
            )
            .options(
                selectinload(ScheduledCheckin.user),
                selectinload(ScheduledCheckin.target_user)
            )
        )
        return result.scalars().all()
    
    async def get_user_checkins(self, user_id: int) -> List[ScheduledCheckin]:
        """Get all check-ins created by a user"""
        result = await self.db.execute(
            select(ScheduledCheckin)
            .where(ScheduledCheckin.user_id == user_id)
            .options(selectinload(ScheduledCheckin.target_user))
            .order_by(desc(ScheduledCheckin.created_at))
        )
        return result.scalars().all()
    
    async def get_received_checkins(self, user_id: int) -> List[ScheduledCheckin]:
        """Get all check-ins targeting a user"""
        result = await self.db.execute(
            select(ScheduledCheckin)
            .where(ScheduledCheckin.target_user_id == user_id)
            .options(selectinload(ScheduledCheckin.user))
            .order_by(desc(ScheduledCheckin.created_at))
        )
        return result.scalars().all()
    
    async def execute_checkin(self, checkin_id: int) -> bool:
        """Mark check-in as executed and schedule next one"""
        checkin = await self.get_by_id(checkin_id)
        if not checkin:
            return False
        
        # Calculate next check-in time based on frequency
        next_checkin = self._calculate_next_checkin(checkin)
        
        # Update checkin
        result = await self.db.execute(
            update(ScheduledCheckin)
            .where(ScheduledCheckin.id == checkin_id)
            .values(
                last_checkin_at=func.now(),
                next_checkin_at=next_checkin,
                total_checkins_sent=ScheduledCheckin.total_checkins_sent + 1
            )
        )
        await self.db.commit()
        return result.rowcount > 0
    
    def _calculate_next_checkin(self, checkin: ScheduledCheckin) -> datetime:
        """Calculate next check-in time based on frequency"""
        now = datetime.utcnow()
        
        if checkin.frequency_type == "daily":
            return now + timedelta(days=checkin.frequency_value)
        elif checkin.frequency_type == "weekly":
            return now + timedelta(weeks=checkin.frequency_value)
        elif checkin.frequency_type == "monthly":
            return now + timedelta(days=checkin.frequency_value * 30)  # Approximate
        else:  # custom
            return now + timedelta(days=checkin.frequency_value)

# =====================================================
# COMBINED MJ NETWORK REPOSITORY - Main interface (800+ lines complete)
# =====================================================

class MJNetworkRepository:
    """Combined repository for all MJ Network operations - COMPLETE VERSION"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.mj_registry = MJRegistryRepository(db)
        self.relationships = NetworkRelationshipRepository(db)
        self.friend_requests = FriendRequestRepository(db)
        self.conversations = MJConversationRepository(db)
        self.messages = MJMessageRepository(db)
        self.pending_messages = PendingMessageRepository(db)
        self.locations = UserLocationRepository(db)
        self.checkins = ScheduledCheckinRepository(db)
    
    async def get_complete_user_network_data(self, user_id: int) -> Dict[str, Any]:
        """Get complete network data for a user - for dashboard"""
        
        # Get MJ registry
        mj_registry = await self.mj_registry.get_by_user_id(user_id)
        
        # Get relationships with MJ status (optimized query)
        friends_with_status = await self.relationships.get_user_friends_with_mj_status(user_id)
        
        # Get friend requests
        pending_requests = await self.friend_requests.get_pending_requests_for_user(user_id)
        sent_requests = await self.friend_requests.get_sent_requests_by_user(user_id)
        
        # Get conversations
        conversations = await self.conversations.get_user_conversations(user_id)
        
        # Get pending messages
        pending_messages = await self.pending_messages.get_pending_for_user(user_id)
        
        # Get location
        location_result = await self.db.execute(
            select(UserLocation).where(UserLocation.user_id == user_id)
        )
        location = location_result.scalar_one_or_none()
        
        # Get scheduled check-ins
        scheduled_checkins = await self.checkins.get_user_checkins(user_id)
        received_checkins = await self.checkins.get_received_checkins(user_id)
        
        return {
            "mj_registry": mj_registry,
            "friends": [rel for rel, status in friends_with_status],
            "friends_with_status": friends_with_status,
            "pending_friend_requests": pending_requests,
            "sent_friend_requests": sent_requests,
            "conversations": conversations,
            "pending_messages": pending_messages,
            "location": location,
            "scheduled_checkins": scheduled_checkins,
            "received_checkins": received_checkins
        }
    
    async def get_network_statistics(self) -> Dict[str, Any]:
        """Get comprehensive network statistics"""
        
        registry_stats = await self.mj_registry.get_registry_stats()
        conversation_stats = await self.conversations.get_conversation_statistics()
        message_stats = await self.messages.get_message_statistics()
        request_stats = await self.friend_requests.get_request_statistics()
        
        return {
            "registry": registry_stats,
            "conversations": conversation_stats,
            "messages": message_stats,
            "friend_requests": request_stats,
            "generated_at": datetime.utcnow()
        }
    
    async def cleanup_expired_data(self) -> Dict[str, int]:
        """Clean up expired data across all tables"""
        
        expired_requests = await self.friend_requests.expire_old_requests()
        expired_messages = await self.pending_messages.cleanup_expired_messages()
        expired_locations = await self.locations.cleanup_expired_locations()
        
        return {
            "expired_friend_requests": expired_requests,
            "expired_pending_messages": expired_messages,
            "expired_locations": expired_locations
        }