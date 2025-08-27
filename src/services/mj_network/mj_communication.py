# src/services/mj_network/mj_communication.py - COMPLETE WORKING VERSION
import json
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ...database.repositories.mj_network import MJNetworkRepository
from ...database.repositories.memory import MemoryRepository
from ...services.ai.openai_client import OpenAIClient
from ...services.ai.personality.prompts import PersonalityPrompts
from ...models.database.mj_network import MJStatus, DeliveryStatus, MessageType

class MJCommunicationService:
    """Core service for MJ-to-MJ communication - The heart of your network"""
    
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
        🌐 MAIN MJ-TO-MJ CONVERSATION FLOW
        
        This is where the magic happens:
        1. Check if users are friends
        2. Get target user's memories/context  
        3. Build privacy-aware prompt
        4. Generate OpenAI response
        5. Save message and handle delivery
        """
        
        print(f"🤖 Initiating MJ conversation: User {from_user_id} -> User {to_user_id}")
        print(f"💭 Purpose: {message_purpose}")
        
        # Step 1: Validate relationship and get privacy settings
        relationship = await self.network_repo.relationships.get_mutual_relationship(from_user_id, to_user_id)
        if not relationship:
            raise ValueError("Users are not friends. Send a friend request first.")
        
        print(f"✅ Relationship found: {relationship.relationship_type} (trust: {relationship.trust_level})")
        
        # Step 2: Check target user's MJ status
        target_mj_registry = await self.network_repo.mj_registry.get_by_user_id(to_user_id)
        if not target_mj_registry:
            raise ValueError("Target user's MJ is not registered in the network")
        
        target_user_online = target_mj_registry.status == MJStatus.ONLINE.value
        can_respond_when_offline = await self.network_repo.relationships.can_mj_respond_when_offline(
            to_user_id, from_user_id
        )
        
        print(f"🔍 Target user status: {'online' if target_user_online else 'offline'}")
        print(f"📱 Can respond when offline: {can_respond_when_offline}")
        
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
            print(f"💬 Created new conversation: {conversation.id}")
        else:
            print(f"💬 Using existing conversation: {conversation.id}")
        
        # Step 4: 🧠 GENERATE MJ RESPONSE - This is the core AI magic
        try:
            mj_response_data = await self._generate_mj_response(
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                message_purpose=message_purpose,
                privacy_settings=relationship.privacy_settings or {},
                relationship_type=relationship.relationship_type
            )
            print(f"🎯 Generated response: '{mj_response_data['response_content'][:100]}...'")
        except Exception as e:
            print(f"❌ Failed to generate MJ response: {e}")
            # Provide fallback response
            mj_response_data = {
                "response_content": "I'm having trouble finding the right words right now... but I'm here for you. Maybe try reaching out again in a moment?",
                "prompt_used": f"Fallback response for: {message_purpose}",
                "raw_response": "Fallback response due to generation error",
                "privacy_settings_applied": relationship.privacy_settings or {},
                "memories_used": [],
                "tokens_used": 0
            }
        
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
        
        print(f"💾 Saved message: {message.id}")
        
        # Step 6: Handle delivery based on online status
        if target_user_online:
            await self.network_repo.messages.mark_as_delivered(message.id)
            await self.network_repo.mj_registry.increment_stats(
                user_id=to_user_id,
                messages_received=1
            )
            print(f"📨 Message delivered immediately (user online)")
        else:
            # Will be queued for offline delivery by the calling function
            print(f"📬 Message will be queued for offline delivery")
        
        # Step 7: Update sender statistics
        await self.network_repo.mj_registry.increment_stats(
            user_id=from_user_id,
            messages_sent=1
        )
        
        # Update conversation stats
        await self.network_repo.conversations.update_last_message(conversation.id)
        await self.network_repo.relationships.update_interaction(from_user_id, to_user_id)
        
        print(f"✅ MJ conversation completed successfully")
        
        return {
            "conversation": conversation,
            "message": message,
            "target_user_online": target_user_online,
            "response_generated": True,
            "tokens_used": mj_response_data["tokens_used"],
            "response_content": mj_response_data["response_content"]  # For immediate display
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
        🧠 THE CORE AI GENERATION - Where MJ personality meets privacy
        
        This creates the actual MJ-to-MJ conversation using:
        1. Target user's memories for context
        2. Privacy settings for filtering
        3. MJ personality for authentic responses
        """
        
        print(f"🧠 Generating MJ response with privacy level: {privacy_settings}")
        
        # Step 1: Get target user's memories for context (what MJ knows about them)
        try:
            target_user_memories = await self.memory_repo.get_recent_memories(
                user_id=to_user_id,
                limit=10,
                days=30
            )
            print(f"💭 Found {len(target_user_memories)} memories for context")
        except Exception as e:
            print(f"⚠️ Memory retrieval failed: {e}")
            target_user_memories = []
        
        # Step 2: Build context from memories
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
        
        # Step 3: 🎭 Build MJ-to-MJ prompt with personality and privacy
        prompt = PersonalityPrompts.build_mj_to_mj_prompt(
            message_purpose=message_purpose,
            user_context=user_context,
            privacy_settings=privacy_settings,
            relationship_type=relationship_type,
            from_user_id=from_user_id,
            to_user_id=to_user_id
        )
        
        print(f"📝 Built MJ-to-MJ prompt ({len(prompt)} chars)")
        
        # Step 4: 🤖 Generate response using OpenAI
        try:
            print(f"🔄 Calling OpenAI for MJ response...")
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
            
            print(f"✅ OpenAI response generated: {len(response_content)} chars, {tokens_used} tokens")
            
        except Exception as e:
            print(f"❌ OpenAI error in MJ communication: {e}")
            response_content = "I'm having some technical difficulties right now, but I'm still here for you."
            openai_response = {"content": response_content}
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
        """📬 Queue message for offline delivery"""
        
        await self.network_repo.pending_messages.queue_message(
            message_id=message_id,
            recipient_user_id=recipient_user_id
        )
        
        print(f"📬 Message {message_id} queued for offline delivery to user {recipient_user_id}")
    
    async def deliver_pending_messages(self, user_id: int) -> int:
        """
        📨 Deliver all pending messages when user comes online
        
        Called when MJ status changes to online
        """
        
        print(f"📨 Delivering pending messages for user {user_id}")
        
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
        
        if delivered_count > 0:
            print(f"✅ Delivered {delivered_count} pending messages to user {user_id}")
        
        return delivered_count
    
    async def get_conversation_history(
        self,
        user_a_id: int,
        user_b_id: int,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """📜 Get formatted conversation history between two users"""
        
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
                "tokens_used": message.tokens_used,
                "privacy_level_applied": message.privacy_settings_applied
            })
        
        return formatted_messages
    
    async def create_scheduled_checkin_conversation(
        self,
        checker_user_id: int,
        target_user_id: int,
        checkin_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        📅 Execute a scheduled check-in by creating a conversation and message
        
        This is called by the scheduled check-in system
        """
        
        print(f"📅 Executing scheduled check-in: {checker_user_id} -> {target_user_id}")
        
        try:
            # Use the regular MJ conversation flow for check-ins
            result = await self.initiate_mj_conversation(
                from_user_id=checker_user_id,
                to_user_id=target_user_id,
                message_purpose=f"Scheduled check-in: {checkin_data.get('checkin_message', 'How are you doing?')}",
                conversation_topic=f"Scheduled check-in: {checkin_data.get('checkin_name', 'General')}"
            )
            
            # Update message type to check-in
            await self.network_repo.messages.update(result["message"].id, {
                "message_type": MessageType.CHECK_IN.value
            })
            
            return {
                "success": True,
                "conversation_id": result["conversation"].id,
                "message_id": result["message"].id,
                "target_user_online": result["target_user_online"],
                "response_content": result["response_content"],
                "tokens_used": result["tokens_used"]
            }
            
        except Exception as e:
            print(f"❌ Failed to execute scheduled check-in: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_status_update(
        self,
        from_user_id: int,
        status_message: str,
        target_users: List[int] = None
    ) -> Dict[str, Any]:
        """
        📢 Send status update to friends (like "I'm at the gym")
        
        This broadcasts to all friends or specific users
        """
        
        if not target_users:
            # Get all friends
            friends = await self.network_repo.relationships.get_user_friends(from_user_id)
            target_users = [f.friend_user_id for f in friends]
        
        results = []
        
        for target_user_id in target_users:
            try:
                result = await self.initiate_mj_conversation(
                    from_user_id=from_user_id,
                    to_user_id=target_user_id,
                    message_purpose=f"Status update: {status_message}",
                    conversation_topic="Status Update"
                )
                
                # Update message type to status_update
                await self.network_repo.messages.update(result["message"].id, {
                    "message_type": MessageType.STATUS_UPDATE.value
                })
                
                results.append({
                    "target_user_id": target_user_id,
                    "success": True,
                    "message_id": result["message"].id
                })
                
            except Exception as e:
                print(f"❌ Failed to send status update to user {target_user_id}: {e}")
                results.append({
                    "target_user_id": target_user_id,
                    "success": False,
                    "error": str(e)
                })
        
        successful_sends = len([r for r in results if r["success"]])
        
        return {
            "message": f"Status update sent to {successful_sends}/{len(target_users)} friends",
            "results": results,
            "total_targets": len(target_users),
            "successful_sends": successful_sends
        }