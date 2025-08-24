from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from .security import verify_token
from ..config.database import get_db_session
from ..models.database.user import User
from ..database.repositories.user import UserRepository

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db_session)
) -> Optional[User]:
    """Return the authenticated User or None if no/invalid token."""
    if not credentials:
        return None
    try:
        payload = verify_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            return None
        user_repo = UserRepository(db)
        return await user_repo.get_by_id(int(user_id))
    except Exception:
        # Invalid/expired token -> treat as unauthenticated
        return None

async def get_authenticated_user(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """Require authentication; raises 401 if not authenticated."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user
