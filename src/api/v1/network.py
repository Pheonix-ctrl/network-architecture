# src/api/v1/network.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional

from ...config.database import get_db_session
from ...core.dependencies import get_authenticated_user
from ...models.database.user import User
from ...models.schemas.network import (
    MJDiscoveryRequest, MJConnectionRequest, MJConnectionResponse, 
    MJTalkRequest, MJTalkResponse
)
from ...database.repositories.relationship import RelationshipRepository
from ...services.network.discovery import MJDiscoveryService
from ...services.network.context_filter import ContextFilter
from ...services.memory.redis_client import RedisClient

router = APIRouter()

@router.get("/discovery/start")
async def start_mj_discovery(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Start MJ network discovery service for current user"""
    
    discovery_service = MJDiscoveryService()
    await discovery_service.initialize(
        user_id=current_user.id,
        user_name=current_user.username
    )
    await discovery_service.start_discovery()
    
    return {
        "message": "MJ discovery started",
        "mj_id": discovery_service.local_mj_id,
        "user": current_user.username
    }

@router.get("/discovery/stop")
async def stop_mj_discovery(
    current_user: User = Depends(get_authenticated_user)
):
    """Stop MJ network discovery service"""
    
    discovery_service = MJDiscoveryService()
    await discovery_service.stop_discovery()
    
    return {"message": "MJ discovery stopped"}

@router.get("/discovery/nearby", response_model=List[Dict[str, Any]])
async def discover_nearby_mjs(
    method: str = "wifi",  # wifi, bluetooth, or network
    radius_km: float = 1.0,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Discover nearby MJ instances"""
    
    discovery_service = MJDiscoveryService()
    await discovery_service.initialize(
        user_id=current_user.id,
        user_name=current_user.username
    )
    
    nearby_mjs = await discovery_service.discover_nearby_mjs(
        method=method,
        radius_km=radius_km
    )
    
    return nearby_mjs

@router.post("/connection/request", response_model=Dict[str, Any])
async def request_mj_connection(
    connection_request: MJConnectionRequest,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Request connection to another MJ instance"""
    
    # Store connection request in Redis for the target MJ to see
    redis = RedisClient()
    await redis.connect()
    
    request_key = f"mj_connection_request:{connection_request.target_mj_id}"
    request_data = {
        "from_user_id": current_user.id,
        "from_mj_id": connection_request.requester_mj_id,
        "from_username": current_user.username,
        "relationship_type": connection_request.relationship_type,
        "message": connection_request.message,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "pending"
    }
    
    # Store request with 1 hour expiry
    await redis.redis.setex(request_key, 3600, json.dumps(request_data))
    await redis.disconnect()
    
    return {
        "message": "Connection request sent",
        "target_mj_id": connection_request.target_mj_id,
        "status": "pending"
    }

@router.get("/connection/requests", response_model=List[Dict[str, Any]])
async def get_connection_requests(
    current_user: User = Depends(get_authenticated_user)
):
    """Get pending connection requests for current user's MJ"""
    
    redis = RedisClient()
    await redis.connect()
    
    # Get requests for this MJ
    request_key = f"mj_connection_request:{current_user.mj_instance_id}"
    request_data = await redis.redis.get(request_key)
    
    requests = []
    if request_data:
        request = json.loads(request_data)
        if request.get("status") == "pending":
            requests.append(request)
    
    await redis.disconnect()
    return requests

@router.post("/connection/respond", response_model=Dict[str, Any])
async def respond_to_connection_request(
    requester_mj_id: str,
    response: MJConnectionResponse,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Respond to a connection request"""
    
    redis = RedisClient()
    await redis.connect()
    
    # Get the original request
    request_key = f"mj_connection_request:{current_user.mj_instance_id}"
    request_data = await redis.redis.get(request_key)
    
    if not request_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection request not found"
        )
    
    request = json.loads(request_data)
    
    if response.approved:
        # Create relationship in database
        relationship_repo = RelationshipRepository(db)
        
        # Create relationship for both users if approved
        await relationship_repo.create({
            "user_id": current_user.id,
            "contact_name": request["from_username"],
            "contact_mj_id": requester_mj_id,
            "relationship_type": response.relationship_type or request.get("relationship_type", "friend"),
            "share_level": response.share_level,
            "is_connected": True,
            "trust_level": 0.5
        })
        
        # Store response for requester to see
        response_key = f"mj_connection_response:{requester_mj_id}"
        response_data = {
            "approved": True,
            "relationship_type": response.relationship_type,
            "share_level": response.share_level,
            "message": response.message,
            "responder_mj_id": current_user.mj_instance_id,
            "responder_username": current_user.username,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await redis.redis.setex(response_key, 3600, json.dumps(response_data))
        
        # Remove original request
        await redis.redis.delete(request_key)
        
        message = "Connection approved and relationship created"
    else:
        # Store rejection response
        response_key = f"mj_connection_response:{requester_mj_id}"
        response_data = {
            "approved": False,
            "message": response.message or "Connection request declined",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await redis.redis.setex(response_key, 3600, json.dumps(response_data))
        await redis.redis.delete(request_key)
        
        message = "Connection request declined"
    
    await redis.disconnect()
    
    return {
        "message": message,
        "approved": response.approved,
        "requester_mj_id": requester_mj_id
    }

@router.get("/relationships", response_model=List[Dict[str, Any]])
async def get_mj_relationships(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all MJ network relationships for current user"""
    
    relationship_repo = RelationshipRepository(db)
    relationships = await relationship_repo.get_by_user(current_user.id)
    
    return [
        {
            "id": rel.id,
            "contact_name": rel.contact_name,
            "contact_mj_id": rel.contact_mj_id,
            "relationship_type": rel.relationship_type,
            "share_level": rel.share_level,
            "is_connected": rel.is_connected,
            "trust_level": rel.trust_level,
            "created_at": rel.created_at,
            "last_interaction": rel.last_interaction
        }
        for rel in relationships
    ]

@router.post("/talk", response_model=MJTalkResponse)
async def mj_to_mj_talk(
    talk_request: MJTalkRequest,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Initiate MJ-to-MJ communication"""
    
    try:
        # Get context filter service
        context_filter = ContextFilter(db)
        
        # Get user's current context (this would include recent activities, mood, etc.)
        user_context = await _get_user_context_for_sharing(current_user.id, db)
        
        # Filter context based on relationship
        filtered_data = await context_filter.filter_context_for_mj_talk(
            from_user_id=current_user.id,
            to_mj_id=talk_request.to_mj_id,
            content=talk_request.content,
            context_data=user_context
        )
        
        # Store filtered message for target MJ to retrieve
        redis = RedisClient()
        await redis.connect()
        
        message_key = f"mj_talk_message:{talk_request.to_mj_id}:{current_user.mj_instance_id}"
        message_data = {
            "from_mj_id": talk_request.from_mj_id,
            "from_username": current_user.username,
            "filtered_content": filtered_data["filtered_content"],
            "context": filtered_data["context"],
            "filter_level": filtered_data["filter_level"],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store with 24 hour expiry
        await redis.redis.setex(message_key, 86400, json.dumps(message_data))
        await redis.disconnect()
        
        return MJTalkResponse(
            success=True,
            response=f"Message sent to {talk_request.to_mj_id}",
            filtered_content=filtered_data["filtered_content"]
        )
        
    except Exception as e:
        return MJTalkResponse(
            success=False,
            error=f"Failed to send message: {str(e)}"
        )

@router.get("/messages", response_model=List[Dict[str, Any]])
async def get_mj_messages(
    current_user: User = Depends(get_authenticated_user)
):
    """Get messages from other MJs"""
    
    redis = RedisClient()
    await redis.connect()
    
    # Get all messages for this MJ
    pattern = f"mj_talk_message:{current_user.mj_instance_id}:*"
    keys = await redis.redis.keys(pattern)
    
    messages = []
    for key in keys:
        message_data = await redis.redis.get(key)
        if message_data:
            message = json.loads(message_data)
            messages.append(message)
    
    await redis.disconnect()
    
    # Sort by timestamp
    messages.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    return messages

@router.delete("/relationship/{relationship_id}")
async def delete_mj_relationship(
    relationship_id: int,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete/disconnect from an MJ relationship"""
    
    relationship_repo = RelationshipRepository(db)
    relationship = await relationship_repo.get_by_id_and_user(relationship_id, current_user.id)
    
    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found"
        )
    
    await relationship_repo.delete(relationship_id)
    
    return {"message": "MJ relationship disconnected successfully"}

async def _get_user_context_for_sharing(user_id: int, db: AsyncSession) -> Dict[str, Any]:
    """Get user context that can be shared with other MJs"""
    
    # This would gather various context about the user
    # For now, return basic context structure
    context = {
        "user_status": "online",
        "general_mood": "neutral",
        "recent_activities": [],
        "interests": [],
        "current_mode": "mj",
        "last_active": datetime.utcnow().isoformat()
    }
    
    # In a full implementation, this would:
    # 1. Get recent conversation sentiment
    # 2. Get user's current activities from calendar/apps
    # 3. Get interests from memory system
    # 4. Get current emotional state from recent messages
    # 5. Get work/social status
    
    return context