# src/api/v1/chat.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import time
from datetime import datetime

from ...config.database import get_db_session
from ...core.dependencies import get_authenticated_user
from ...models.database.user import User
from ...models.schemas.chat import ChatMessage, ChatResponse, PersonalityMode
from ...database.repositories.conversation import ConversationRepository
from ...database.repositories.memory import MemoryRepository
from ...services.ai.openai_client import OpenAIClient
from ...services.ai.mode_classifier import ModeClassifier
from ...services.ai.personality.prompts import PersonalityPrompts
from ...services.memory.manager import MemoryManager
from ...services.external.perplexity import PerplexityClient
from ...utils.formatters import format_conversation_for_ai

router = APIRouter()

@router.post("/message", response_model=ChatResponse)
async def send_message(
    message: ChatMessage,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Send a chat message to MJ and get response"""
    
    start_time = time.time()
    
    try:
        # Initialize services
        openai_client = OpenAIClient()
        mode_classifier = ModeClassifier()
        personality_prompts = PersonalityPrompts()
        memory_manager = MemoryManager(db)
        conversation_repo = ConversationRepository(db)
        
        # Classify personality mode
        detected_mode, confidence = mode_classifier.classify_mode(
            message=message.content,
            current_mode=message.mode or PersonalityMode.MJ,
            user_context={"user_id": current_user.id}
        )
        
        # Use requested mode if provided, otherwise use detected mode
        active_mode = message.mode if message.mode else detected_mode
        
        # Get relevant memories
        relevant_memories = await memory_manager.get_relevant_memories(
            user_id=current_user.id,
            query=message.content,
            limit=8
        )
        
        # Get recent conversation context
        recent_conversations = await conversation_repo.get_recent_by_user(
            user_id=current_user.id,
            limit=10
        )
        
        # Build conversation messages for AI
        messages = await _build_conversation_context(
            user_message=message.content,
            mode=active_mode,
            memories=relevant_memories,
            recent_conversations=recent_conversations,
            user=current_user,
            personality_prompts=personality_prompts
        )
        
        # Get tools for this mode
        tools = _get_tools_for_mode(active_mode)
        
        # Generate AI response
        ai_response = await openai_client.chat_completion(
            messages=messages,
            mode=active_mode,
            tools=tools
        )
        
        # Handle tool calls if present
        final_content = ai_response["content"]
        if ai_response.get("tool_calls"):
            final_content = await _handle_tool_calls(
                ai_response["tool_calls"],
                openai_client,
                messages,
                active_mode
            )
        
        # Save user message
        user_conversation = await conversation_repo.create({
            "user_id": current_user.id,
            "role": "user",
            "content": message.content,
            "personality_mode": active_mode,
            "tokens_used": 0
        })
        
        # Save AI response
        response_time_ms = int((time.time() - start_time) * 1000)
        ai_conversation = await conversation_repo.create({
            "user_id": current_user.id,
            "role": "assistant", 
            "content": final_content,
            "personality_mode": active_mode,
            "tokens_used": ai_response["tokens"]["total"],
            "response_time_ms": response_time_ms
        })
        
        # Queue for memory extraction (background task)
        background_tasks.add_task(
            memory_manager.queue_conversation_for_extraction,
            current_user.id,
            user_conversation.id
        )
        
        return ChatResponse(
            content=final_content,
            mode=active_mode,
            response_time_ms=response_time_ms,
            tokens_used=ai_response["tokens"]["total"],
            session_id=str(user_conversation.session_id),
            similar_memories=[m.dict() for m in relevant_memories]
        )
        
    except Exception as e:
        print(f"Chat error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message"
        )

@router.get("/history", response_model=List[Dict[str, Any]])
async def get_chat_history(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get chat history for current user"""
    
    conversation_repo = ConversationRepository(db)
    conversations = await conversation_repo.get_by_user_paginated(
        user_id=current_user.id,
        limit=limit,
        offset=offset
    )
    
    return [
        {
            "id": conv.id,
            "role": conv.role,
            "content": conv.content,
            "mode": conv.personality_mode,
            "timestamp": conv.created_at,
            "tokens_used": conv.tokens_used,
            "response_time_ms": conv.response_time_ms
        }
        for conv in conversations
    ]

@router.delete("/history")
async def clear_chat_history(
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Clear all chat history for current user"""
    
    conversation_repo = ConversationRepository(db)
    deleted_count = await conversation_repo.delete_by_user(current_user.id)
    
    return {
        "message": f"Deleted {deleted_count} conversations",
        "deleted_count": deleted_count
    }

@router.post("/mode", response_model=Dict[str, Any])
async def set_personality_mode(
    mode: PersonalityMode,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Manually set personality mode for user"""
    
    # Update user's preferred mode
    from ...database.repositories.user import UserRepository
    user_repo = UserRepository(db)
    await user_repo.update(current_user.id, {"preferred_mode": mode.value})
    
    return {
        "message": f"Personality mode set to {mode.value}",
        "mode": mode.value,
        "timestamp": datetime.utcnow()
    }

async def _build_conversation_context(
    user_message: str,
    mode: PersonalityMode,
    memories: List[Any],
    recent_conversations: List[Any],
    user: User,
    personality_prompts: PersonalityPrompts
) -> List[Dict[str, str]]:
    """Build conversation context for AI"""
    
    messages = []
    
    # Add personality system prompt
    system_prompt = personality_prompts.MODE_PROMPTS[mode]
    
    # Add memory context
    if memories:
        memory_context = personality_prompts.MEMORY_INTEGRATION_PROMPT.format(
            memories="\n".join([f"- {m.fact} (confidence: {m.confidence:.1f})" for m in memories[:5]]),
            recent_context=""
        )
        system_prompt += "\n\n" + memory_context
    
    # Add user context
    system_prompt += f"\n\nUser Info: {user.username}, preferred mode: {user.preferred_mode}"
    
    messages.append({"role": "system", "content": system_prompt})
    
    # Add recent conversation context (last 4 messages)
    for conv in recent_conversations[-4:]:
        messages.append({
            "role": conv.role,
            "content": conv.content
        })
    
    # Add current user message
    messages.append({"role": "user", "content": user_message})
    
    return messages

def _get_tools_for_mode(mode: PersonalityMode) -> Optional[List[Dict]]:
    """Get available tools for personality mode"""
    
    # All modes have Perplexity search
    tools = [{
        "type": "function",
        "function": {
            "name": "perplexity_search",
            "description": "Search for real-time information, current events, news, weather, facts",
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
    
    # Mode-specific tools
    if mode == PersonalityMode.KALKI:
        # Add emergency/safety tools
        tools.append({
            "type": "function", 
            "function": {
                "name": "emergency_assistance",
                "description": "Get emergency contact information or safety guidance",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "emergency_type": {"type": "string", "enum": ["medical", "safety", "crisis"]},
                        "location": {"type": "string", "description": "User's location if known"}
                    },
                    "required": ["emergency_type"]
                }
            }
        })
    
    elif mode == PersonalityMode.HEALTHCARE:
        # Add health information tools
        tools.append({
            "type": "function",
            "function": {
                "name": "health_information",
                "description": "Get general health information (not medical advice)",
                "parameters": {
                    "type": "object", 
                    "properties": {
                        "topic": {"type": "string", "description": "Health topic to research"}
                    },
                    "required": ["topic"]
                }
            }
        })
    
    return tools

async def _handle_tool_calls(
    tool_calls: List[Any],
    openai_client: OpenAIClient,
    messages: List[Dict[str, str]],
    mode: PersonalityMode
) -> str:
    """Handle tool calls and generate final response"""
    
    # Process each tool call
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        
        if function_name == "perplexity_search":
            perplexity = PerplexityClient()
            search_result = await perplexity.search(arguments["query"])
            
            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": search_result
            })
        
        elif function_name == "emergency_assistance":
            emergency_info = _get_emergency_info(arguments)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": emergency_info
            })
        
        elif function_name == "health_information":
            health_info = await _get_health_info(arguments["topic"])
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": health_info
            })
    
    # Generate final response with tool results
    final_response = await openai_client.chat_completion(
        messages=messages,
        mode=mode
    )
    
    return final_response["content"]

