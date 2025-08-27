# src/api/v1/mj_network.py - COMPLETE API ENDPOINTS - FIXED IMPORTS

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, asc, text  # ← FIXED: Added missing imports
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from ...config.database import get_db_session
from ...core.dependencies import get_authenticated_user
from ...models.database.user import User
from ...database.repositories.mj_network import MJNetworkRepository
from ...services.mj_network.mj_communication import MJCommunicationService
from ...services.mj_network.friend_management import FriendManagementService
from ...config.database import AsyncSessionLocal

router = APIRouter()

# =====================================================
# PYDANTIC SCHEMAS FOR API
# =====================================================

class LocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_meters: Optional[int] = None
    is_visible_on_map: bool = True

class FriendRequestCreate(BaseModel):
    to_user_id: int
    request_message: Optional[str] = None
    suggested_relationship_type: str = "friend"
    discovery_method: str = "manual"

class FriendRequestResponse(BaseModel):
    request_id: int
    accept: bool
    response_message: Optional[str] = None
    relationship_type: Optional[str] = "friend"

class MJTalkRequest(BaseModel):
    target_user_id: int
    message_purpose: str  # "Ask how they're doing", "Check on their health", etc.
    conversation_topic: Optional[str] = None

class ScheduledCheckinCreate(BaseModel):
    target_user_id: int
    checkin_name: str
    frequency_type: str = Field(..., pattern="^(daily|weekly|monthly|custom)$")
    frequency_value: int = Field(1, ge=1)
    time_of_day: Optional[str] = None  # HH:MM format
    checkin_message: str = "How are you doing?"
    checkin_type: str = "general"

class StatusUpdateRequest(BaseModel):
    status_message: str
    target_users: Optional[List[int]] = None  # If None, sends to all friends

async def _queue_offline_message_safe(message_id: int, recipient_user_id: int):
    """Background task to queue offline messages safely"""
    async with AsyncSessionLocal() as session:
        svc = MJCommunicationService(session)
        await svc.queue_offline_message(message_id, recipient_user_id)

# =====================================================
# 1. MJ REGISTRY & STATUS ENDPOINTS
# =====================================================

