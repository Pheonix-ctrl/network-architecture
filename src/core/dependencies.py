
# src/core/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import jwt
from .security import verify_token
from ..config.database import get_db_session
from ..models.database.user import User
from ..database.repositories.user import UserRepository

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db_session)
) -> Optional[User]:
    """Get current authenticated user or None if not authenticated"""
    if not credentials:
        return None
    
    try:
        payload = verify_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(int(user_id))
        return user
    except:
        return None

async def get_authenticated_user(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """Require authenticated user"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return current_user
