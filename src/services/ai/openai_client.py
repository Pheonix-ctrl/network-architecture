# src/services/ai/openai_client.py
from openai import AsyncOpenAI
from typing import List, Dict, Optional, Any
import asyncio
import json
from ...config.settings import Settings
from ...models.schemas.chat import PersonalityMode

settings = Settings()

class OpenAIClient:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        mode: PersonalityMode = PersonalityMode.MJ,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate chat completion with optional tool calling"""
        try:
            completion_params = {
                "model": self.model,
                "messages": messages,
                "temperature": self._get_temperature_for_mode(mode),
                "max_tokens": kwargs.get("max_tokens", 1000),
                **kwargs
            }
            
            if tools:
                completion_params["tools"] = tools
                completion_params["tool_choice"] = "auto"
            
            response = await self.client.chat.completions.create(**completion_params)
            
            return {
                "content": response.choices[0].message.content,
                "tool_calls": response.choices[0].message.tool_calls,
                "tokens": {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                },
                "model": response.model
            }
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    async def get_embeddings(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small"
    ) -> List[List[float]]:
        """Get embeddings for texts"""
        try:
            response = await self.client.embeddings.create(
                model=model,
                input=texts
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            raise Exception(f"OpenAI Embeddings error: {str(e)}")
    
    def _get_temperature_for_mode(self, mode: PersonalityMode) -> float:
        """Get temperature setting for different personality modes"""
        temperature_map = {
            PersonalityMode.MJ: 0.8,
            PersonalityMode.KALKI: 0.3,  # More deterministic for crisis
            PersonalityMode.JUPITER: 0.9,  # More creative for emotional support
            PersonalityMode.EDUCATIONAL: 0.5,  # Balanced for teaching
            PersonalityMode.HEALTHCARE: 0.2,  # Very careful for health
        }
        return temperature_map.get(mode, 0.7)

