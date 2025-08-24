# src/services/mj_network/friend_management.py - FIXED VERSION
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ...database.repositories.mj_network import MJNetworkRepository  # ← FIXED: Updated import path
from ...models.database.mj_network import FriendRequestStatus, RelationshipStatus  # ← FIXED: Updated import path

class FriendManagementService:
    """Service for managing friend requests and relationships"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.network_repo = MJNetworkRepository(db)
    
    async def send_friend_request(
        self,
        from_user_id: int,
        to_user_id: int,
        request_message: Optional[str] = None,
        suggested_relationship_type: str = "friend",
        discovery_method: str = "manual"
    ) -> Any:
        """Send a friend request"""
        
        # Check if users are already friends
        existing_relationship = await self.network_repo.relationships.get_mutual_relationship(from_user_id, to_user_id)
        if existing_relationship:
            raise ValueError("Users are already friends")
        
        # Check if request already exists
        existing_request = await self.network_repo.friend_requests.get_existing_request(from_user_id, to_user_id)
        if existing_request:
            raise ValueError("Friend request already sent")
        
        # Check reverse request
        reverse_request = await self.network_repo.friend_requests.get_existing_request(to_user_id, from_user_id)
        if reverse_request:
            raise ValueError("This user has already sent you a friend request. Please respond to their request instead.")
        
        # Create friend request
        request_data = {
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "request_message": request_message,
            "suggested_relationship_type": suggested_relationship_type,
            "discovery_method": discovery_method
        }
        
        friend_request = await self.network_repo.friend_requests.create(request_data)
        
        print(f"👥 Friend request sent from user {from_user_id} to user {to_user_id}")
        
        return friend_request
    
    async def accept_friend_request(
        self,
        request_id: int,
        accepting_user_id: int,
        relationship_type: Optional[str] = None,
        response_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Accept a friend request and create mutual relationship"""
        
        # Get the friend request
        friend_request = await self.network_repo.friend_requests.get_by_id(request_id)
        if not friend_request:
            raise ValueError("Friend request not found")
        
        if friend_request.to_user_id != accepting_user_id:
            raise ValueError("You can only accept requests sent to you")
        
        if friend_request.status != FriendRequestStatus.PENDING.value:
            raise ValueError(f"Friend request is already {friend_request.status}")

        
        # Accept the request
        await self.network_repo.friend_requests.accept_request(request_id, response_message)
        
        # Use suggested relationship type if none provided
        final_relationship_type = relationship_type or friend_request.suggested_relationship_type
        
        # Get default privacy settings based on relationship type
        privacy_settings = self._get_default_privacy_settings(final_relationship_type)
        
        # Create mutual relationships
        rel_a_to_b, rel_b_to_a = await self.network_repo.relationships.create_mutual_relationship(
            user_a_id=friend_request.from_user_id,
            user_b_id=friend_request.to_user_id,
            relationship_type=final_relationship_type,
            privacy_settings=privacy_settings
        )
        
        print(f"✅ Friend request accepted: users {friend_request.from_user_id} and {friend_request.to_user_id} are now friends")
        
        return {
            "friend_request": friend_request,
            "relationship": rel_a_to_b,
            "mutual_relationship": rel_b_to_a
        }
    
    async def reject_friend_request(
        self,
        request_id: int,
        rejecting_user_id: int,
        response_message: Optional[str] = None
    ) -> Any:
        """Reject a friend request"""
        
        # Get the friend request
        friend_request = await self.network_repo.friend_requests.get_by_id(request_id)
        if not friend_request:
            raise ValueError("Friend request not found")
        
        if friend_request.to_user_id != rejecting_user_id:
            raise ValueError("You can only reject requests sent to you")
        
        if friend_request.status != FriendRequestStatus.PENDING:
            raise ValueError(f"Friend request is already {friend_request.status}")
        
        # Reject the request
        rejected_request = await self.network_repo.friend_requests.reject_request(request_id, response_message)
        
        print(f"❌ Friend request rejected: {friend_request.from_user_id} -> {friend_request.to_user_id}")
        
        return rejected_request
    
    async def cancel_friend_request(
        self,
        request_id: int,
        cancelling_user_id: int
    ) -> Any:
        """Cancel a sent friend request"""
        
        friend_request = await self.network_repo.friend_requests.get_by_id(request_id)
        if not friend_request:
            raise ValueError("Friend request not found")
        
        if friend_request.from_user_id != cancelling_user_id:
            raise ValueError("You can only cancel requests you sent")
        
        if friend_request.status != FriendRequestStatus.PENDING:
            raise ValueError(f"Friend request is already {friend_request.status}")
        
        # Update status to cancelled
        updated_request = await self.network_repo.friend_requests.update(request_id, {
            "status": FriendRequestStatus.CANCELLED.value,
            "responded_at": datetime.utcnow()
        })


        
        print(f"🚫 Friend request cancelled: {friend_request.from_user_id} -> {friend_request.to_user_id}")
        
        return updated_request
    
    async def remove_friend(
        self,
        user_id: int,
        friend_user_id: int
    ) -> bool:
        """Remove friend relationship (both directions)"""
        
        # Get both relationships
        rel_a_to_b = await self.network_repo.relationships.get_relationship(user_id, friend_user_id)
        rel_b_to_a = await self.network_repo.relationships.get_relationship(friend_user_id, user_id)
        
        if not rel_a_to_b and not rel_b_to_a:
            raise ValueError("No friendship found between these users")
        
        # Delete both relationships
        if rel_a_to_b:
            await self.network_repo.relationships.delete(rel_a_to_b.id)
        
        if rel_b_to_a:
            await self.network_repo.relationships.delete(rel_b_to_a.id)
        
        print(f"💔 Friendship removed between users {user_id} and {friend_user_id}")
        
        return True
    
    async def block_user(
        self,
        blocking_user_id: int,
        blocked_user_id: int
    ) -> bool:
        """Block a user (update relationship status to blocked)"""
        
        relationship = await self.network_repo.relationships.get_relationship(blocking_user_id, blocked_user_id)
        if not relationship:
            # Create a blocked relationship even if they weren't friends
            block_data = {
                "user_id": blocking_user_id,
                "friend_user_id": blocked_user_id,
                "relationship_type": "blocked",
                "status": RelationshipStatus.BLOCKED.value,
                "privacy_settings": self._get_blocked_privacy_settings()
            }
            await self.network_repo.relationships.create(block_data)
        else:
            # Update existing relationship to blocked
            await self.network_repo.relationships.update(relationship.id, {
                "status": RelationshipStatus.BLOCKED.value,
                "privacy_settings": self._get_blocked_privacy_settings()
            })
        
        print(f"🚫 User {blocked_user_id} blocked by user {blocking_user_id}")
        
        return True
    
    async def unblock_user(
        self,
        unblocking_user_id: int,
        unblocked_user_id: int
    ) -> bool:
        """Unblock a user"""
        
        relationship = await self.network_repo.relationships.get_relationship(unblocking_user_id, unblocked_user_id)
        if not relationship or relationship.status != RelationshipStatus.BLOCKED.value:
            raise ValueError("User is not blocked")
        
        # Remove the blocked relationship
        await self.network_repo.relationships.delete(relationship.id)
        
        print(f"✅ User {unblocked_user_id} unblocked by user {unblocking_user_id}")
        
        return True
    
    async def update_relationship_type(
        self,
        user_id: int,
        friend_user_id: int,
        new_relationship_type: str
    ) -> bool:
        """Update the relationship type between two users"""
        
        # Update both directions
        rel_a_to_b = await self.network_repo.relationships.get_relationship(user_id, friend_user_id)
        rel_b_to_a = await self.network_repo.relationships.get_relationship(friend_user_id, user_id)
        
        if not rel_a_to_b or not rel_b_to_a:
            raise ValueError("Friendship not found")
        
        # Update relationship type for both
        await self.network_repo.relationships.update(rel_a_to_b.id, {
            "relationship_type": new_relationship_type
        })
        
        await self.network_repo.relationships.update(rel_b_to_a.id, {
            "relationship_type": new_relationship_type
        })
        
        print(f"🔄 Relationship type updated to '{new_relationship_type}' between users {user_id} and {friend_user_id}")
        
        return True
    
    async def get_mutual_friends(
        self,
        user_a_id: int,
        user_b_id: int
    ) -> list:
        """Get mutual friends between two users"""
        
        # Get friends of user A
        friends_a = await self.network_repo.relationships.get_user_friends(user_a_id)
        friend_ids_a = {f.friend_user_id for f in friends_a}
        
        # Get friends of user B
        friends_b = await self.network_repo.relationships.get_user_friends(user_b_id)
        friend_ids_b = {f.friend_user_id for f in friends_b}
        
        # Find intersection
        mutual_friend_ids = friend_ids_a & friend_ids_b
        
        # Get detailed info for mutual friends
        mutual_friends = []
        for friend_id in mutual_friend_ids:
            # Find the relationship object from either list
            friend_info = next((f for f in friends_a if f.friend_user_id == friend_id), None)
            if friend_info:
                mutual_friends.append(friend_info)
        
        return mutual_friends
    
    def _get_default_privacy_settings(self, relationship_type: str) -> Dict[str, Any]:
        """Get default privacy settings based on relationship type"""
        
        privacy_defaults = {
            "friend": {
                "share_mood": True,
                "share_activity": True,
                "share_health": False,
                "share_life_events": True,
                "share_work": True,
                "share_location": False,
                "custom_categories": {}
            },
            "family": {
                "share_mood": True,
                "share_activity": True,
                "share_health": True,
                "share_life_events": True,
                "share_work": True,
                "share_location": True,
                "custom_categories": {}
            },
            "parent": {
                "share_mood": True,
                "share_activity": True,
                "share_health": True,
                "share_life_events": True,
                "share_work": True,
                "share_location": True,
                "custom_categories": {}
            },
            "sibling": {
                "share_mood": True,
                "share_activity": True,
                "share_health": True,
                "share_life_events": True,
                "share_work": True,
                "share_location": False,
                "custom_categories": {}
            },
            "colleague": {
                "share_mood": False,
                "share_activity": False,
                "share_health": False,
                "share_life_events": False,
                "share_work": True,
                "share_location": False,
                "custom_categories": {}
            },
            "acquaintance": {
                "share_mood": False,
                "share_activity": False,
                "share_health": False,
                "share_life_events": False,
                "share_work": False,
                "share_location": False,
                "custom_categories": {}
            }
        }
        
        return privacy_defaults.get(relationship_type, privacy_defaults["friend"])
    
    def _get_blocked_privacy_settings(self) -> Dict[str, Any]:
        """Get privacy settings for blocked users (share nothing)"""
        
        return {
            "share_mood": False,
            "share_activity": False,
            "share_health": False,
            "share_life_events": False,
            "share_work": False,
            "share_location": False,
            "custom_categories": {}
        }
    
    async def get_friendship_suggestions(
        self,
        user_id: int,
        limit: int = 10
    ) -> list:
        """Get friend suggestions based on mutual friends and proximity"""
        
        # Get user's current friends
        current_friends = await self.network_repo.relationships.get_user_friends(user_id)
        current_friend_ids = {f.friend_user_id for f in current_friends}
        current_friend_ids.add(user_id)  # Exclude self
        
        suggestions = []
        
        # Find users with mutual friends
        for friend in current_friends:
            mutual_friends = await self.network_repo.relationships.get_user_friends(friend.friend_user_id)
            
            for mutual_friend in mutual_friends:
                if mutual_friend.friend_user_id not in current_friend_ids:
                    # Check if already suggested
                    if not any(s["user_id"] == mutual_friend.friend_user_id for s in suggestions):
                        suggestions.append({
                            "user_id": mutual_friend.friend_user_id,
                            "username": mutual_friend.friend.username,
                            "mj_instance_id": mutual_friend.friend.mj_instance_id,
                            "suggestion_reason": f"Mutual friend: {friend.friend.username}",
                            "mutual_friends_count": 1
                        })
                    else:
                        # Increment mutual friends count
                        for s in suggestions:
                            if s["user_id"] == mutual_friend.friend_user_id:
                                s["mutual_friends_count"] += 1
                                s["suggestion_reason"] = f"{s['mutual_friends_count']} mutual friends"
                                break
        
        # Sort by mutual friends count
        suggestions.sort(key=lambda x: x["mutual_friends_count"], reverse=True)
        
        return suggestions[:limit]
    
    async def update_relationship_privacy_settings(
        self,
        user_id: int,
        friend_user_id: int,
        privacy_settings: Dict[str, Any]
    ) -> bool:
        """Update privacy settings for a specific relationship"""
        
        # Only update the user's own privacy settings for this relationship
        # (not the mutual relationship)
        success = await self.network_repo.relationships.update_privacy_settings(
            user_id=user_id,
            friend_user_id=friend_user_id,
            privacy_settings=privacy_settings
        )
        
        if success:
            print(f"🔒 Privacy settings updated for relationship: user {user_id} -> user {friend_user_id}")
        
        return success
    
    async def get_relationship_status(
        self,
        user_id: int,
        other_user_id: int
    ) -> Dict[str, Any]:
        """Get comprehensive relationship status between two users"""
        
        # Check for existing relationship
        relationship = await self.network_repo.relationships.get_mutual_relationship(user_id, other_user_id)
        
        # Check for pending friend requests
        sent_request = await self.network_repo.friend_requests.get_existing_request(user_id, other_user_id)
        received_request = await self.network_repo.friend_requests.get_existing_request(other_user_id, user_id)
        
        return {
            "is_friend": relationship is not None and relationship.status == RelationshipStatus.ACTIVE,
            "is_blocked": relationship is not None and relationship.status == RelationshipStatus.BLOCKED,
            "relationship_type": relationship.relationship_type if relationship else None,
            "trust_level": float(relationship.trust_level) if relationship else None,
            "has_sent_request": sent_request is not None,
            "has_received_request": received_request is not None,
            "can_send_request": (
                relationship is None and 
                sent_request is None and 
                received_request is None
            ),
            "relationship_id": relationship.id if relationship else None
        }
    
    async def get_user_relationship_stats(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive relationship statistics for a user"""
        
        # Get all relationships
        all_relationships = await self.network_repo.relationships.get_user_friends(user_id, status="active")
        
        # Get pending requests
        pending_sent = await self.network_repo.friend_requests.get_sent_requests_by_user(user_id)
        pending_received = await self.network_repo.friend_requests.get_pending_requests_for_user(user_id)
        
        # Categorize relationships by type
        relationship_types = {}
        for rel in all_relationships:
            rel_type = rel.relationship_type
            if rel_type not in relationship_types:
                relationship_types[rel_type] = 0
            relationship_types[rel_type] += 1
        
        # Calculate average trust level
        total_trust = sum(float(rel.trust_level) for rel in all_relationships)
        avg_trust = total_trust / len(all_relationships) if all_relationships else 0.0
        
        return {
            "total_friends": len(all_relationships),
            "pending_sent_requests": len(pending_sent),
            "pending_received_requests": len(pending_received),
            "relationship_types": relationship_types,
            "average_trust_level": avg_trust,
            "most_trusted_friends": [
                {
                    "user_id": rel.friend_user_id,
                    "username": rel.friend.username,
                    "trust_level": float(rel.trust_level),
                    "relationship_type": rel.relationship_type
                }
                for rel in sorted(all_relationships, key=lambda x: x.trust_level, reverse=True)[:5]
            ]
        }