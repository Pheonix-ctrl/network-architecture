
# src/database/repositories/relationship.py
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from .base import BaseRepository
from ...models.database.relationship import Relationship

class RelationshipRepository(BaseRepository[Relationship]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Relationship)
    
    async def get_by_user(self, user_id: int) -> List[Relationship]:
        """Get all relationships for a user"""
        result = await self.db.execute(
            select(Relationship)
            .where(Relationship.user_id == user_id)
            .order_by(desc(Relationship.last_interaction), desc(Relationship.created_at))
        )
        return result.scalars().all()
    
    async def get_by_mj_id(self, user_id: int, mj_id: str) -> Optional[Relationship]:
        """Get relationship by MJ instance ID"""
        result = await self.db.execute(
            select(Relationship).where(
                and_(
                    Relationship.user_id == user_id,
                    Relationship.contact_mj_id == mj_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_by_id_and_user(self, relationship_id: int, user_id: int) -> Optional[Relationship]:
        """Get relationship by ID and user ID"""
        result = await self.db.execute(
            select(Relationship).where(
                and_(
                    Relationship.id == relationship_id,
                    Relationship.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_connected_relationships(self, user_id: int) -> List[Relationship]:
        """Get only connected (active) relationships"""
        result = await self.db.execute(
            select(Relationship)
            .where(Relationship.user_id == user_id)
            .where(Relationship.is_connected == True)
            .order_by(desc(Relationship.last_interaction))
        )
        return result.scalars().all()
    
    async def get_by_relationship_type(
        self,
        user_id: int,
        relationship_type: str
    ) -> List[Relationship]:
        """Get relationships by type (family, friend, colleague, etc.)"""
        result = await self.db.execute(
            select(Relationship)
            .where(Relationship.user_id == user_id)
            .where(Relationship.relationship_type == relationship_type)
            .order_by(desc(Relationship.trust_level))
        )
        return result.scalars().all()
    
    async def update_interaction(
        self,
        relationship_id: int,
        trust_adjustment: float = 0.0
    ) -> bool:
        """Update last interaction time and optionally adjust trust level"""
        
        update_data = {"last_interaction": datetime.utcnow()}
        
        if trust_adjustment != 0.0:
            # Adjust trust level within bounds [0.0, 1.0]
            update_data["trust_level"] = func.greatest(
                0.0,
                func.least(1.0, Relationship.trust_level + trust_adjustment)
            )
        
        result = await self.db.execute(
            update(Relationship)
            .where(Relationship.id == relationship_id)
            .values(**update_data)
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def update_share_level(
        self,
        relationship_id: int,
        new_share_level: str,
        user_id: int
    ) -> Optional[Relationship]:
        """Update sharing level for relationship"""
        
        result = await self.db.execute(
            update(Relationship)
            .where(
                and_(
                    Relationship.id == relationship_id,
                    Relationship.user_id == user_id
                )
            )
            .values(
                share_level=new_share_level,
                updated_at=datetime.utcnow()
            )
        )
        await self.db.commit()
        
        if result.rowcount > 0:
            return await self.get_by_id(relationship_id)
        return None
    
    async def add_restricted_topic(
        self,
        relationship_id: int,
        topic: str,
        user_id: int
    ) -> bool:
        """Add a topic to restricted topics list"""
        
        # Get current relationship
        relationship = await self.get_by_id_and_user(relationship_id, user_id)
        if not relationship:
            return False
        
        restricted_topics = relationship.restricted_topics or []
        if topic not in restricted_topics:
            restricted_topics.append(topic)
            
            result = await self.db.execute(
                update(Relationship)
                .where(Relationship.id == relationship_id)
                .values(
                    restricted_topics=restricted_topics,
                    updated_at=datetime.utcnow()
                )
            )
            await self.db.commit()
            return result.rowcount > 0
        
        return True  # Topic already restricted
    
    async def remove_restricted_topic(
        self,
        relationship_id: int,
        topic: str,
        user_id: int
    ) -> bool:
        """Remove a topic from restricted topics list"""
        
        relationship = await self.get_by_id_and_user(relationship_id, user_id)
        if not relationship:
            return False
        
        restricted_topics = relationship.restricted_topics or []
        if topic in restricted_topics:
            restricted_topics.remove(topic)
            
            result = await self.db.execute(
                update(Relationship)
                .where(Relationship.id == relationship_id)
                .values(
                    restricted_topics=restricted_topics,
                    updated_at=datetime.utcnow()
                )
            )
            await self.db.commit()
            return result.rowcount > 0
        
        return True  # Topic wasn't restricted
    
    async def get_relationship_stats(self, user_id: int) -> Dict[str, Any]:
        """Get relationship statistics for user"""
        
        # Total relationships
        total_result = await self.db.execute(
            select(func.count(Relationship.id))
            .where(Relationship.user_id == user_id)
        )
        total_relationships = total_result.scalar()
        
        # Connected relationships
        connected_result = await self.db.execute(
            select(func.count(Relationship.id))
            .where(Relationship.user_id == user_id)
            .where(Relationship.is_connected == True)
        )
        connected_relationships = connected_result.scalar()
        
        # Relationship types distribution
        type_stats_result = await self.db.execute(
            select(
                Relationship.relationship_type,
                func.count(Relationship.id)
            )
            .where(Relationship.user_id == user_id)
            .group_by(Relationship.relationship_type)
        )
        relationship_types = {rel_type: count for rel_type, count in type_stats_result}
        
        # Share levels distribution
        share_stats_result = await self.db.execute(
            select(
                Relationship.share_level,
                func.count(Relationship.id)
            )
            .where(Relationship.user_id == user_id)
            .group_by(Relationship.share_level)
        )
        share_levels = {level: count for level, count in share_stats_result}
        
        # Average trust level
        trust_result = await self.db.execute(
            select(func.avg(Relationship.trust_level))
            .where(Relationship.user_id == user_id)
            .where(Relationship.is_connected == True)
        )
        avg_trust_level = trust_result.scalar()
        
        return {
            "total_relationships": total_relationships,
            "connected_relationships": connected_relationships,
            "relationship_types": relationship_types,
            "share_levels": share_levels,
            "average_trust_level": float(avg_trust_level) if avg_trust_level else 0.0
        }
    
    async def disconnect_relationship(self, relationship_id: int, user_id: int) -> bool:
        """Disconnect (but don't delete) a relationship"""
        result = await self.db.execute(
            update(Relationship)
            .where(
                and_(
                    Relationship.id == relationship_id,
                    Relationship.user_id == user_id
                )
            )
            .values(
                is_connected=False,
                updated_at=datetime.utcnow()
            )
        )
        await self.db.commit()
        return result.rowcount > 0