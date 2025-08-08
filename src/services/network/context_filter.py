
# src/services/network/context_filter.py
from typing import Dict, Any, List, Optional
from ...models.database.relationship import Relationship
from ...database.repositories.relationship import RelationshipRepository
from sqlalchemy.ext.asyncio import AsyncSession

class ContextFilter:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.relationship_repo = RelationshipRepository(db)
    
    async def filter_context_for_mj_talk(
        self,
        from_user_id: int,
        to_mj_id: str,
        content: str,
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Filter context based on relationship between users"""
        
        # Get relationship between users
        relationship = await self.relationship_repo.get_by_mj_id(from_user_id, to_mj_id)
        
        if not relationship:
            # No relationship = minimal sharing (basic/stranger level)
            return await self._apply_stranger_filter(content, context_data)
        
        share_level = relationship.share_level
        restricted_topics = relationship.restricted_topics or []
        
        if share_level == "basic":
            return await self._apply_basic_filter(content, context_data, restricted_topics)
        elif share_level == "moderate":
            return await self._apply_moderate_filter(content, context_data, restricted_topics)
        elif share_level == "full":
            return await self._apply_full_filter(content, context_data, restricted_topics)
        else:
            return await self._apply_stranger_filter(content, context_data)
    
    async def _apply_stranger_filter(
        self,
        content: str,
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply strictest filtering for strangers/unknown MJs"""
        
        # Only share very basic info
        filtered_context = {
            "user_status": "online",  # Just that they're active
            "general_mood": self._extract_general_mood(content),
            "location_general": "city_level_only",  # Never specific location
            "activity_type": self._extract_activity_type(content)  # General activity
        }
        
        # Filter content to remove personal details
        filtered_content = await self._remove_personal_details(content)
        
        return {
            "filtered_content": filtered_content,
            "context": filtered_context,
            "filter_level": "stranger"
        }
    
    async def _apply_basic_filter(
        self,
        content: str,
        context_data: Dict[str, Any],
        restricted_topics: List[str]
    ) -> Dict[str, Any]:
        """Apply basic filtering for acquaintances/colleagues"""
        
        filtered_context = {
            "user_status": context_data.get("user_status", "online"),
            "general_mood": self._extract_general_mood(content),
            "recent_activities": self._filter_activities(
                context_data.get("recent_activities", []),
                level="basic"
            ),
            "interests": context_data.get("general_interests", []),
            "work_status": context_data.get("work_status")  # If colleague
        }
        
        # Remove restricted topics
        filtered_content = await self._remove_restricted_topics(content, restricted_topics)
        
        return {
            "filtered_content": filtered_content,
            "context": filtered_context,
            "filter_level": "basic"
        }
    
    async def _apply_moderate_filter(
        self,
        content: str,
        context_data: Dict[str, Any],
        restricted_topics: List[str]
    ) -> Dict[str, Any]:
        """Apply moderate filtering for friends"""
        
        filtered_context = {
            "user_status": context_data.get("user_status"),
            "detailed_mood": context_data.get("current_mood"),
            "recent_activities": self._filter_activities(
                context_data.get("recent_activities", []),
                level="moderate"
            ),
            "interests": context_data.get("interests", []),
            "life_updates": context_data.get("recent_life_events", []),
            "social_context": context_data.get("social_status")
        }
        
        # Still remove restricted topics but allow more personal sharing
        filtered_content = await self._remove_restricted_topics(content, restricted_topics)
        
        return {
            "filtered_content": filtered_content,
            "context": filtered_context,
            "filter_level": "moderate"
        }
    
    async def _apply_full_filter(
        self,
        content: str,
        context_data: Dict[str, Any],
        restricted_topics: List[str]
    ) -> Dict[str, Any]:
        """Apply minimal filtering for family/closest friends"""
        
        # Share most context, only filter explicitly restricted topics
        filtered_context = context_data.copy()
        
        # Remove only specifically restricted topics
        filtered_content = await self._remove_restricted_topics(content, restricted_topics)
        
        return {
            "filtered_content": filtered_content,
            "context": filtered_context,
            "filter_level": "full"
        }
    
    def _extract_general_mood(self, content: str) -> str:
        """Extract general mood from content without details"""
        # Simplified mood extraction
        positive_words = ["happy", "good", "great", "excited", "wonderful"]
        negative_words = ["sad", "bad", "terrible", "angry", "frustrated"]
        
        content_lower = content.lower()
        
        positive_score = sum(1 for word in positive_words if word in content_lower)
        negative_score = sum(1 for word in negative_words if word in content_lower)
        
        if positive_score > negative_score:
            return "positive"
        elif negative_score > positive_score:
            return "negative"
        else:
            return "neutral"
    
    def _extract_activity_type(self, content: str) -> str:
        """Extract general activity type"""
        # Map activities to general categories
        activity_keywords = {
            "work": ["working", "office", "meeting", "project", "deadline"],
            "social": ["friends", "party", "dinner", "hanging out"],
            "leisure": ["reading", "watching", "playing", "relaxing"],
            "exercise": ["gym", "running", "workout", "sports"],
            "travel": ["trip", "vacation", "flight", "hotel"]
        }
        
        content_lower = content.lower()
        
        for activity, keywords in activity_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                return activity
        
        return "general"
    
    def _filter_activities(self, activities: List[str], level: str) -> List[str]:
        """Filter activities based on sharing level"""
        if level == "basic":
            # Only general activity types
            return [self._generalize_activity(activity) for activity in activities[:3]]
        elif level == "moderate":
            # More specific but still filtered
            return [activity for activity in activities[:5] 
                   if not self._is_too_personal(activity)]
        else:
            return activities
    
    def _generalize_activity(self, activity: str) -> str:
        """Convert specific activity to general category"""
        # This would implement logic to generalize activities
        # e.g., "went to dinner with Sarah" -> "social dining"
        return activity  # Simplified
    
    def _is_too_personal(self, activity: str) -> bool:
        """Check if activity is too personal for moderate sharing"""
        personal_keywords = ["therapy", "doctor", "medication", "private", "intimate"]
        return any(keyword in activity.lower() for keyword in personal_keywords)
    
    async def _remove_personal_details(self, content: str) -> str:
        """Remove personal details from content"""
        # This would implement NLP to remove names, addresses, phone numbers, etc.
        # For now, simplified version
        import re
        
        # Remove potential phone numbers
        content = re.sub(r'\b\d{3}-\d{3}-\d{4}\b', '[PHONE]', content)
        # Remove potential addresses
        content = re.sub(r'\b\d+\s+[\w\s]+\s+(Street|St|Avenue|Ave|Road|Rd)\b', '[ADDRESS]', content)
        # Remove email addresses
        content = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', content)
        
        return content
    
    async def _remove_restricted_topics(self, content: str, restricted_topics: List[str]) -> str:
        """Remove content related to restricted topics"""
        filtered_content = content
        
        for topic in restricted_topics:
            # Simple keyword-based filtering
            # In production, would use more sophisticated NLP
            if topic.lower() in content.lower():
                filtered_content = filtered_content.replace(topic, f"[FILTERED: {topic.upper()}]")
        
        return filtered_content
