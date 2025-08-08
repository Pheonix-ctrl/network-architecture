# src/api/v1/memory.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ...config.database import get_db_session
from ...core.dependencies import get_authenticated_user
from ...models.database.user import User
from ...models.schemas.memory import MemoryCreate, MemoryResponse, MemoryUpdate
from ...database.repositories.memory import MemoryRepository
from ...services.memory.manager import MemoryManager
from ...services.ai.openai_client import OpenAIClient

router = APIRouter()

@router.post("/", response_model=MemoryResponse)
async def create_memory(
    memory_data: MemoryCreate,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Manually create a memory"""
    
    memory_manager = MemoryManager(db)
    
    try:
        memory = await memory_manager.create_memory(
            user_id=current_user.id,
            memory_data=memory_data
        )
        return memory
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create memory: {str(e)}"
        )

@router.get("/", response_model=List[MemoryResponse])
async def get_memories(
    query: Optional[str] = None,
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, le=100, description="Number of memories to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get user memories with optional search and filtering"""
    
    memory_repo = MemoryRepository(db)
    
    if query:
        # Use semantic search
        memory_manager = MemoryManager(db)
        memories = await memory_manager.get_relevant_memories(
            user_id=current_user.id,
            query=query,
            limit=limit
        )
        return memories
    else:
        # Get memories with filters
        memories = await memory_repo.get_by_user_filtered(
            user_id=current_user.id,
            memory_type=memory_type,
            category=category,
            limit=limit,
            offset=offset
        )
        return [MemoryResponse.from_orm(m) for m in memories]

@router.get("/search", response_model=List[MemoryResponse])
async def search_memories(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, le=50, description="Number of results"),
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Semantic search through user memories"""
    
    memory_manager = MemoryManager(db)
    
    memories = await memory_manager.get_relevant_memories(
        user_id=current_user.id,
        query=q,
        limit=limit,
        use_cache=True
    )
    
    return memories

@router.get("/stats", response_model=Dict[str, Any])
async def get_memory_stats(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get memory statistics for current user"""
    
    memory_repo = MemoryRepository(db)
    
    stats = await memory_repo.get_user_memory_stats(current_user.id)
    
    return {
        "total_memories": stats.get("total_memories", 0),
        "memory_types": stats.get("memory_types", {}),
        "categories": stats.get("categories", {}),
        "confidence_distribution": stats.get("confidence_distribution", {}),
        "recent_memories": stats.get("recent_memories", 0),
        "most_accessed_memories": stats.get("most_accessed", [])
    }

@router.get("/categories", response_model=List[str])
async def get_memory_categories(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all memory categories for current user"""
    
    memory_repo = MemoryRepository(db)
    categories = await memory_repo.get_user_categories(current_user.id)
    
    return categories

@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: int,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get specific memory by ID"""
    
    memory_repo = MemoryRepository(db)
    memory = await memory_repo.get_by_id_and_user(memory_id, current_user.id)
    
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    
    # Update access count
    await memory_repo.increment_access_count(memory_id)
    
    return MemoryResponse.from_orm(memory)

@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: int,
    memory_update: MemoryUpdate,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Update a specific memory"""
    
    memory_repo = MemoryRepository(db)
    memory = await memory_repo.get_by_id_and_user(memory_id, current_user.id)
    
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    
    # If fact is being updated, regenerate embedding
    update_data = memory_update.dict(exclude_unset=True)
    if "fact" in update_data:
        openai_client = OpenAIClient()
        embeddings = await openai_client.get_embeddings([update_data["fact"]])
        update_data["embedding"] = embeddings[0]
    
    updated_memory = await memory_repo.update(memory_id, update_data)
    
    # Invalidate cache
    from ...services.memory.redis_client import RedisClient
    redis = RedisClient()
    await redis.connect()
    await redis.invalidate_user_memory_cache(current_user.id)
    await redis.disconnect()
    
    return MemoryResponse.from_orm(updated_memory)

@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: int,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a specific memory"""
    
    memory_repo = MemoryRepository(db)
    memory = await memory_repo.get_by_id_and_user(memory_id, current_user.id)
    
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    
    await memory_repo.delete(memory_id)
    
    # Invalidate cache
    from ...services.memory.redis_client import RedisClient
    redis = RedisClient()
    await redis.connect()
    await redis.invalidate_user_memory_cache(current_user.id)
    await redis.disconnect()
    
    return {"message": "Memory deleted successfully"}

@router.post("/extract", response_model=Dict[str, Any])
async def trigger_memory_extraction(
    conversation_ids: List[int],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Manually trigger memory extraction from specific conversations"""
    
    memory_manager = MemoryManager(db)
    
    # Queue conversations for extraction
    for conv_id in conversation_ids:
        background_tasks.add_task(
            memory_manager.queue_conversation_for_extraction,
            current_user.id,
            conv_id
        )
    
    return {
        "message": f"Queued {len(conversation_ids)} conversations for memory extraction",
        "conversation_ids": conversation_ids
    }

@router.post("/validate/{memory_id}")
async def validate_memory(
    memory_id: int,
    is_valid: bool,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Validate or invalidate a memory (user feedback)"""
    
    memory_repo = MemoryRepository(db)
    memory = await memory_repo.get_by_id_and_user(memory_id, current_user.id)
    
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    
    # Update validation status
    update_data = {
        "is_validated": is_valid,
        "validation_source": "user_feedback"
    }
    
    # Adjust confidence based on validation
    if is_valid:
        update_data["confidence"] = min(memory.confidence + 0.1, 1.0)
    else:
        update_data["confidence"] = max(memory.confidence - 0.2, 0.1)
    
    await memory_repo.update(memory_id, update_data)
    
    return {
        "message": "Memory validation updated",
        "is_valid": is_valid,
        "new_confidence": update_data["confidence"]
    }

