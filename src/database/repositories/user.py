# src/database/repositories/user.py - Simplified version
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.sql import func
from typing import Optional, Dict, Any
from ...models.database.user import User

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

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

    async def create(self, user_data: Dict[str, Any]) -> User:
        """Create a new user"""
        user = User(**user_data)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user_id: int, update_data: Dict[str, Any]) -> Optional[User]:
        """Update user data"""
        # Add updated_at timestamp
        update_data["updated_at"] = func.now()
        
        result = await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(**update_data)
            .returning(User)
        )
        await self.db.commit()
        return result.scalar_one_or_none()

    async def update_last_active(self, user_id: int) -> None:
        """Update user's last active timestamp"""
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_active=func.now(), is_online=True)
        )
        await self.db.commit()

    async def set_online_status(self, user_id: int, is_online: bool) -> None:
        """Set user online/offline status"""
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_online=is_online)
        )
        await self.db.commit()

    async def delete(self, user_id: int) -> bool:
        """Delete user"""
        user = await self.get_by_id(user_id)
        if user:
            await self.db.delete(user)
            await self.db.commit()
            return True
        return False