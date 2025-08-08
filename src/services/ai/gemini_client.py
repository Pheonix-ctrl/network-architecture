# src/services/ai/gemini_client.py
import google.generativeai as genai
from typing import List, Dict, Optional,Any
import json
from ...config.settings import Settings

settings = Settings()
genai.configure(api_key=settings.GEMINI_API_KEY)

class GeminiClient:
    def __init__(self):
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
    
    async def extract_memories(
        self,
        conversation_text: str,
        user_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Extract memories from conversation using Gemini"""
        
        prompt = f"""
        Analyze this conversation and extract ONLY high-quality, factual information about the user.
        
        Focus on:
        1. Personal preferences (likes, dislikes, favorites)
        2. Personal information (work, location, hobbies, relationships)
        3. Skills and expertise mentioned
        4. Important life facts or events
        5. Goals or plans mentioned
        
        CRITICAL RULES:
        - Extract ONLY factual, verifiable information
        - Avoid temporary emotions or casual statements
        - Be selective - quality over quantity (max 5 facts)
        - Normalize facts to consistent format
        - Provide realistic confidence scores (0.7-1.0)
        
        {f"User Context: {user_context}" if user_context else ""}
        
        Conversation:
        {conversation_text}
        
        Return a JSON array with this exact structure:
        [
            {{
                "fact": "Clear, normalized fact about the user",
                "memory_type": "personal|preference|skill|goal|relationship",
                "category": "work|hobbies|relationships|preferences|skills|etc",
                "confidence": 0.7-1.0,
                "importance": 0.1-1.0,
                "context": "Brief context about when/how this was mentioned",
                "relevance_tags": ["tag1", "tag2"]
            }}
        ]
        
        Return empty array if no significant facts found.
        """
        
        try:
            response = await self.model.generate_content_async(prompt)
            
            # Extract JSON from response
            response_text = response.text.strip()
            if not response_text:
                return []
            
            # Find JSON array in response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                return []
            
            json_str = response_text[start_idx:end_idx]
            memories = json.loads(json_str)
            
            # Validate and clean memories
            validated_memories = []
            for memory in memories:
                if self._validate_memory(memory):
                    validated_memories.append(memory)
            
            return validated_memories
            
        except Exception as e:
            print(f"Gemini memory extraction error: {e}")
            return []
    
    def _validate_memory(self, memory: Dict) -> bool:
        """Validate memory structure and content"""
        required_fields = ['fact', 'memory_type', 'confidence']
        
        # Check required fields
        for field in required_fields:
            if field not in memory:
                return False
        
        # Validate fact length
        if not memory['fact'] or len(memory['fact'].strip()) < 5:
            return False
        
        # Validate memory type
        valid_types = ['personal', 'preference', 'skill', 'goal', 'relationship']
        if memory['memory_type'] not in valid_types:
            return False
        
        # Validate confidence
        try:
            confidence = float(memory['confidence'])
            if not (0.0 <= confidence <= 1.0):
                return False
        except (ValueError, TypeError):
            return False
        
        return True
