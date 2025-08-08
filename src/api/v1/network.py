# src/api/v1/network.py - UPDATED FOR NETWORK-ONLY
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
    """Start MJ network discovery service (network-only)"""
    
    discovery_service = MJDiscoveryService()
    await discovery_service.initialize(
        user_id=current_user.id,
        user_name=current_user.username
    )
    await discovery_service.start_discovery()
    
    return {
        "message": "MJ network discovery started",
        "mj_id": discovery_service.local_mj_id,
        "user": current_user.username,
        "discovery_methods": ["network", "redis"],  # No Bluetooth
        "discovery_port": 8888
    }

@router.get("/discovery/stop")
async def stop_mj_discovery(
    current_user: User = Depends(get_authenticated_user)
):
    """Stop MJ network discovery service"""
    
    discovery_service = MJDiscoveryService()
    await discovery_service.stop_discovery()
    
    return {"message": "MJ network discovery stopped"}

@router.get("/discovery/nearby", response_model=List[Dict[str, Any]])
async def discover_nearby_mjs(
    method: str = "network",  # network or redis
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Discover nearby MJ instances (network-only)"""
    
    if method not in ["network", "redis"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid discovery method. Use 'network' or 'redis'"
        )
    
    discovery_service = MJDiscoveryService()
    await discovery_service.initialize(
        user_id=current_user.id,
        user_name=current_user.username
    )
    
    nearby_mjs = await discovery_service.discover_nearby_mjs(method=method)
    
    return {
        "discovered_mjs": nearby_mjs,
        "discovery_method": method,
        "count": len(nearby_mjs),
        "local_mj_id": discovery_service.local_mj_id
    }

@router.get("/discovery/status")
async def get_discovery_status(
    current_user: User = Depends(get_authenticated_user)
):
    """Get MJ network discovery status"""
    
    discovery_service = MJDiscoveryService()
    
    return {
        "discovery_active": discovery_service.discovery_active,
        "local_mj_id": discovery_service.local_mj_id,
        "available_methods": ["network", "redis"],
        "discovery_port": 8888,
        "note": "Bluetooth discovery disabled for simplified setup"
    }

# Test endpoints for network discovery
@router.post("/test/ping")
async def test_mj_ping(
    target_ip: str,
    current_user: User = Depends(get_authenticated_user)
):
    """Test connectivity to another MJ instance"""
    
    discovery_service = MJDiscoveryService()
    await discovery_service.initialize(
        user_id=current_user.id,
        user_name=current_user.username
    )
    
    # Test connection to target MJ
    result = await discovery_service._check_mj_at_ip(target_ip)
    
    if result:
        return {
            "success": True,
            "message": f"Successfully connected to MJ at {target_ip}",
            "mj_info": result
        }
    else:
        return {
            "success": False,
            "message": f"No MJ instance found at {target_ip}",
            "mj_info": None
        }

@router.get("/test/network-info")
async def get_network_info(
    current_user: User = Depends(get_authenticated_user)
):
    """Get local network information for debugging"""
    
    discovery_service = MJDiscoveryService()
    networks = discovery_service._get_local_networks()
    local_ip = discovery_service._get_local_ip()
    
    return {
        "local_ip": local_ip,
        "local_networks": networks,
        "discovery_port": 8888,
        "scan_ranges": [f"{net['network_base']}.1-254" for net in networks]
    }

# All other network endpoints remain the same...
# (connection requests, responses, MJ-to-MJ talk, etc.)
