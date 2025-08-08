
# src/database/repositories/memory.py
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, func, desc, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import numpy as np

from .base import BaseRepository
from ...models.database.memory import Memory
from ...models.schemas.memory import MemoryCreate, MemoryResponse

class MemoryRepository(BaseRepository[Memory]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Memory)
    
    async def create_with_embedding(
        self,
        user_id: int,
        memory_data: MemoryCreate,
        embedding: List[float],
        source_conversation_id: Optional[int] = None
    ) -> Memory:
        """Create memory with embedding"""
        
        data = {
            "user_id": user_id,
            "source_conversation_id": source_conversation_id,
            "embedding": embedding,
            **memory_data.dict()
        }
        
        return await self.create(data)
    
    async def search_by_embedding(
        self,
        user_id: int,
        embedding: List[float],
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[MemoryResponse]:
        """Search memories by embedding similarity using cosine similarity"""
        
        # Convert embedding to PostgreSQL array format
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        
        # Use raw SQL for vector similarity search
        # In production, you'd use pgvector extension for better performance
        query = text("""
            SELECT m.*, 
                   (m.embedding <-> :embedding::float[]) as distance,
                   (1 - (m.embedding <-> :embedding::float[])) as similarity
            FROM memories m
            WHERE m.user_id = :user_id 
            AND (1 - (m.embedding <-> :embedding::float[])) >= :threshold
            ORDER BY similarity DESC
            LIMIT :limit
        """)
        
        result = await self.db.execute(
            query,
            {
                "user_id": user_id,
                "embedding": embedding_str,
                "threshold": similarity_threshold,
                "limit": limit
            }
        )
        
        memories = []
        for row in result:
            memory_dict = {
                "id": row.id,
                "fact": row.fact,
                "context": row.context,
                "memory_type": row.memory_type,
                "category": row.category,
                "confidence": row.confidence,
                "importance": row.importance,
                "relevance_tags": row.relevance_tags or [],
                "access_count": row.access_count,
                "created_at": row.created_at,
                "last_accessed": row.last_accessed,
                "is_validated": row.is_validated
            }
            # Add similarity score
            memory_dict["relevance_score"] = float(row.similarity)
            memories.append(MemoryResponse(**memory_dict))
        
        return memories
    
    async def get_by_user_filtered(
        self,
        user_id: int,
        memory_type: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Memory]:
        """Get memories with filters"""
        
        query = select(Memory).where(Memory.user_id == user_id)
        
        if memory_type:
            query = query.where(Memory.memory_type == memory_type)
        
        if category:
            query = query.where(Memory.category == category)
        
        query = query.order_by(desc(Memory.last_accessed), desc(Memory.confidence))
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_by_id_and_user(self, memory_id: int, user_id: int) -> Optional[Memory]:
        """Get memory by ID and user ID"""
        result = await self.db.execute(
            select(Memory).where(
                and_(Memory.id == memory_id, Memory.user_id == user_id)
            )
        )
        return result.scalar_one_or_none()
    
    async def increment_access_count(self, memory_id: int) -> bool:
        """Increment access count and update last accessed time"""
        result = await self.db.execute(
            update(Memory)
            .where(Memory.id == memory_id)
            .values(
                access_count=Memory.access_count + 1,
                last_accessed=datetime.utcnow()
            )
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def get_recent_memories(
        self,
        user_id: int,
        limit: int = 10,
        days: int = 30
    ) -> List[Memory]:
        """Get recent memories within specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            select(Memory)
            .where(Memory.user_id == user_id)
            .where(Memory.created_at >= cutoff_date)
            .order_by(desc(Memory.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_high_confidence_memories(
        self,
        user_id: int,
        confidence_threshold: float = 0.8,
        limit: int = 20
    ) -> List[Memory]:
        """Get high confidence memories"""
        result = await self.db.execute(
            select(Memory)
            .where(Memory.user_id == user_id)
            .where(Memory.confidence >= confidence_threshold)
            .order_by(desc(Memory.confidence), desc(Memory.access_count))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_user_memory_stats(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive memory statistics for user"""
        
        # Total memories
        total_result = await self.db.execute(
            select(func.count(Memory.id)).where(Memory.user_id == user_id)
        )
        total_memories = total_result.scalar()
        
        # Memory types distribution
        type_stats_result = await self.db.execute(
            select(
                Memory.memory_type,
                func.count(Memory.id)
            )
            .where(Memory.user_id == user_id)
            .group_by(Memory.memory_type)
        )
        memory_types = {mem_type: count for mem_type, count in type_stats_result}
        
        # Categories distribution
        category_stats_result = await self.db.execute(
            select(
                Memory.category,
                func.count(Memory.id)
            )
            .where(Memory.user_id == user_id)
            .where(Memory.category.is_not(None))
            .group_by(Memory.category)
        )
        categories = {category: count for category, count in category_stats_result}
        
        # Confidence distribution
        confidence_stats_result = await self.db.execute(
            select(
                func.case(
                    (Memory.confidence >= 0.9, "very_high"),
                    (Memory.confidence >= 0.8, "high"),
                    (Memory.confidence >= 0.6, "medium"),
                    (Memory.confidence >= 0.4, "low"),
                    else_="very_low"
                ).label("confidence_level"),
                func.count(Memory.id)
            )
            .where(Memory.user_id == user_id)
            .group_by("confidence_level")
        )
        confidence_distribution = {level: count for level, count in confidence_stats_result}
        
        # Recent memories (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_result = await self.db.execute(
            select(func.count(Memory.id))
            .where(Memory.user_id == user_id)
            .where(Memory.created_at >= seven_days_ago)
        )
        recent_memories = recent_result.scalar()
        
        # Most accessed memories
        accessed_result = await self.db.execute(
            select(Memory.fact, Memory.access_count)
            .where(Memory.user_id == user_id)
            .order_by(desc(Memory.access_count))
            .limit(5)
        )
        most_accessed = [
            {"fact": fact, "access_count": count}
            for fact, count in accessed_result
        ]
        
        return {
            "total_memories": total_memories,
            "memory_types": memory_types,
            "categories": categories,
            "confidence_distribution": confidence_distribution,
            "recent_memories": recent_memories,
            "most_accessed": most_accessed
        }
    
    async def get_user_categories(self, user_id: int) -> List[str]:
        """Get all categories used by user"""
        result = await self.db.execute(
            select(Memory.category)
            .where(Memory.user_id == user_id)
            .where(Memory.category.is_not(None))
            .distinct()
        )
        return [category for category, in result]
    
    async def cleanup_old_memories(
        self,
        user_id: int,
        days: int = 365,
        min_confidence: float = 0.3
    ) -> int:
        """Clean up old, low-confidence memories"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.execute(
            delete(Memory)
            .where(Memory.user_id == user_id)
            .where(Memory.created_at < cutoff_date)
            .where(Memory.confidence < min_confidence)
            .where(Memory.access_count < 2)
        )
        await self.db.commit()
        return result.rowcount
