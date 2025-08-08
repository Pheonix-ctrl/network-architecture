
# src/services/websocket/handlers.py
from typing import Dict, Any, Optional
import json
from ...services.ai.openai_client import OpenAIClient
from ...services.ai.mode_classifier import ModeClassifier
from ...services.ai.personality.prompts import PersonalityPrompts
from ...services.memory.manager import MemoryManager
from ...models.schemas.chat import PersonalityMode, ChatResponse
from .manager import ConnectionManager

class WebSocketHandler:
    def __init__(
        self,
        connection_manager: ConnectionManager,
        memory_manager: MemoryManager
    ):
        self.connection_manager = connection_manager
        self.memory_manager = memory_manager
        self.openai_client = OpenAIClient()
        self.mode_classifier = ModeClassifier()
        self.personality_prompts = PersonalityPrompts()
    
    async def handle_chat_message(
        self,
        user_id: int,
        message: str,
        session_data: Dict[str, Any]
    ) -> ChatResponse:
        """Handle incoming chat message"""
        
        # Send typing indicator
        await self.connection_manager.send_typing_indicator(user_id, True)
        
        try:
            # Classify personality mode
            current_mode = session_data.get("current_mode", PersonalityMode.MJ)
            new_mode, confidence = self.mode_classifier.classify_mode(
                message=message,
                current_mode=current_mode
            )
            
            # If mode changed, notify user
            if new_mode != current_mode:
                reason = self.mode_classifier.get_mode_explanation(new_mode)
                await self.connection_manager.send_mode_change(user_id, new_mode, reason)
            
            # Get relevant memories
            relevant_memories = await self.memory_manager.get_relevant_memories(
                user_id=user_id,
                query=message,
                limit=8
            )
            
            # Build conversation context
            messages = await self._build_conversation_context(
                user_id=user_id,
                current_message=message,
                mode=new_mode,
                memories=relevant_memories
            )
            
            # Generate AI response
            response = await self.openai_client.chat_completion(
                messages=messages,
                mode=new_mode,
                tools=self._get_tools_for_mode(new_mode)
            )
            
            # Stop typing indicator
            await self.connection_manager.send_typing_indicator(user_id, False)
            
            # Queue conversation for memory extraction
            # Note: conversation_id would be set after saving to DB
            # await self.memory_manager.queue_conversation_for_extraction(user_id, conversation_id)
            
            return ChatResponse(
                content=response["content"],
                mode=new_mode,
                response_time_ms=0,  # Would calculate actual time
                tokens_used=response["tokens"]["total"],
                session_id=f"ws_{user_id}",
                similar_memories=[m.dict() for m in relevant_memories]
            )
            
        except Exception as e:
            await self.connection_manager.send_typing_indicator(user_id, False)
            raise e
    
    async def _build_conversation_context(
        self,
        user_id: int,
        current_message: str,
        mode: PersonalityMode,
        memories: List[Any]
    ) -> List[Dict[str, str]]:
        """Build conversation context for AI"""
        
        messages = []
        
        # Add personality prompt
        system_prompt = self.personality_prompts.MODE_PROMPTS[mode]
        
        # Add memory context if available
        if memories:
            memory_context = self.personality_prompts.MEMORY_INTEGRATION_PROMPT.format(
                memories="\n".join([f"- {m.fact}" for m in memories]),
                recent_context=""  # Would add recent conversation context
            )
            system_prompt += "\n\n" + memory_context
        
        messages.append({"role": "system", "content": system_prompt})
        
        # Add recent conversation history (would fetch from DB)
        # For now, just add current message
        messages.append({"role": "user", "content": current_message})
        
        return messages
    
    def _get_tools_for_mode(self, mode: PersonalityMode) -> Optional[List[Dict]]:
        """Get available tools for personality mode"""
        
        # All modes have access to Perplexity search
        tools = [{
            "type": "function",
            "function": {
                "name": "perplexity_search",
                "description": "Search for real-time information, current events, news, facts",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for current information"
                        }
                    },
                    "required": ["query"]
                }
            }
        }]
        
        # Mode-specific tools would be added here
        # Kalki mode: Emergency services, location services
        # Healthcare mode: Medical databases, symptom checkers
        # Educational mode: Educational resources, calculators
        
        return tools
    
    async def handle_mode_request(
        self,
        user_id: int,
        requested_mode: str
    ):
        """Handle manual mode change request"""
        try:
            mode = PersonalityMode(requested_mode)
            await self.connection_manager.send_mode_change(
                user_id=user_id,
                new_mode=mode,
                reason="Mode changed by user request"
            )
        except ValueError:
            await self.connection_manager.send_personal_message(user_id, {
                "type": "error",
                "message": f"Invalid mode: {requested_mode}"
            })
    
    async def handle_memory_query(
        self,
        user_id: int,
        query: str
    ):
        """Handle memory search query"""
        memories = await self.memory_manager.get_relevant_memories(
            user_id=user_id,
            query=query,
            limit=10
        )
        
        await self.connection_manager.send_personal_message(user_id, {
            "type": "memory_results",
            "query": query,
            "memories": [m.dict() for m in memories],
            "count": len(memories)
        })