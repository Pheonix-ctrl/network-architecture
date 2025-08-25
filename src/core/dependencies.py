from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from typing import Optional

from .security import verify_token

security = HTTPBearer(auto_error=False)

class SimpleUser:
    """Simple user object that matches what your main.py expects"""
    def __init__(self, id, username, email, mj_instance_id):
        self.id = id
        self.username = username
        self.email = email
        self.mj_instance_id = mj_instance_id

async def get_current_user(credentials = Depends(security)):
    """Get current user using asyncpg like main.py"""
    if not credentials:
        return None
    try:
        payload = verify_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            return None
            
        # Use the same database method as main.py
        from ..main import get_db_pool
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            user_row = await conn.fetchrow(
                "SELECT id, username, email, mj_instance_id FROM users WHERE id = $1",
                int(user_id)
            )
            if user_row:
                return SimpleUser(
                    id=user_row['id'],
                    username=user_row['username'], 
                    email=user_row['email'],
                    mj_instance_id=user_row['mj_instance_id']
                )
            return None
    except Exception:
        return None

async def get_authenticated_user(current_user = Depends(get_current_user)):
    """Require authentication"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return current_user