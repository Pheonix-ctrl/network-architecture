# src/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from typing import Dict, Any
from pydantic import BaseModel

from ...config.database import get_db_session
from ...config.settings import Settings
from ...core.security import create_access_token, create_refresh_token, hash_password, verify_password
from ...core.dependencies import get_authenticated_user
from ...database.repositories.user import UserRepository
from ...models.schemas.user import UserCreate, UserResponse, UserUpdate
from ...models.database.user import User
from ...services.memory.redis_client import RedisClient
from ...utils.validators import validate_password_strength

router = APIRouter()
settings = Settings()
security = HTTPBearer()

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/register", response_model=Dict[str, Any])
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """Register a new user and create their MJ instance"""
    
    # Validate password strength
    if not validate_password_strength(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password does not meet security requirements"
        )
    
    user_repo = UserRepository(db)
    
    # Check if user already exists
    existing_user = await user_repo.get_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    existing_username = await user_repo.get_by_username(user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Hash password
    hashed_password = hash_password(user_data.password)
    
    # Create user
    user = await user_repo.create({
        "username": user_data.username,
        "email": user_data.email,
        "password_hash": hashed_password,
        "mj_instance_id": f"MJ-{user_data.username.upper()}-{hash(user_data.email) % 10000:04d}",
        "preferred_mode": "mj"  # Use string that matches enum value
    })
    
    # Generate tokens
    access_token = create_access_token({"sub": str(user.id), "username": user.username})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "mj_instance_id": user.mj_instance_id,
            "preferred_mode": user.preferred_mode.value if user.preferred_mode else "mj",
            "is_online": user.is_online,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        },
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.post("/login", response_model=Dict[str, Any])
async def login_user(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Login user and return tokens"""
    
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(login_data.email)
    
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Note: removed is_active check since it doesn't exist in our database schema
    
    # Update last active
    await user_repo.update_last_active(user.id)
    
    # Generate tokens
    access_token = create_access_token({"sub": str(user.id), "username": user.username})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "mj_instance_id": user.mj_instance_id,
            "preferred_mode": user.preferred_mode.value if user.preferred_mode else "mj",
            "is_online": user.is_online,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        },
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.post("/refresh", response_model=Dict[str, Any])
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Refresh access token using refresh token"""
    
    try:
        # Verify refresh token
        from ...core.security import verify_token
        payload = verify_token(refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Get user
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(int(user_id))
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Generate new access token
        access_token = create_access_token({"sub": str(user.id), "username": user.username})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_authenticated_user)
):
    """Get current user information"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "mj_instance_id": current_user.mj_instance_id,
        "preferred_mode": current_user.preferred_mode.value if current_user.preferred_mode else "mj",
        "is_online": current_user.is_online,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at
    }

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update current user information"""
    
    user_repo = UserRepository(db)
    
    # Update user
    update_data = user_update.dict(exclude_unset=True)
    updated_user = await user_repo.update(current_user.id, update_data)
    
    return UserResponse.from_orm(updated_user)

@router.post("/logout")
async def logout_user(
    current_user: User = Depends(get_authenticated_user)
):
    """Logout user (invalidate tokens in Redis if needed)"""
    
    redis = RedisClient()
    await redis.connect()
    
    # In a full implementation, you'd maintain a token blacklist in Redis
    # For now, just confirm logout
    
    await redis.disconnect()
    
    return {"message": "Successfully logged out"}