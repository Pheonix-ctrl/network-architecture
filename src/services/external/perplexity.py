
# src/services/external/perplexity.py
import aiohttp
import json
from typing import Dict, Any, Optional
from ...config.settings import Settings

settings = Settings()

class PerplexityClient:
    """Client for Perplexity AI real-time search"""
    
    def __init__(self):
        self.api_key = settings.PERPLEXITY_API_KEY
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.model = settings.PERPLEXITY_MODEL
        self.timeout = 30
    
    async def search(self, query: str, max_tokens: int = 400) -> str:
        """Search for real-time information using Perplexity"""
        
        if not self.api_key:
            return "Real-time search is not available (API key not configured)."
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that provides accurate, up-to-date information. Keep responses concise and cite sources when possible."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "top_p": 0.9,
            "return_citations": True,
            "search_domain_filter": ["perplexity.ai"],
            "return_images": False,
            "return_related_questions": False
        }
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.base_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # Extract content from response
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        # Add citations if available
                        citations = result.get("citations", [])
                        if citations:
                            content += "\n\nSources:"
                            for i, citation in enumerate(citations[:3], 1):
                                content += f"\n{i}. {citation}"
                        
                        return content or "No information found for this query."
                    
                    else:
                        error_text = await response.text()
                        print(f"Perplexity API error {response.status}: {error_text}")
                        return "Sorry, I couldn't retrieve real-time information right now."
        
        except aiohttp.ClientError as e:
            print(f"Perplexity connection error: {e}")
            return "Sorry, I'm having trouble connecting to real-time information sources."
        
        except json.JSONDecodeError as e:
            print(f"Perplexity JSON decode error: {e}")
            return "Sorry, I received an invalid response from the information source."
        
        except Exception as e:
            print(f"Perplexity unexpected error: {e}")
            return "Sorry, an unexpected error occurred while searching for information."
    
    async def search_with_context(
        self,
        query: str,
        context: str,
        max_tokens: int = 400
    ) -> str:
        """Search with additional context for better results"""
        
        enhanced_query = f"Context: {context}\n\nQuery: {query}"
        return await self.search(enhanced_query, max_tokens)
    
    async def get_current_events(self, topic: str = "world news") -> str:
        """Get current events on a specific topic"""
        
        query = f"What are the latest {topic} from today? Please provide a brief summary of the most important recent developments."
        return await self.search(query)
    
    async def get_weather(self, location: str) -> str:
        """Get current weather for a location"""
        
        query = f"What is the current weather in {location}? Include temperature, conditions, and any weather alerts."
        return await self.search(query)
    
    async def get_stock_price(self, symbol: str) -> str:
        """Get current stock price and basic information"""
        
        query = f"What is the current stock price and recent performance of {symbol}?"
        return await self.search(query)
    
    async def verify_fact(self, fact: str) -> str:
        """Verify or fact-check a statement"""
        
        query = f"Please verify this information and provide accurate, up-to-date details: {fact}"
        return await self.search(query)

# Create singleton instance for easy import
perplexity_client = PerplexityClient()
