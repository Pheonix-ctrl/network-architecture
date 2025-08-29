# src/services/mj_network/mj_communication.py - MODIFIED FOR DRAFT APPROVAL WORKFLOW
import json
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ...database.repositories.mj_network import MJNetworkRepository
from ...database.repositories.memory import MemoryRepository
from ...services.ai.openai_client import OpenAIClient
from ...services.ai.personality.prompts import PersonalityPrompts
from ...models.database.mj_network import MJStatus, DeliveryStatus, MessageType
from datetime import datetime, timedelta

import json
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from decimal import Decimal

def serialize_for_json(obj):
    """Convert objects to JSON-serializable format"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    return obj

class MJCommunicationService:
    """Core service for MJ-to-MJ communication - Modified for draft approval workflow"""
    
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
        🌐 MODIFIED: Now only handles SENDING REQUESTS (User A to User B's MJ)
        
        This method now:
        1. Sends the request from User A's MJ to User B's MJ
        2. Triggers draft response generation for User B (but doesn't auto-send)
        """
        
        print(f"🤖 Initiating MJ conversation: User {from_user_id} -> User {to_user_id}")
        print(f"💭 Purpose: {message_purpose}")
        
        # Step 1: Validate relationship and get privacy settings
        relationship = await self.network_repo.relationships.get_mutual_relationship(from_user_id, to_user_id)
        if not relationship:
            raise ValueError("Users are not friends. Send a friend request first.")
        
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
        
        # Step 3: Get or create conversation
        conversation = await self.network_repo.conversations.get_conversation_between_users(from_user_id, to_user_id)
        if not conversation:
            conversation = await self.network_repo.conversations.create_conversation(
                user_a_id=from_user_id,
                user_b_id=to_user_id,
                initiated_by_user_id=from_user_id,
                conversation_topic=conversation_topic,
                relationship_id=getattr(relationship, 'id', None)
            )
            print(f"💬 Created new conversation: {conversation.id}")
        else:
            print(f"💬 Using existing conversation: {conversation.id}")
        
        # Step 4: Create the REQUEST message (this gets sent immediately)
        request_message = await self.network_repo.messages.create_mj_message(
            conversation_id=conversation.id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            message_content=message_purpose,
            message_type=MessageType.QUESTION.value,
            openai_prompt_used=None,
            openai_response_raw=None,
            privacy_settings_applied={},
            user_memories_used=[],  # <- This is fine as empty list
            tokens_used=0,
            approval_status="sent"
        )
        
        print(f"💾 Saved request message: {request_message.id}")
        
        # Step 5: Handle delivery of the request
        if target_user_online:
            await self.network_repo.messages.mark_as_delivered(request_message.id)
            await self.network_repo.mj_registry.increment_stats(
                user_id=to_user_id,
                messages_received=1
            )
            print(f"📨 Request delivered immediately (user online)")
        else:
            await self.queue_offline_message(request_message.id, to_user_id)
            print(f"📬 Request queued for offline delivery")
        
        # Step 6: Generate draft response for the target user (User B)
        # Step 6: Generate draft response for the target user (User B)
        try:
            draft_response = await self.generate_draft_response(
                request_message_id=request_message.id,
                responding_user_id=to_user_id,
                requesting_user_id=from_user_id,
                conversation_id=conversation.id,
                message_purpose=message_purpose
            )
            print(f"📝 Generated draft response for user {to_user_id}")
        except Exception as e:
            print(f"⚠️ Failed to generate draft response: {e}")
            draft_response = None
        
        # Step 7: Update sender statistics
        await self.network_repo.mj_registry.increment_stats(
            user_id=from_user_id,
            messages_sent=1
        )
        
        # Update conversation stats
        # Only increment for the sent request message, not the draft
        await self.network_repo.conversations.update_last_message(conversation.id, increment=True)
        await self.network_repo.relationships.update_interaction(from_user_id, to_user_id)
        
        print(f"✅ MJ request sent successfully, draft response generated")
        
        return {
            "conversation": conversation,
            "request_message": request_message,
            "draft_response": draft_response,
            "target_user_online": target_user_online,
            "request_sent": True,
            "draft_generated": draft_response is not None
        }
    
    async def _check_user_online_status(self, user_id: int) -> bool:
        """
        Check if a user's MJ is currently online and available for immediate delivery
        """
        from datetime import datetime, timedelta, timezone
        
        try:
            mj_registry = await self.network_repo.mj_registry.get_by_user_id(user_id)
            
            if not mj_registry:
                return False
            
            if mj_registry.status != MJStatus.ONLINE.value:
                return False
            
            if mj_registry.last_seen:
                # Use UTC-aware datetime for comparison
                five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
                if mj_registry.last_seen < five_minutes_ago:
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error checking online status for user {user_id}: {e}")
            return False

    async def generate_draft_response(
        self,
        request_message_id: int,
        responding_user_id: int,
        requesting_user_id: int,
        conversation_id: int,
        message_purpose: str
    ) -> Dict[str, Any]:
        """
        🆕 NEW: Generate a draft response that needs user approval
        
        This creates the MJ response but saves it as a draft, not sent.
        """
        
        print(f"📝 Generating draft response for user {responding_user_id}")
        
        # Get relationship and privacy settings
        relationship = await self.network_repo.relationships.get_mutual_relationship(
            requesting_user_id, responding_user_id
        )
        
        if not relationship:
            raise ValueError("Users are not friends")
        
        # Generate the MJ response
        mj_response_data = await self._generate_mj_response(
            from_user_id=requesting_user_id,
            to_user_id=responding_user_id,
            message_purpose=message_purpose,
            privacy_settings=getattr(relationship, 'privacy_settings', {}) or {},
            relationship_type=getattr(relationship, 'relationship_type', 'friend')
        )
        
        # Create draft message (approval_status = 'draft')
        draft_message = await self.network_repo.messages.create_mj_message(
            conversation_id=conversation_id,
            from_user_id=responding_user_id,
            to_user_id=requesting_user_id,
            message_content=mj_response_data["response_content"],
            message_type=MessageType.RESPONSE.value,
            openai_prompt_used=mj_response_data["prompt_used"],
            openai_response_raw=mj_response_data["raw_response"],
            privacy_settings_applied=serialize_for_json(mj_response_data["privacy_settings_applied"]),
            user_memories_used=serialize_for_json(mj_response_data["memories_used"]),
            tokens_used=mj_response_data["tokens_used"],
            approval_status="draft"  # KEY: This is a draft, not sent
        )
        
        print(f"📝 Draft response saved: {draft_message.id}")
        
        return {
            "draft_message": draft_message,
            "response_content": mj_response_data["response_content"],
            "memories_used": mj_response_data["memories_used"],
            "privacy_settings_applied": mj_response_data["privacy_settings_applied"],
            "tokens_used": mj_response_data["tokens_used"]
        }
    
    async def approve_mj_response(self, message_id: int, user_id: int) -> Dict[str, Any]:
        """
        🆕 NEW: Approve a draft response and send it
        """
        
        # Get the draft message
        message = await self.network_repo.messages.get_by_id(message_id)
        if not message:
            raise ValueError("Message not found")
        
        if message.from_user_id != user_id:
            raise ValueError("You can only approve your own MJ's responses")
        
        if message.approval_status != "draft":
            raise ValueError("Message is not a draft")
        
        # Update status to approved and then send
        await self.network_repo.messages.update(message_id, {
            "approval_status": "approved"
        })
        
        # Handle delivery
        target_user_online = await self._check_user_online_status(message.to_user_id) # TODO: Check if target user is online
        
        if target_user_online:
            await self.network_repo.messages.mark_as_delivered(message_id)
            await self.network_repo.mj_registry.increment_stats(
                user_id=message.to_user_id,
                messages_received=1
            )
        else:
            await self.queue_offline_message(message_id, message.to_user_id)
        
        # Update sender statistics
        await self.network_repo.mj_registry.increment_stats(
            user_id=user_id,
            messages_sent=1
        )
        
        # Update conversation
        # Now increment when the draft is approved
        await self.network_repo.conversations.update_last_message(message.conversation_id, increment=True)
        
        print(f"✅ Draft response {message_id} approved and sent")
        
        return {
            "message": message,
            "sent": True,
            "delivered": target_user_online
        }
    
    async def edit_and_approve_response(
        self, 
        message_id: int, 
        user_id: int, 
        new_content: str
    ) -> Dict[str, Any]:
        """
        🆕 NEW: Edit draft response content and then approve it
        """
        
        # Get the draft message
        message = await self.network_repo.messages.get_by_id(message_id)
        if not message:
            raise ValueError("Message not found")
        
        if message.from_user_id != user_id:
            raise ValueError("You can only edit your own MJ's responses")
        
        if message.approval_status != "draft":
            raise ValueError("Message is not a draft")
        
        # Update content and approve
        await self.network_repo.messages.update(message_id, {
            "message_content": new_content,
            "approval_status": "approved"
        })
        
        # Handle delivery (same as approve_mj_response)
        target_user_online = await self._check_user_online_status(message.to_user_id)  # TODO: Check if target user is online
        
        if target_user_online:
            await self.network_repo.messages.mark_as_delivered(message_id)
            await self.network_repo.mj_registry.increment_stats(
                user_id=message.to_user_id,
                messages_received=1
            )
        else:
            await self.queue_offline_message(message_id, message.to_user_id)
        
        # Update sender statistics
        await self.network_repo.mj_registry.increment_stats(
            user_id=user_id,
            messages_sent=1
        )
        
        # Update conversation
        await self.network_repo.conversations.update_last_message(message.conversation_id, increment=True)
        
        print(f"✅ Draft response {message_id} edited and approved")
        
        return {
            "message_id": message_id,
            "new_content": new_content,
            "sent": True,
            "delivered": target_user_online
        }
    
    async def get_pending_responses(self, user_id: int) -> List[Dict[str, Any]]:
        """
        🆕 NEW: Get all draft responses awaiting user approval
        """
        
        # Get all draft messages where this user is the sender
        from sqlalchemy import select
        from ...models.database.mj_network import MJMessage
        
        result = await self.db.execute(
            select(MJMessage)
            .where(MJMessage.from_user_id == user_id)
            .where(MJMessage.approval_status == "draft")
            .order_by(MJMessage.created_at.desc())
        )
        
        draft_messages = result.scalars().all()
        
        pending_responses = []
        for message in draft_messages:
            # Get the original request message to provide context
            original_request = await self.network_repo.messages.get_conversation_messages(
                conversation_id=message.conversation_id,
                limit=10
            )
            
            # Find the request that this draft is responding to
            request_message = None
            for msg in original_request:
                if (msg.from_user_id == message.to_user_id and 
                    msg.to_user_id == message.from_user_id and
                    msg.message_type == MessageType.QUESTION.value):
                    request_message = msg
                    break
            
            pending_responses.append({
                "draft_message_id": message.id,
                "conversation_id": message.conversation_id,
                "requesting_user_id": message.to_user_id,
                "draft_content": message.message_content,
                "original_request": request_message.message_content if request_message else "Unknown request",
                "memories_used": message.user_memories_used,
                "privacy_settings": message.privacy_settings_applied,
                "created_at": message.created_at,
                "tokens_used": message.tokens_used
            })
        
        return pending_responses

    # Keep all existing methods unchanged
    async def _generate_mj_response(
        self,
        from_user_id: int,
        to_user_id: int,
        message_purpose: str,
        privacy_settings: Dict[str, Any],
        relationship_type: str
    ) -> Dict[str, Any]:
        """
        🧠 THE CORE AI GENERATION - Unchanged, still generates responses
        """
        
        print(f"🧠 Generating MJ response with privacy level: {privacy_settings}")
        
        # Step 1: Get target user's memories for context
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
        
        # Step 3: Build MJ-to-MJ prompt
        prompt = PersonalityPrompts.build_mj_to_mj_prompt(
            message_purpose=message_purpose,
            user_context=user_context,
            privacy_settings=privacy_settings,
            relationship_type=relationship_type,
            from_user_id=from_user_id,
            to_user_id=to_user_id
        )
        
        print(f"📝 Built MJ-to-MJ prompt ({len(prompt)} chars)")
        
        # Step 4: Generate response using OpenAI
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
    
    # All other existing methods remain unchanged...
    async def queue_offline_message(self, message_id: int, recipient_user_id: int):
        """📬 Queue message for offline delivery"""
        await self.network_repo.pending_messages.queue_message(
            message_id=message_id,
            recipient_user_id=recipient_user_id
        )
        print(f"📬 Message {message_id} queued for offline delivery to user {recipient_user_id}")
    
    async def deliver_pending_messages(self, user_id: int) -> int:
        """📨 Deliver all pending messages when user comes online"""
        print(f"📨 Delivering pending messages for user {user_id}")
        
        pending_messages = await self.network_repo.pending_messages.get_pending_for_user(user_id)
        delivered_count = 0
        
        for pending in pending_messages:
            try:
                await self.network_repo.messages.mark_as_delivered(pending.message_id)
                await self.network_repo.pending_messages.mark_as_delivered(pending.id)
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
            # Only include sent messages in conversation history, not drafts
            if message.approval_status in ["sent", "approved"]:
                formatted_messages.append({
                    "id": message.id,
                    "from_user_id": message.from_user_id,
                    "to_user_id": message.to_user_id,
                    "content": message.message_content,
                    "message_type": message.message_type,
                    "delivery_status": message.delivery_status,
                    "approval_status": message.approval_status,
                    "created_at": message.created_at,
                    "tokens_used": message.tokens_used,
                    "privacy_level_applied": message.privacy_settings_applied
                })
        
        return formatted_messages