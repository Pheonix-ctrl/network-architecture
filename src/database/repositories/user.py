
# src/database/repositories/user.py
from typing import Optional, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import uuid

from .base import BaseRepository
from ...models.database.user import User

class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, User)
    
    async def create(self, data: Dict[str, Any]) -> User:
        """Create user with auto-generated MJ instance ID"""
        # Generate unique MJ instance ID
        if "mj_instance_id" not in data:
            data["mj_instance_id"] = f"MJ-{uuid.uuid4().hex[:8]}"
        
        return await super().create(data)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def get_by_mj_instance_id(self, mj_instance_id: str) -> Optional[User]:
        """Get user by MJ instance ID"""
        result = await self.db.execute(
            select(User).where(User.mj_instance_id == mj_instance_id)
        )
        return result.scalar_one_or_none()
    
    async def update_last_active(self, user_id: int) -> bool:
        """Update user's last active timestamp"""
        result = await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_active=datetime.utcnow())
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def set_online_status(self, user_id: int, is_online: bool) -> bool:
        """Set user's online status"""
        result = await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_online=is_online, last_active=datetime.utcnow())
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def get_active_users(self, limit: int = 100) -> List[User]:
        """Get currently active users"""
        result = await self.db.execute(
            select(User)
            .where(User.is_online == True)
            .where(User.is_active == True)
            .limit(limit)
        )
        return result.scalars().all()
