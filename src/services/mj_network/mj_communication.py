# src/services/mj_network/mj_communication.py - MODIFIED FOR DRAFT APPROVAL WORKFLOW
import json
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from ...models.database.user import User
from sqlalchemy import select
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
        objective: str,
        conversation_topic: Optional[str] = None,
        max_turns: int = 10  # ✅ Change from 6 to 10
    ) -> Dict[str, Any]:
        """
        Create a pending auto-chat session that needs objective approval
        """
        
        print(f"Creating pending auto-chat session: User {from_user_id} -> User {to_user_id}")
        print(f"Objective: {objective}")
        
        # Step 1: Validate relationship
        relationship = await self.network_repo.relationships.get_mutual_relationship(from_user_id, to_user_id)
        if not relationship:
            raise ValueError("Users are not friends. Send a friend request first.")
        
        # Step 2: Check if target user is online (required for approval)
        target_mj_registry = await self.network_repo.mj_registry.get_by_user_id(to_user_id)
        if not target_mj_registry or target_mj_registry.status != MJStatus.ONLINE.value:
            raise ValueError("Target user must be online to approve auto-chat objectives")
        
        # Step 3: Create pending session
        conversation = await self.network_repo.conversations.create_pending_session(
            user_a_id=from_user_id,
            user_b_id=to_user_id,
            initiated_by_user_id=from_user_id,
            objective=objective,
            conversation_topic=conversation_topic,
            relationship_id=getattr(relationship, 'id', None)
        )
        
        print(f"Created pending session: {conversation.id}")
        
        return {
            "conversation": conversation,
            "objective": objective,
            "status": "pending_approval",
            "requires_approval_from": to_user_id
        }
    async def approve_objective(self, conversation_id: int, user_id: int, approved: bool = True) -> Dict[str, Any]:

    
        # Get the conversation
        conversation = await self.network_repo.conversations.get_by_id(conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")
        
        # Verify user can approve this objective
        if conversation.user_a_id != user_id and conversation.user_b_id != user_id:
            raise ValueError("You can only approve objectives for your own conversations")
        
        if conversation.initiated_by_user_id == user_id:
            raise ValueError("You cannot approve your own conversation request")
        
        if conversation.session_status != "pending_approval":
            raise ValueError("This conversation is not pending approval")
        
        if not approved:
            # Reject the objective
            await self.network_repo.conversations.end_session(conversation_id, "rejected")
            return {
                "conversation_id": conversation_id,
                "approved": False,
                "status": "rejected"
            }
        
        # Approve and start session
        success = await self.network_repo.conversations.start_auto_session(
            conversation_id=conversation_id,
            approved_by_user_id=user_id,
            objective=conversation.objective,
            max_turns=conversation.max_turns or 10  # ✅ Match the new default
        )
        
        if not success:
            raise ValueError("Failed to start auto-chat session")
        
        # Generate first response immediately
        first_response = await self._generate_auto_response(conversation_id)
        
        print(f"Objective approved and session started: {conversation_id}")
        
        return {
            "conversation_id": conversation_id,
            "approved": True,
            "status": "in_progress",
            "first_response": first_response
        }

    async def _get_user_context(self, user_id: int) -> str:
        """Get user context for prompt building"""
        try:
            # Get basic user info
            from sqlalchemy import select
            from ...models.database.user import User
            
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if user:
                return f"User: {user.username}, joined: {user.created_at.strftime('%Y-%m')}"
            else:
                return f"User ID: {user_id}"
        except Exception as e:
            print(f"Error getting user context: {e}")
            return f"User ID: {user_id}"

    async def _get_user_memories(self, user_id: int) -> List[Any]:
        """Get user memories for prompt building"""
        try:
            memories = await self.memory_repo.get_recent_memories(
                user_id=user_id,
                limit=10,
                days=30
            )
            return memories
        except Exception as e:
            print(f"Error getting user memories: {e}")
            return []
    async def _generate_auto_response(self, conversation_id: int) -> Dict[str, Any]:
        """Generate automatic response for active session"""
        
        try:
            # Get all database data FIRST, before any OpenAI calls
            conversation = await self.network_repo.conversations.get_by_id(conversation_id)
            if not conversation:
                raise ValueError("Conversation not found")
            
            # Get conversation history
            messages = await self.network_repo.messages.get_conversation_messages(
                conversation_id=conversation_id,
                limit=10
            )
            
            # Determine speakers
            if conversation.next_speaker_id:
                from_user_id = conversation.next_speaker_id
                to_user_id = conversation.user_b_id if from_user_id == conversation.user_a_id else conversation.user_a_id
            else:
                from_user_id = conversation.initiated_by_user_id
                to_user_id = conversation.user_b_id if from_user_id == conversation.user_a_id else conversation.user_a_id
            
            # Get relationship and users info
            relationship = await self.network_repo.relationships.get_mutual_relationship(from_user_id, to_user_id)
            
            # Get user context and memories BEFORE OpenAI call
            user_context = await self._get_user_context(from_user_id)
            user_memories = await self._get_user_memories(from_user_id)
            
            # Prepare all data for response generation
            privacy_settings = getattr(relationship, 'privacy_settings', {}) or {}
            relationship_type = getattr(relationship, 'relationship_type', 'friend')
            
            # Now generate response (this can fail without affecting database)
            mj_response_data = await self._generate_mj_response(
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                message_purpose=conversation.objective,
                privacy_settings=privacy_settings,
                relationship_type=relationship_type,
                conversation_id=conversation.id,
                conversation_data={  # Add this new parameter
                    "turn_count": conversation.turn_count or 1,
                    "max_turns": conversation.max_turns or 6,
                    "session_status": conversation.session_status
                }
            )
            
            # Only after successful generation, create the message
            message = await self.network_repo.messages.create_mj_message(
                conversation_id=conversation.id,
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                message_content=mj_response_data["response_content"],
                message_type=MessageType.RESPONSE.value,
                openai_prompt_used=mj_response_data["prompt_used"],
                openai_response_raw=mj_response_data["raw_response"],
                privacy_settings_applied=serialize_for_json(mj_response_data["privacy_settings_applied"]),
                user_memories_used=serialize_for_json(mj_response_data["memories_used"]),
                tokens_used=mj_response_data["tokens_used"],
                approval_status="sent",
                delivery_status=DeliveryStatus.DELIVERED.value
            )
            
            # Update session state
            next_speaker = to_user_id
            await self.network_repo.conversations.advance_turn(conversation.id, next_speaker)  # ✅ Fixed

            # Check completion
            # Check completion - let OpenAI decide + safety limit
            # Check completion - only safety limit, let prompt handle natural ending
            if conversation.turn_count + 1 >= conversation.max_turns:
                await self.network_repo.conversations.end_session(conversation.id, "max_turns_reached")
            
            # Update stats
            await self.network_repo.mj_registry.increment_stats(user_id=from_user_id, messages_sent=1)
            await self.network_repo.mj_registry.increment_stats(user_id=to_user_id, messages_received=1)
            
            return {
                "message": message,
                "from_user_id": from_user_id,
                "to_user_id": to_user_id,
                "turn_count": conversation.turn_count + 1,
                "session_status": "completed" if conversation.turn_count + 1 >= conversation.max_turns else "in_progress"
            }
            
        except Exception as e:
            # Log the error but don't let it crash the approval process
            print(f"Failed to generate auto response: {e}")
            raise e
        
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
    
    async def get_pending_approvals(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get objectives pending approval for this user
        """
        
        pending_conversations = await self.network_repo.conversations.get_pending_approvals_for_user(user_id)
        
        pending_approvals = []
        for conversation in pending_conversations:
            pending_approvals.append({
                "conversation_id": conversation.id,
                "objective": conversation.objective,
                "conversation_topic": conversation.conversation_topic,
                "initiated_by_user_id": conversation.initiated_by_user_id,
                "max_turns": conversation.max_turns,
                "created_at": conversation.created_at
            })
        
        return pending_approvals

    # Keep all existing methods unchanged
    async def _generate_mj_response(
        self,
        from_user_id: int,
        to_user_id: int,
        message_purpose: str,
        privacy_settings: Dict[str, Any],
        relationship_type: str,
        conversation_id: Optional[int] = None,
        conversation_data: Optional[Dict[str, Any]] = None  # Add this
    ) -> Dict[str, Any]:
        """
        🧠 THE CORE AI GENERATION - Unchanged, still generates responses
        """
        
        print(f"🧠 Generating MJ response with privacy level: {privacy_settings}")
        
        # Step 1: Get target user's memories for context
        try:
            speaker_user_memories = await self.memory_repo.get_recent_memories(
                user_id=from_user_id, 
                limit=10,
                days=30
            )
            print(f"💭 Found {len(speaker_user_memories)} memories for context")

        except Exception as e:
            print(f"⚠️ Memory retrieval failed: {e}")
            speaker_user_memories = []

        
        # Step 2: Build context from memories
        context_parts = []
        memories_used = []
        
        for memory in speaker_user_memories:
            # Include context in the formatted string if available
            if hasattr(memory, 'context') and memory.context:
                context_parts.append(f"- {memory.fact} (context: {memory.context}, confidence: {memory.confidence})")
            else:
                context_parts.append(f"- {memory.fact} (confidence: {memory.confidence})")
            
            memories_used.append({
                "id": memory.id,
                "fact": memory.fact,
                "category": memory.category,
                "confidence": memory.confidence,
                "context": getattr(memory, 'context', None)  # Add context field
            })
        
        user_context = "\n".join(context_parts) if context_parts else "No specific memories available."
        
        # Step 3: Build MJ-to-MJ prompt
        # Get usernames for the prompt
        # Get usernames for the prompt
        from_user = await self.db.execute(select(User).where(User.id == from_user_id))
        to_user = await self.db.execute(select(User).where(User.id == to_user_id))

        from_user_obj = from_user.scalar_one_or_none()
        to_user_obj = to_user.scalar_one_or_none()

        from_username = from_user_obj.username if from_user_obj else f"User{from_user_id}"
        to_username = to_user_obj.username if to_user_obj else f"User{to_user_id}"

        # Get conversation history properly
        # Get conversation history properly
        # This method doesn't have access to conversation_id, so we need to pass it
        # For now, we'll skip conversation history in this legacy method
        # Get conversation history (if conversation_id is provided)
        if conversation_id:
            conversation_messages = await self.network_repo.messages.get_conversation_messages(
                conversation_id=conversation_id,
                limit=10
            )
        else:
            conversation_messages = []

        # Format conversation history for the prompt
        formatted_history = []
        for msg in conversation_messages:
            speaker = from_username if msg.from_user_id == from_user_id else to_username
            formatted_history.append(f"{speaker}: {msg.message_content}")

        history_text = "\n".join(formatted_history) if formatted_history else "This is the start of your conversation."

        # Format memories for the prompt
        # Format memories for the prompt
        formatted_memories = []
        for memory in speaker_user_memories:
            formatted_memories.append({
                "fact": memory.fact,
                "confidence": memory.confidence,
                "context": getattr(memory, 'context', None)  # Add context here too
            })

# Use legacy prompt parameters since we don't have conversation object here
        prompt = PersonalityPrompts.build_mj_to_mj_prompt(
            objective=message_purpose,
            conversation_history=history_text,
            user_context=user_context,
            user_memories=formatted_memories,
            privacy_settings=privacy_settings,
            relationship_type=relationship_type,
            turn_count=conversation_data["turn_count"] if conversation_data else 1,
            max_turns=conversation_data["max_turns"] if conversation_data else 10,
            current_speaker_name=from_username,
            other_speaker_name=to_username,
            session_status=conversation_data["session_status"] if conversation_data else "in_progress"
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
        
        # Get conversation history
        messages = await self.network_repo.messages.get_conversation_messages(
            conversation_id=conversation.id,  # ✅ Use conversation.id
            limit=10
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