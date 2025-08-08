# src/database/repositories/base.py
from typing import Generic, TypeVar, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime

ModelType = TypeVar("ModelType", bound=DeclarativeBase)

class BaseRepository(Generic[ModelType]):
    def __init__(self, db: AsyncSession, model: type[ModelType]):
        self.db = db
        self.model = model
    
    async def create(self, data: Dict[str, Any]) -> ModelType:
        """Create a new record"""
        db_obj = self.model(**data)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj
    
    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """Get record by ID"""
        result = await self.db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()
    
    async def get_all(self, limit: int = 100, offset: int = 0) -> List[ModelType]:
        """Get all records with pagination"""
        result = await self.db.execute(
            select(self.model)
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
    
    async def update(self, id: int, data: Dict[str, Any]) -> Optional[ModelType]:
        """Update record by ID"""
        await self.db.execute(
            update(self.model)
            .where(self.model.id == id)
            .values(**data)
        )
        await self.db.commit()
        return await self.get_by_id(id)
    
    async def delete(self, id: int) -> bool:
        """Delete record by ID"""
        result = await self.db.execute(
            delete(self.model).where(self.model.id == id)
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def count(self) -> int:
        """Count total records"""
        result = await self.db.execute(select(func.count(self.model.id)))
        return result.scalar()