def _get_emergency_info(arguments: Dict[str, Any]) -> str:
    """Get emergency assistance information"""
    emergency_type = arguments.get("emergency_type", "general")
    
    emergency_contacts = {
        "medical": "🚨 EMERGENCY: Call 911 immediately for medical emergencies. If you're having chest pain, difficulty breathing, severe bleeding, or loss of consciousness, call 911 now.",
        "safety": "🛡️ SAFETY: If you're in immediate danger, call 911. For domestic violence: National Hotline 1-800-799-7233. For crisis text support: Text HOME to 741741.",
        "crisis": "💙 CRISIS SUPPORT: National Suicide Prevention Lifeline: 988. Crisis Text Line: Text HOME to 741741. You're not alone - help is available 24/7."
    }
    
    return emergency_contacts.get(emergency_type, emergency_contacts["crisis"])

async def _get_health_info(topic: str) -> str:
    """Get general health information (not medical advice)"""
    # This would integrate with reliable health information APIs
    # For now, return a general disclaimer
    return f"""
    General information about {topic}:
    
    ⚠️ IMPORTANT: This is general information only, not medical advice. 
    Always consult with healthcare professionals for medical concerns.
    
    For reliable health information, visit:
    - CDC: cdc.gov
    - Mayo Clinic: mayoclinic.org  
    - WebMD: webmd.com
    
    If you have urgent health concerns, contact your doctor or call 911.
    """