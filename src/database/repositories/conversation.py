
# src/database/repositories/conversation.py
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import uuid

from .base import BaseRepository
from ...models.database.conversation import Conversation

class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Conversation)
    
    async def create(self, data: Dict[str, Any]) -> Conversation:
        """Create conversation with auto-generated session ID if not provided"""
        if "session_id" not in data:
            data["session_id"] = uuid.uuid4()
        
        return await super().create(data)
    
    async def get_by_user(self, user_id: int, limit: int = 50) -> List[Conversation]:
        """Get conversations by user ID"""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_by_user_paginated(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Conversation]:
        """Get paginated conversations by user"""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
    
    async def get_recent_by_user(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Conversation]:
        """Get recent conversations by user (for context)"""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.created_at))
            .limit(limit)
        )
        conversations = result.scalars().all()
        return list(reversed(conversations))  # Return in chronological order
    
    async def get_conversation_context(
        self,
        user_id: int,
        conversation_id: int,
        context_window: int = 10
    ) -> List[Conversation]:
        """Get conversation context around a specific conversation"""
        
        # Get the target conversation's timestamp
        target_conv_result = await self.db.execute(
            select(Conversation.created_at)
            .where(Conversation.id == conversation_id)
        )
        target_timestamp = target_conv_result.scalar_one_or_none()
        
        if not target_timestamp:
            return []
        
        # Get conversations around that timestamp
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .where(Conversation.created_at <= target_timestamp)
            .order_by(desc(Conversation.created_at))
            .limit(context_window)
        )
        conversations = result.scalars().all()
        return list(reversed(conversations))
    
    async def get_by_session(self, session_id: uuid.UUID) -> List[Conversation]:
        """Get all conversations in a session"""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.session_id == session_id)
            .order_by(Conversation.created_at)
        )
        return result.scalars().all()
    
    async def delete_by_user(self, user_id: int) -> int:
        """Delete all conversations for a user"""
        result = await self.db.execute(
            delete(Conversation).where(Conversation.user_id == user_id)
        )
        await self.db.commit()
        return result.rowcount
    
    async def delete_older_than(self, days: int) -> int:
        """Delete conversations older than specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        result = await self.db.execute(
            delete(Conversation).where(Conversation.created_at < cutoff_date)
        )
        await self.db.commit()
        return result.rowcount
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get conversation statistics for a user"""
        
        # Total conversations
        total_result = await self.db.execute(
            select(func.count(Conversation.id))
            .where(Conversation.user_id == user_id)
        )
        total_conversations = total_result.scalar()
        
        # Conversations by role
        role_stats_result = await self.db.execute(
            select(
                Conversation.role,
                func.count(Conversation.id)
            )
            .where(Conversation.user_id == user_id)
            .group_by(Conversation.role)
        )
        role_stats = {role: count for role, count in role_stats_result}
        
        # Total tokens used
        tokens_result = await self.db.execute(
            select(func.sum(Conversation.tokens_used))
            .where(Conversation.user_id == user_id)
        )
        total_tokens = tokens_result.scalar() or 0
        
        # Average response time
        response_time_result = await self.db.execute(
            select(func.avg(Conversation.response_time_ms))
            .where(Conversation.user_id == user_id)
            .where(Conversation.response_time_ms.is_not(None))
        )
        avg_response_time = response_time_result.scalar()
        
        # Recent activity (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_result = await self.db.execute(
            select(func.count(Conversation.id))
            .where(Conversation.user_id == user_id)
            .where(Conversation.created_at >= seven_days_ago)
        )
        recent_conversations = recent_result.scalar()
        
        return {
            "total_conversations": total_conversations,
            "role_distribution": role_stats,
            "total_tokens_used": total_tokens,
            "average_response_time_ms": float(avg_response_time) if avg_response_time else None,
            "recent_conversations_7d": recent_conversations
        }
