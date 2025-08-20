# src/database/repositories/mj_network.py
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
import math

from ..base import BaseRepository
from ...models.database.mj_network import (
    MJRegistry, Relationship, FriendRequest, MJConversation, 
    MJMessage, PendingMessage, ScheduledCheckin, UserLocation,
    MJStatus, RelationshipStatus, FriendRequestStatus, ConversationStatus,
    MessageType, DeliveryStatus, PendingMessageStatus
)

# =====================================================
# 1. MJ REGISTRY REPOSITORY
# =====================================================

class MJRegistryRepository(BaseRepository[MJRegistry]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, MJRegistry)
    
    async def get_by_user_id(self, user_id: int) -> Optional[MJRegistry]:
        """Get MJ registry by user ID"""
        result = await self.db.execute(
            select(MJRegistry).where(MJRegistry.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_mj_instance_id(self, mj_instance_id: str) -> Optional[MJRegistry]:
        """Get MJ registry by MJ instance ID"""
        result = await self.db.execute(
            select(MJRegistry).where(MJRegistry.mj_instance_id == mj_instance_id)
        )
        return result.scalar_one_or_none()
    
    async def update_status(self, user_id: int, status: MJStatus) -> bool:
        """Update MJ online status"""
        result = await self.db.execute(
            update(MJRegistry)
            .where(MJRegistry.user_id == user_id)
            .values(status=status, last_seen=func.now())
        )
        await self.db.commit()
        return result.rowcount > 0

# =====================================================
# 7. USER LOCATIONS REPOSITORY
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
        """Update or create user location"""
        
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
                    expires_at=func.now() + func.make_interval(hours=12)
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
        """Get locations within radius"""
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
# 8. SCHEDULED CHECKINS REPOSITORY
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
# COMBINED MJ NETWORK SERVICE
# =====================================================

class MJNetworkRepository:
    """Combined repository for all MJ Network operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.mj_registry = MJRegistryRepository(db)
        self.relationships = RelationshipRepository(db)
        self.friend_requests = FriendRequestRepository(db)
        self.conversations = MJConversationRepository(db)
        self.messages = MJMessageRepository(db)
        self.pending_messages = PendingMessageRepository(db)
        self.locations = UserLocationRepository(db)
        self.checkins = ScheduledCheckinRepository(db)
    
    async def get_complete_user_network_data(self, user_id: int) -> Dict[str, Any]:
        """Get complete network data for a user"""
        
        # Get MJ registry
        mj_registry = await self.mj_registry.get_by_user_id(user_id)
        
        # Get relationships
        friends = await self.relationships.get_user_friends(user_id)
        
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
            "friends": friends,
            "pending_friend_requests": pending_requests,
            "sent_friend_requests": sent_requests,
            "conversations": conversations,
            "pending_messages": pending_messages,
            "location": location,
            "scheduled_checkins": scheduled_checkins,
            "received_checkins": received_checkins
        } > 0
    
    async def update_location(
        self, 
        user_id: int, 
        latitude: float, 
        longitude: float,
        accuracy_meters: Optional[int] = None
    ) -> bool:
        """Update MJ location"""
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
        """Get all online MJ instances"""
        result = await self.db.execute(
            select(MJRegistry)
            .where(MJRegistry.status == MJStatus.ONLINE)
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
        """Get MJs within specified radius"""
        # Using Haversine formula for distance calculation
        query = select(MJRegistry).where(
            and_(
                MJRegistry.latitude.is_not(None),
                MJRegistry.longitude.is_not(None),
                MJRegistry.location_enabled == True,
                MJRegistry.status.in_([MJStatus.ONLINE, MJStatus.AWAY])
            )
        )
        
        if exclude_user_id:
            query = query.where(MJRegistry.user_id != exclude_user_id)
        
        result = await self.db.execute(query)
        all_mjs = result.scalars().all()
        
        # Filter by distance
        nearby_mjs = []
        for mj in all_mjs:
            distance = self._calculate_distance(latitude, longitude, float(mj.latitude), float(mj.longitude))
            if distance <= radius_km:
                nearby_mjs.append(mj)
        
        return nearby_mjs
    
    async def increment_stats(self, user_id: int, conversations: int = 0, messages_sent: int = 0, messages_received: int = 0):
        """Increment MJ statistics"""
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
# 2. RELATIONSHIPS REPOSITORY
# =====================================================

class RelationshipRepository(BaseRepository[Relationship]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Relationship)
    
    async def get_relationship(self, user_id: int, friend_user_id: int) -> Optional[Relationship]:
        """Get relationship between two users"""
        result = await self.db.execute(
            select(Relationship).where(
                and_(
                    Relationship.user_id == user_id,
                    Relationship.friend_user_id == friend_user_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_mutual_relationship(self, user_a_id: int, user_b_id: int) -> Optional[Relationship]:
        """Get relationship from either direction"""
        result = await self.db.execute(
            select(Relationship).where(
                or_(
                    and_(Relationship.user_id == user_a_id, Relationship.friend_user_id == user_b_id),
                    and_(Relationship.user_id == user_b_id, Relationship.friend_user_id == user_a_id)
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_user_friends(self, user_id: int, status: RelationshipStatus = RelationshipStatus.ACTIVE) -> List[Relationship]:
        """Get all friends for a user"""
        result = await self.db.execute(
            select(Relationship)
            .where(
                and_(
                    Relationship.user_id == user_id,
                    Relationship.status == status
                )
            )
            .options(selectinload(Relationship.friend))
            .order_by(desc(Relationship.last_interaction))
        )
        return result.scalars().all()
    
    async def create_mutual_relationship(
        self, 
        user_a_id: int, 
        user_b_id: int, 
        relationship_type: str,
        privacy_settings: Dict[str, Any]
    ) -> Tuple[Relationship, Relationship]:
        """Create mutual relationship between two users"""
        
        # Create relationship from A to B
        rel_a_to_b = Relationship(
            user_id=user_a_id,
            friend_user_id=user_b_id,
            relationship_type=relationship_type,
            privacy_settings=privacy_settings
        )
        
        # Create relationship from B to A
        rel_b_to_a = Relationship(
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
            update(Relationship)
            .where(
                and_(
                    Relationship.user_id == user_id,
                    Relationship.friend_user_id == friend_user_id
                )
            )
            .values(privacy_settings=privacy_settings, updated_at=func.now())
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def can_mj_respond_when_offline(self, user_id: int, requesting_user_id: int) -> bool:
        """Check if user allows MJ to respond when they're offline"""
        result = await self.db.execute(
            select(Relationship.can_respond_when_offline)
            .where(
                and_(
                    Relationship.user_id == user_id,
                    Relationship.friend_user_id == requesting_user_id,
                    Relationship.status == RelationshipStatus.ACTIVE
                )
            )
        )
        setting = result.scalar_one_or_none()
        return setting if setting is not None else False

# =====================================================
# 3. FRIEND REQUESTS REPOSITORY
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
                    FriendRequest.status == FriendRequestStatus.PENDING,
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
                    FriendRequest.status == FriendRequestStatus.PENDING
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
                status=FriendRequestStatus.ACCEPTED,
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
                status=FriendRequestStatus.REJECTED,
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
                    FriendRequest.status == FriendRequestStatus.PENDING,
                    FriendRequest.expires_at < func.now()
                )
            )
            .values(status=FriendRequestStatus.EXPIRED)
        )
        await self.db.commit()
        return result.rowcount

# =====================================================
# 4. MJ CONVERSATIONS REPOSITORY
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
                    MJConversation.status == ConversationStatus.ACTIVE
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

# =====================================================
# 5. MJ MESSAGES REPOSITORY
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
        message_type: MessageType = MessageType.TEXT,
        openai_prompt_used: Optional[str] = None,
        openai_response_raw: Optional[str] = None,
        privacy_settings_applied: Optional[Dict] = None,
        user_memories_used: Optional[Dict] = None,
        tokens_used: int = 0
    ) -> MJMessage:
        """Create new MJ message"""
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
                delivery_status=DeliveryStatus.DELIVERED,
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
                delivery_status=DeliveryStatus.READ,
                read_at=func.now()
            )
        )
        await self.db.commit()
        return result.rowcount > 0

# =====================================================
# 6. PENDING MESSAGES REPOSITORY
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
                    PendingMessage.status == PendingMessageStatus.QUEUED
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
                status=PendingMessageStatus.DELIVERED,
                delivered_at=func.now()
            )
        )
        await self.db.commit()
        return result.rowcount