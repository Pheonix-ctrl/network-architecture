# src/services/mj_network/mj_communication.py - FIXED VERSION
import json
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ...database.repositories.mj_network import MJNetworkRepository  # ← FIXED: Updated import path
from ...database.repositories.memory import MemoryRepository
from ...services.ai.openai_client import OpenAIClient
from ...services.ai.personality.prompts import PersonalityPrompts
from ...models.database.mj_network import MJStatus, DeliveryStatus, MessageType  # ← FIXED: Updated import path

class MJCommunicationService:
    """Core service for MJ-to-MJ communication"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.network_repo = MJNetworkRepository(db)
        self.memory_repo = MemoryRepository(db)
        self.openai_client = OpenAIClient()
    
    async def initiate_mj_conversation(
        self,
        from_user_id: int,
        to_user_id: int,
        message_purpose: str,
        conversation_topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main method for initiating MJ-to-MJ conversation
        
        Flow:
        1. Check if users are friends and get privacy settings
        2. Get target user's context/memories
        3. Build prompt with privacy settings
        4. Generate OpenAI response
        5. Create conversation and message records
        6. Handle online/offline delivery
        """
        
        # Step 1: Validate relationship and get privacy settings
        relationship = await self.network_repo.relationships.get_mutual_relationship(from_user_id, to_user_id)
        if not relationship:
            raise ValueError("Users are not friends. Send a friend request first.")
        
        # Step 2: Check if target user allows offline responses
        target_mj_registry = await self.network_repo.mj_registry.get_by_user_id(to_user_id)
        if not target_mj_registry:
            raise ValueError("Target user's MJ is not registered in the network")
        
        target_user_online = target_mj_registry.status == MJStatus.ONLINE.value
        can_respond_when_offline = await self.network_repo.relationships.can_mj_respond_when_offline(
            to_user_id, from_user_id
        )
        
        if not target_user_online and not can_respond_when_offline:
            raise ValueError("Target user is offline and does not allow offline responses")
        
        # Step 3: Get or create conversation
        conversation = await self.network_repo.conversations.get_conversation_between_users(from_user_id, to_user_id)
        if not conversation:
            conversation = await self.network_repo.conversations.create_conversation(
                user_a_id=from_user_id,
                user_b_id=to_user_id,
                initiated_by_user_id=from_user_id,
                conversation_topic=conversation_topic,
                relationship_id=relationship.id
            )
        
        # Step 4: Generate MJ response using OpenAI
        mj_response_data = await self._generate_mj_response(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            message_purpose=message_purpose,
            privacy_settings=relationship.privacy_settings or {},

            relationship_type=relationship.relationship_type
        )
        
        # Step 5: Create message record
        message = await self.network_repo.messages.create_mj_message(
            conversation_id=conversation.id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            message_content=mj_response_data["response_content"],
            message_type=MessageType.TEXT.value,
            openai_prompt_used=mj_response_data["prompt_used"],
            openai_response_raw=mj_response_data["raw_response"],
            privacy_settings_applied=mj_response_data["privacy_settings_applied"],
            user_memories_used=mj_response_data["memories_used"],
            tokens_used=mj_response_data["tokens_used"]
        )
        
        # Step 6: Mark as delivered if target is online
        if target_user_online:
            await self.network_repo.messages.mark_as_delivered(message.id)
        
        # Step 7: Update statistics
        await self.network_repo.mj_registry.increment_stats(
            user_id=from_user_id,
            messages_sent=1
        )
        
        if target_user_online:
            await self.network_repo.mj_registry.increment_stats(
                user_id=to_user_id,
                messages_received=1
            )
        
        return {
            "conversation": conversation,
            "message": message,
            "target_user_online": target_user_online,
            "response_generated": True,
            "tokens_used": mj_response_data["tokens_used"]
        }
    
    async def _generate_mj_response(
        self,
        from_user_id: int,
        to_user_id: int,
        message_purpose: str,
        privacy_settings: Dict[str, Any],
        relationship_type: str
    ) -> Dict[str, Any]:
        """
        Generate MJ response using OpenAI with privacy-aware prompting
        
        This is where the magic happens:
        1. Get target user's memories/context
        2. Build privacy-aware prompt
        3. Call OpenAI
        4. Return structured response data
        """
        
        # Step 1: Get target user's memories for context
        target_user_memories = await self.memory_repo.get_recent_memories(
            user_id=to_user_id,
            limit=10,
            days=30
        )
        
        # Step 2: Get recent conversations for additional context
        recent_conversations = await self.network_repo.conversations.get_user_conversations(
            user_id=to_user_id,
            limit=5
        )
        
        # Step 3: Build context string from memories
        context_parts = []
        memories_used = []
        
        for memory in target_user_memories:
            context_parts.append(f"- {memory.fact} (confidence: {memory.confidence})")
            memories_used.append({
                "id": memory.id,
                "fact": memory.fact,
                "category": memory.category,
                "confidence": memory.confidence
            })
        
        user_context = "\n".join(context_parts) if context_parts else "No specific memories available."
        
        # Step 4: Build privacy-aware prompt
        # Step 4: Build privacy-aware prompt
        prompt = PersonalityPrompts.build_mj_to_mj_prompt(
            message_purpose=message_purpose,
            user_context=user_context,
            privacy_settings=privacy_settings,
            relationship_type=relationship_type,
            from_user_id=from_user_id,
            to_user_id=to_user_id
        )
        
        # Step 5: Call OpenAI API
        try:
            openai_response = await self.openai_client.chat_completion(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": message_purpose}
                ],
                temperature=0.8,
                max_tokens=300
            )
            
            response_content = openai_response.get("content", "").strip()
            tokens_used = openai_response.get("tokens", {}).get("total", 0)
            
            if not response_content:
                response_content = "I'm having trouble finding the right words right now... maybe try again in a moment?"
            
        except Exception as e:
            print(f"OpenAI error in MJ communication: {e}")
            response_content = "I'm having some technical difficulties right now, but I'm still here for you."
            tokens_used = 0
        
        return {
            "response_content": response_content,
            "prompt_used": prompt,
            "raw_response": openai_response.get("content", "") if 'openai_response' in locals() else "",
            "privacy_settings_applied": privacy_settings,
            "memories_used": memories_used,
            "tokens_used": tokens_used
        }
    

    

    
    async def queue_offline_message(self, message_id: int, recipient_user_id: int):
        """Queue message for offline delivery"""
        
        await self.network_repo.pending_messages.queue_message(
            message_id=message_id,
            recipient_user_id=recipient_user_id
        )
        
        print(f"📬 Message {message_id} queued for offline delivery to user {recipient_user_id}")
    
    async def deliver_pending_messages(self, user_id: int) -> int:
        """
        Deliver all pending messages when user comes online
        
        Called when MJ status changes to online
        """
        
        pending_messages = await self.network_repo.pending_messages.get_pending_for_user(user_id)
        delivered_count = 0
        
        for pending in pending_messages:
            try:
                # Mark original message as delivered
                await self.network_repo.messages.mark_as_delivered(pending.message_id)
                
                # Mark pending message as delivered
                await self.network_repo.pending_messages.mark_as_delivered(pending.id)
                
                # Update recipient stats
                await self.network_repo.mj_registry.increment_stats(
                    user_id=user_id,
                    messages_received=1
                )
                
                delivered_count += 1
                print(f"📨 Delivered message {pending.message_id} to user {user_id}")
                
            except Exception as e:
                print(f"❌ Failed to deliver message {pending.message_id}: {e}")
                continue
        
        return delivered_count
    
    async def get_conversation_history(
        self,
        user_a_id: int,
        user_b_id: int,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get formatted conversation history between two users"""
        
        conversation = await self.network_repo.conversations.get_conversation_between_users(user_a_id, user_b_id)
        if not conversation:
            return []
        
        messages = await self.network_repo.messages.get_conversation_messages(
            conversation_id=conversation.id,
            limit=limit
        )
        
        formatted_messages = []
        for message in messages:
            formatted_messages.append({
                "id": message.id,
                "from_user_id": message.from_user_id,
                "to_user_id": message.to_user_id,
                "content": message.message_content,
                "message_type": message.message_type,
                "delivery_status": message.delivery_status,
                "created_at": message.created_at,
                "tokens_used": message.tokens_used
            })
        
        return formatted_messages
    
    async def generate_mj_checkin_response(
        self,
        checker_user_id: int,
        target_user_id: int,
        checkin_message: str,
        checkin_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Generate automated check-in response for scheduled check-ins
        
        This is similar to regular MJ communication but optimized for check-ins
        """
        
        # Get relationship for privacy settings
        relationship = await self.network_repo.relationships.get_mutual_relationship(checker_user_id, target_user_id)
        if not relationship:
            raise ValueError("No relationship found for scheduled check-in")
        
        # Generate response using similar logic to regular MJ communication
        response_data = await self._generate_mj_response(
            from_user_id=checker_user_id,
            to_user_id=target_user_id,
            message_purpose=f"Scheduled check-in: {checkin_message}",
            privacy_settings=relationship.privacy_settings or {},

            relationship_type=relationship.relationship_type
        )
        
        return response_data
    
    async def create_scheduled_checkin_conversation(
        self,
        checker_user_id: int,
        target_user_id: int,
        checkin_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a scheduled check-in by creating a conversation and message
        
        This is called by the scheduled check-in system
        """
        
        try:
            # Generate the check-in response
            response_data = await self.generate_mj_checkin_response(
                checker_user_id=checker_user_id,
                target_user_id=target_user_id,
                checkin_message=checkin_data.get("checkin_message", "How are you doing?"),
                checkin_type=checkin_data.get("checkin_type", "general")
            )
            
            # Get or create conversation
            conversation = await self.network_repo.conversations.get_conversation_between_users(
                checker_user_id, target_user_id
            )
            if not conversation:
                relationship = await self.network_repo.relationships.get_mutual_relationship(
                    checker_user_id, target_user_id
                )
                conversation = await self.network_repo.conversations.create_conversation(
                    user_a_id=checker_user_id,
                    user_b_id=target_user_id,
                    initiated_by_user_id=checker_user_id,
                    conversation_topic=f"Scheduled check-in: {checkin_data.get('checkin_name', 'General')}",
                    relationship_id=relationship.id if relationship else None
                )
            
            # Create the check-in message
            message = await self.network_repo.messages.create_mj_message(
                conversation_id=conversation.id,
                from_user_id=checker_user_id,
                to_user_id=target_user_id,
                message_content=response_data["response_content"],
                message_type=MessageType.CHECK_IN.value,
                openai_prompt_used=response_data["prompt_used"],
                openai_response_raw=response_data["raw_response"],
                privacy_settings_applied=response_data["privacy_settings_applied"],
                user_memories_used=response_data["memories_used"],
                tokens_used=response_data["tokens_used"]
            )
            
            # Check if target user is online
            target_mj_registry = await self.network_repo.mj_registry.get_by_user_id(target_user_id)
            target_user_online = target_mj_registry and target_mj_registry.status == MJStatus.ONLINE
            
            if target_user_online:
                await self.network_repo.messages.mark_as_delivered(message.id)
                await self.network_repo.mj_registry.increment_stats(target_user_id, messages_received=1)
            else:
                # Queue for offline delivery
                await self.queue_offline_message(message.id, target_user_id)
            
            # Update sender stats
            await self.network_repo.mj_registry.increment_stats(checker_user_id, messages_sent=1)
            
            return {
                "success": True,
                "conversation_id": conversation.id,
                "message_id": message.id,
                "target_user_online": target_user_online,
                "response_content": response_data["response_content"],
                "tokens_used": response_data["tokens_used"]
            }
            
        except Exception as e:
            print(f"❌ Failed to execute scheduled check-in: {e}")
            return {
                "success": False,
                "error": str(e)
            }