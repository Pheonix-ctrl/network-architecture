# src/services/memory/manager.py
from typing import List, Dict, Optional, Any, Tuple
import asyncio
import json
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from ...database.repositories.memory import MemoryRepository
from ...database.repositories.conversation import ConversationRepository
from ...services.ai.openai_client import OpenAIClient
from ...services.ai.gemini_client import GeminiClient
from ..memory.redis_client import RedisClient
from ...models.schemas.memory import MemoryCreate, MemoryResponse
from ...config.settings import Settings

settings = Settings()

class MemoryManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.memory_repo = MemoryRepository(db)
        self.conversation_repo = ConversationRepository(db)
        self.openai = OpenAIClient()
        self.gemini = GeminiClient()
        self.redis = RedisClient()
        self._extraction_queue = asyncio.Queue()
        self._worker_task = None
    
    async def start_background_worker(self):
        """Start background memory extraction worker"""
        if not self._worker_task:
            self._worker_task = asyncio.create_task(self._background_worker())
    
    async def stop_background_worker(self):
        """Stop background worker gracefully"""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
    
    async def queue_conversation_for_extraction(
        self,
        user_id: int,
        conversation_id: int
    ):
        """Queue a conversation for memory extraction"""
        await self._extraction_queue.put((user_id, conversation_id))
    
    async def get_relevant_memories(
        self,
        user_id: int,
        query: str,
        limit: int = 10,
        use_cache: bool = True
    ) -> List[MemoryResponse]:
        """Get memories relevant to current query"""
        
        # Try cache first
        if use_cache:
            cached_memories = await self.redis.get_cached_memories(user_id, query)
            if cached_memories:
                return cached_memories
        
        # Get query embedding
        embeddings = await self.openai.get_embeddings([query])
        query_embedding = embeddings[0]
        
        # Search memories using embedding similarity
        memories = await self.memory_repo.search_by_embedding(
            user_id=user_id,
            embedding=query_embedding,
            limit=limit,
            similarity_threshold=settings.MEMORY_SIMILARITY_THRESHOLD
        )
        
        # Cache results
        if use_cache:
            await self.redis.cache_memories(user_id, query, memories)
        
        return memories
    
    async def create_memory(
        self,
        user_id: int,
        memory_data: MemoryCreate,
        source_conversation_id: Optional[int] = None
    ) -> MemoryResponse:
        """Create a new memory with embedding"""
        
        # Generate embedding for the memory
        embeddings = await self.openai.get_embeddings([memory_data.fact])
        embedding = embeddings[0]
        
        # Check for similar existing memories to avoid duplicates
        similar_memories = await self.memory_repo.search_by_embedding(
            user_id=user_id,
            embedding=embedding,
            limit=3,
            similarity_threshold=0.85  # High threshold for duplicate detection
        )
        
        # If very similar memory exists, update it instead
        if similar_memories and similar_memories[0].confidence < memory_data.confidence:
            existing_memory = similar_memories[0]
            existing_memory.confidence = memory_data.confidence
            existing_memory.access_count += 1
            await self.memory_repo.update(existing_memory)
            
            # Invalidate cache
            await self.redis.invalidate_user_memory_cache(user_id)
            return existing_memory
        
        # Create new memory
        memory = await self.memory_repo.create(
            user_id=user_id,
            memory_data=memory_data,
            embedding=embedding,
            source_conversation_id=source_conversation_id
        )
        
        # Invalidate cache
        await self.redis.invalidate_user_memory_cache(user_id)
        
        return memory
    
    async def _background_worker(self):
        """Background worker for processing memory extraction"""
        while True:
            try:
                # Get next conversation to process
                user_id, conversation_id = await self._extraction_queue.get()
                
                # Extract memories from conversation
                await self._process_conversation(user_id, conversation_id)
                
                # Mark task done
                self._extraction_queue.task_done()
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Memory extraction error: {e}")
                continue
    
    async def _process_conversation(self, user_id: int, conversation_id: int):
        """Extract memories from a conversation"""
        try:
            # Get conversation context (last few messages)
            conversations = await self.conversation_repo.get_conversation_context(
                user_id=user_id,
                conversation_id=conversation_id,
                context_window=5
            )
            
            if not conversations:
                return
            
            # Format conversation for memory extraction
            conversation_text = self._format_conversations_for_extraction(conversations)
            
            # Get user context (recent memories)
            recent_memories = await self.memory_repo.get_recent_memories(user_id, limit=10)
            user_context = "\n".join([m.fact for m in recent_memories]) if recent_memories else None
            
            # Extract memories using Gemini
            extracted_memories = await self.gemini.extract_memories(
                conversation_text=conversation_text,
                user_context=user_context
            )
            
            # Create memory objects
            for memory_data in extracted_memories:
                memory_create = MemoryCreate(
                    fact=memory_data['fact'],
                    context=memory_data.get('context', ''),
                    memory_type=memory_data['memory_type'],
                    category=memory_data.get('category', 'general'),
                    confidence=memory_data['confidence'],
                    importance=memory_data.get('importance', 0.5),
                    tags=memory_data.get('tags', [])
                )
                
                await self.create_memory(
                    user_id=user_id,
                    memory_data=memory_create,
                    source_conversation_id=conversation_id
                )
            
            print(f"Extracted {len(extracted_memories)} memories from conversation {conversation_id}")
            
        except Exception as e:
            print(f"Error processing conversation {conversation_id}: {e}")
    
    def _format_conversations_for_extraction(self, conversations: List) -> str:
        """Format conversations for memory extraction"""
        formatted = []
        for conv in conversations:
            role = "User" if conv.role == "user" else "MJ"
            formatted.append(f"{role}: {conv.content}")
        return "\n".join(formatted)