@router.post("/registry/initialize")
async def initialize_mj_registry(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """🌐 Initialize MJ registry for current user"""
    
    network_repo = MJNetworkRepository(db)
    
    # Check if MJ registry already exists
    existing_registry = await network_repo.mj_registry.get_by_user_id(current_user.id)
    if existing_registry:
        return {
            "message": "MJ registry already exists", 
            "mj_registry": {
                "id": existing_registry.id,
                "user_id": existing_registry.user_id,
                "mj_instance_id": existing_registry.mj_instance_id,
                "status": existing_registry.status,
                "location_enabled": existing_registry.location_enabled,
                "total_conversations": existing_registry.total_conversations,
                "total_messages_sent": existing_registry.total_messages_sent,
                "total_messages_received": existing_registry.total_messages_received,
            }
        }
    
    # Create MJ registry
    registry_data = {
        "user_id": current_user.id,
        "mj_instance_id": current_user.mj_instance_id or f"MJ-{current_user.username.upper()}-{current_user.id}",
        "status": "online",
        "capabilities": {"chat": True, "location": False, "voice": False}
    }
    
    mj_registry = await network_repo.mj_registry.create(registry_data)
    
    return {
        "message": "MJ registry initialized successfully",
        "mj_registry": {
            "id": mj_registry.id,
            "user_id": mj_registry.user_id,
            "mj_instance_id": mj_registry.mj_instance_id,
            "status": mj_registry.status,
            "location_enabled": mj_registry.location_enabled,
            "total_conversations": mj_registry.total_conversations,
            "total_messages_sent": mj_registry.total_messages_sent,
            "total_messages_received": mj_registry.total_messages_received,
        }
    }

@router.get("/registry/status")
async def get_mj_status(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """📊 Get current MJ status and comprehensive network statistics"""
    
    network_repo = MJNetworkRepository(db)
    network_data = await network_repo.get_complete_user_network_data(current_user.id)
    
    mj = network_data["mj_registry"]
    return {
        "mj_registry": (None if not mj else {
            "id": mj.id,
            "user_id": mj.user_id,
            "mj_instance_id": mj.mj_instance_id,
            "status": mj.status,
            "last_seen": mj.last_seen,
            "location_enabled": mj.location_enabled,
            "total_conversations": mj.total_conversations,
            "total_messages_sent": mj.total_messages_sent,
            "total_messages_received": mj.total_messages_received,
        }),
        "friends_count": len(network_data["friends"]),
        "pending_requests": len(network_data["pending_friend_requests"]),
        "active_conversations": len(network_data["conversations"]),
        "pending_messages": len(network_data["pending_messages"]),
        "has_location": network_data["location"] is not None,
        "scheduled_checkins": len(network_data["scheduled_checkins"])
    }

@router.put("/registry/status/{new_status}")
async def update_mj_status(
    new_status: str,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """🔄 Update MJ online status"""
    
    valid_statuses = ["online", "offline", "away", "busy"]
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )
    
    network_repo = MJNetworkRepository(db)
    success = await network_repo.mj_registry.update_status(current_user.id, new_status)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MJ registry not found"
        )
    
    return {"message": f"MJ status updated to {new_status}"}

# =====================================================
# 2. LOCATION & MAP DISCOVERY ENDPOINTS
# =====================================================

@router.put("/location")
async def update_location(
    location_data: LocationUpdate,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """📍 Update user location for map discovery"""
    
    network_repo = MJNetworkRepository(db)
    
    # Update location in user_locations table
    location = await network_repo.locations.update_user_location(
        user_id=current_user.id,
        latitude=location_data.latitude,
        longitude=location_data.longitude,
        accuracy_meters=location_data.accuracy_meters,
        is_visible_on_map=location_data.is_visible_on_map
    )
    
    # Update MJ registry with location
    await network_repo.mj_registry.update_location(
        user_id=current_user.id,
        latitude=location_data.latitude,
        longitude=location_data.longitude
    )
    
    # Enable location in MJ registry
    mj_registry = await network_repo.mj_registry.get_by_user_id(current_user.id)
    if mj_registry and not mj_registry.location_enabled:
        capabilities = (mj_registry.capabilities or {}).copy()
        capabilities["location"] = True
        
        await network_repo.mj_registry.update(mj_registry.id, {
            "location_enabled": True,
            "capabilities": capabilities
        })
    
    return {
        "message": "Location updated successfully",
        "location": {
            "latitude": float(location.latitude),
            "longitude": float(location.longitude),
            "is_visible_on_map": location.is_visible_on_map
        }
    }

@router.get("/discover/nearby")
async def discover_nearby_mjs(
    radius_km: float = 50.0,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """🔍 Discover nearby MJ users on the map"""
    
    network_repo = MJNetworkRepository(db)
    
    # Get user's current location - FIXED: Added missing import
    user_location_result = await db.execute(
        select(network_repo.locations.model).where(network_repo.locations.model.user_id == current_user.id)
    )
    user_location_obj = user_location_result.scalar_one_or_none()
    
    if not user_location_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enable location sharing first"
        )
    
    # Get nearby locations
    nearby_locations = await network_repo.locations.get_nearby_locations(
        latitude=float(user_location_obj.latitude),
        longitude=float(user_location_obj.longitude),
        radius_km=radius_km,
        exclude_user_id=current_user.id
    )
    
    # Format response with distance calculations
    import math
    
    def calculate_distance(lat1, lon1, lat2, lon2):
        R = 6371  # Earth's radius in km
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    nearby_users = []
    for location in nearby_locations:
        distance = calculate_distance(
            float(user_location_obj.latitude), float(user_location_obj.longitude),
            float(location.latitude), float(location.longitude)
        )
        nearby_users.append({
            "user_id": location.user.id,
            "username": location.user.username,
            "mj_instance_id": location.user.mj_instance_id,
            "latitude": float(location.latitude),
            "longitude": float(location.longitude),
            "distance_km": round(distance, 2)
        })
    
    return {
        "nearby_users": nearby_users,
        "count": len(nearby_users),
        "search_radius_km": radius_km
    }

@router.get("/discover/map")
async def get_map_users(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """🗺️ Get all users visible on the global map"""
    
    network_repo = MJNetworkRepository(db)
    visible_locations = await network_repo.locations.get_visible_locations(
        exclude_user_id=current_user.id
    )
    
    map_users = []
    for location in visible_locations:
        map_users.append({
            "user_id": location.user.id,
            "username": location.user.username,
            "mj_instance_id": location.user.mj_instance_id,
            "latitude": float(location.latitude),
            "longitude": float(location.longitude),
        })
    
    return {
        "map_users": map_users,
        "count": len(map_users)
    }

# =====================================================
# 3. FRIEND MANAGEMENT ENDPOINTS
# =====================================================

@router.post("/friends/request")
async def send_friend_request(
    request_data: FriendRequestCreate,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """👥 Send friend request to another user"""
    
    if request_data.to_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send friend request to yourself"
        )
    
    friend_service = FriendManagementService(db)
    
    try:
        friend_request = await friend_service.send_friend_request(
            from_user_id=current_user.id,
            to_user_id=request_data.to_user_id,
            request_message=request_data.request_message,
            suggested_relationship_type=request_data.suggested_relationship_type,
            discovery_method=request_data.discovery_method
        )
        
        return {
            "message": "Friend request sent successfully",
            "request_id": friend_request.id,
            "expires_at": friend_request.expires_at
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/friends/requests/pending")
async def get_pending_friend_requests(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """📋 Get pending friend requests for current user"""
    
    network_repo = MJNetworkRepository(db)
    pending_requests = await network_repo.friend_requests.get_pending_requests_for_user(current_user.id)
    
    return {
        "pending_requests": [
            {
                "id": fr.id,
                "from_user_id": fr.from_user_id,
                "from_username": fr.from_user.username if fr.from_user else None,
                "to_user_id": fr.to_user_id,
                "request_message": fr.request_message,
                "status": fr.status,
                "expires_at": fr.expires_at,
                "created_at": fr.created_at,
            }
            for fr in pending_requests
        ],
        "count": len(pending_requests)
    }

@router.post("/friends/requests/respond")
async def respond_to_friend_request(
    response_data: FriendRequestResponse,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """✅ Accept or reject friend request"""
    
    friend_service = FriendManagementService(db)
    
    try:
        if response_data.accept:
            result = await friend_service.accept_friend_request(
                request_id=response_data.request_id,
                accepting_user_id=current_user.id,
                relationship_type=response_data.relationship_type,
                response_message=response_data.response_message
            )
            
            return {
                "message": "Friend request accepted",
                "relationship_created": True,
                "relationship_id": result["relationship"].id
            }
        else:
            await friend_service.reject_friend_request(
                request_id=response_data.request_id,
                rejecting_user_id=current_user.id,
                response_message=response_data.response_message
            )
            
            return {
                "message": "Friend request rejected",
                "relationship_created": False
            }
            
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/friends")
async def get_friends(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """👫 Get user's friends list"""
    
    network_repo = MJNetworkRepository(db)
    friends = await network_repo.relationships.get_user_friends(current_user.id)
    
    friends_list = []
    for friend in friends:
        friends_list.append({
            "id": friend.id,
            "friend_user_id": friend.friend_user_id,
            "friend_username": friend.friend.username,
            "friend_mj_instance_id": friend.friend.mj_instance_id,
            "relationship_type": friend.relationship_type,
            "status": friend.status,
            "trust_level": float(friend.trust_level),
            "last_interaction": friend.last_interaction,
            "can_respond_when_offline": friend.can_respond_when_offline
        })
    
    return {
        "friends": friends_list,
        "count": len(friends_list)
    }

# =====================================================
# 4. MJ-TO-MJ COMMUNICATION - THE CORE FEATURE! 🌐
# =====================================================

@router.post("/mj-talk")
async def initiate_mj_conversation(
    talk_request: MJTalkRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """🤖 THE MAIN EVENT: Initiate MJ-to-MJ conversation!"""
    
    if talk_request.target_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot talk to your own MJ"
        )
    
    communication_service = MJCommunicationService(db)
    
    try:
        result = await communication_service.initiate_mj_conversation(
            from_user_id=current_user.id,
            to_user_id=talk_request.target_user_id,
            message_purpose=talk_request.message_purpose,
            conversation_topic=talk_request.conversation_topic
        )
        
        # Queue background task for offline message delivery if needed
        if not result["target_user_online"]:
            background_tasks.add_task(
                _queue_offline_message_safe,
                result["message"].id,
                talk_request.target_user_id
            )
        
        return {
            "message": "MJ conversation initiated successfully!",
            "conversation_id": result["conversation"].id,
            "message_id": result["message"].id,
            "target_user_online": result["target_user_online"],
            "response_content": result["response_content"],
            "tokens_used": result["tokens_used"]
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/conversations")
async def get_mj_conversations(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """💬 Get user's MJ conversations"""
    
    network_repo = MJNetworkRepository(db)
    conversations = await network_repo.conversations.get_user_conversations(current_user.id)
    
    conversations_list = []
    for conv in conversations:
        other_user = conv.user_b if conv.user_a_id == current_user.id else conv.user_a
        
        conversations_list.append({
            "id": conv.id,
            "user_a_id": conv.user_a_id,
            "user_b_id": conv.user_b_id,
            "user_a_username": conv.user_a.username,
            "user_b_username": conv.user_b.username,
            "conversation_topic": conv.conversation_topic,
            "status": conv.status,
            "last_message_at": conv.last_message_at,
            "message_count": conv.message_count
        })
    
    return {
        "conversations": conversations_list,
        "count": len(conversations_list)
    }

@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: int,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """📜 Get messages for a conversation"""
    
    network_repo = MJNetworkRepository(db)
    
    # Verify user is part of this conversation
    conversation = await network_repo.conversations.get_by_id(conversation_id)
    if not conversation or (conversation.user_a_id != current_user.id and conversation.user_b_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied"
        )
    
    messages = await network_repo.messages.get_conversation_messages(
        conversation_id=conversation_id,
        limit=limit,
        offset=offset
    )
    
    messages_list = []
    for message in messages:
        messages_list.append({
            "id": message.id,
            "from_user_id": message.from_user_id,
            "to_user_id": message.to_user_id,
            "from_username": message.from_user.username,
            "to_username": message.to_user.username,
            "message_content": message.message_content,
            "message_type": message.message_type,
            "delivery_status": message.delivery_status,
            "created_at": message.created_at,
            "tokens_used": message.tokens_used
        })
    
    return {
        "messages": messages_list,
        "count": len(messages_list),
        "conversation_id": conversation_id
    }

@router.post("/status-update")
async def send_status_update(
    status_data: StatusUpdateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """📢 Send status update to friends"""
    
    communication_service = MJCommunicationService(db)
    
    try:
        result = await communication_service.send_status_update(
            from_user_id=current_user.id,
            status_message=status_data.status_message,
            target_users=status_data.target_users
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send status update: {str(e)}"
        )

# =====================================================
# 5. SCHEDULED CHECKINS & AUTOMATION
# =====================================================

@router.post("/checkins")
async def create_scheduled_checkin(
    checkin_data: ScheduledCheckinCreate,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """📅 Create scheduled check-in"""
    
    if checkin_data.target_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create check-in with yourself"
        )
    
    from datetime import datetime, time, timedelta
    
    # Calculate next check-in time
    now = datetime.utcnow()
    if checkin_data.frequency_type == "daily":
        next_checkin = now + timedelta(days=1)
    elif checkin_data.frequency_type == "weekly":
        next_checkin = now + timedelta(weeks=1)
    elif checkin_data.frequency_type == "monthly":
        next_checkin = now + timedelta(days=30)
    else:  # custom
        next_checkin = now + timedelta(days=checkin_data.frequency_value)
    
    # Parse time_of_day if provided
    if checkin_data.time_of_day:
        try:
            hour, minute = map(int, checkin_data.time_of_day.split(':'))
            next_checkin = next_checkin.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid time format. Use HH:MM"
            )
    
    network_repo = MJNetworkRepository(db)
    
    checkin_create_data = {
        "user_id": current_user.id,
        "target_user_id": checkin_data.target_user_id,
        "checkin_name": checkin_data.checkin_name,
        "frequency_type": checkin_data.frequency_type,
        "frequency_value": checkin_data.frequency_value,
        "time_of_day": time(hour, minute) if checkin_data.time_of_day else None,
        "checkin_message": checkin_data.checkin_message,
        "checkin_type": checkin_data.checkin_type,
        "next_checkin_at": next_checkin
    }
    
    checkin = await network_repo.checkins.create(checkin_create_data)
    
    return {
        "message": "Scheduled check-in created successfully",
        "checkin_id": checkin.id,
        "next_checkin_at": checkin.next_checkin_at
    }

@router.get("/checkins")
async def get_scheduled_checkins(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """📋 Get user's scheduled check-ins"""
    
    network_repo = MJNetworkRepository(db)
    
    # Get check-ins created by user
    user_checkins = await network_repo.checkins.get_user_checkins(current_user.id)
    
    # Get check-ins targeting user
    received_checkins = await network_repo.checkins.get_received_checkins(current_user.id)
    
    return {
        "created_checkins": [
            {
                "id": c.id,
                "target_user_id": c.target_user_id,
                "target_username": c.target_user.username,
                "checkin_name": c.checkin_name,
                "frequency_type": c.frequency_type,
                "checkin_message": c.checkin_message,
                "is_active": c.is_active,
                "next_checkin_at": c.next_checkin_at
            } for c in user_checkins
        ],
        "received_checkins": [
            {
                "id": c.id,
                "from_user_id": c.user_id,
                "from_username": c.user.username,
                "checkin_name": c.checkin_name,
                "frequency_type": c.frequency_type,
                "checkin_message": c.checkin_message,
                "is_active": c.is_active,
                "next_checkin_at": c.next_checkin_at
            } for c in received_checkins
        ],
        "created_count": len(user_checkins),
        "received_count": len(received_checkins)
    }

# =====================================================
# 6. SEARCH & UTILITIES
# =====================================================

@router.get("/search/users")
async def search_users(
    query: str,
    limit: int = 10,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """🔍 Search for users by username or MJ instance ID"""
    
    if len(query.strip()) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query must be at least 2 characters"
        )
    
    # FIXED: Added missing imports
    from ...models.database.user import User as UserModel
    
    # Search by username or MJ instance ID
    result = await db.execute(
        select(UserModel).where(
            and_(
                or_(
                    UserModel.username.ilike(f"%{query}%"),
                    UserModel.mj_instance_id.ilike(f"%{query}%")
                ),
                UserModel.id != current_user.id  # Exclude current user
            )
        ).limit(limit)
    )
    
    users = result.scalars().all()
    
    # Check friendship status for each user
    network_repo = MJNetworkRepository(db)
    search_results = []
    
    for user in users:
        # Check if already friends
        relationship = await network_repo.relationships.get_relationship(current_user.id, user.id)
        is_friend = relationship is not None
        
        # Check if friend request exists
        existing_request = await network_repo.friend_requests.get_existing_request(current_user.id, user.id)
        has_pending_request = existing_request is not None
        
        search_results.append({
            "user_id": user.id,
            "username": user.username,
            "mj_instance_id": user.mj_instance_id,
            "is_friend": is_friend,
            "has_pending_request": has_pending_request
        })
    
    return {
        "search_results": search_results,
        "count": len(search_results),
        "query": query
    }

@router.get("/network/stats")
async def get_comprehensive_network_stats(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """📊 Get comprehensive network statistics"""
    
    network_repo = MJNetworkRepository(db)
    network_data = await network_repo.get_complete_user_network_data(current_user.id)
    
    # Calculate stats
    total_friends = len(network_data["friends"])
    active_conversations = len([c for c in network_data["conversations"] if c.status == "active"])
    total_messages = sum(c.message_count for c in network_data["conversations"])
    
    # Get online friends count
    online_friends = 0
    for friend in network_data["friends"]:
        friend_registry = await network_repo.mj_registry.get_by_user_id(friend.friend_user_id)
        if friend_registry and friend_registry.status == "online":
            online_friends += 1
    
    return {
        "user_stats": {
            "total_friends": total_friends,
            "online_friends": online_friends,
            "active_conversations": active_conversations,
            "total_mj_messages": total_messages,
            "pending_messages": len(network_data["pending_messages"]),
            "scheduled_checkins": len(network_data["scheduled_checkins"]),
            "location_enabled": network_data["location"] is not None
        },
        "mj_registry": network_data["mj_registry"],
        "recent_activity": {
            "last_conversation": network_data["conversations"][0].last_message_at if network_data["conversations"] else None,
            "last_friend_added": max([f.created_at for f in network_data["friends"]], default=None),
            "last_location_update": network_data["location"].created_at if network_data["location"] else None
        }
    }