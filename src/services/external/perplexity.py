import os
import requests
from dotenv import load_dotenv

# === Load API Keys from .env ===
load_dotenv()
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

async def get_web_data(user_message: str) -> str:
    """Return web search results only - NO personality, just raw data"""
    try:
        print(f"🔍 Getting web data for: {user_message}")
        
        # Get raw search results
        search_result = search_web(user_message)
        
        if search_result.startswith("Search") and "error" in search_result.lower():
            return "WEB SEARCH ERROR: Unable to get current information from web search service."
        
        # Return with clear prefix
        return f"WEB SEARCH RESULTS: {search_result}"
        
    except Exception as e:
        return f"WEB SEARCH ERROR: {str(e)}"

def search_web(query: str) -> str:
    """Get raw web search results from Perplexity - no processing"""
    print(f"🔍 SEARCHING PERPLEXITY: {query}")
    
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    
    data = {
        "model": "sonar-pro",
        "messages": [
            {"role": "user", "content": query}
        ],
        "max_tokens": 300,
        "temperature": 0.1
    }

    try:
        response = requests.post(PERPLEXITY_URL, headers=headers, json=data, timeout=15)
        print(f"🔍 PERPLEXITY STATUS: {response.status_code}")
        
        if response.status_code != 200:
            print(f"🔍 PERPLEXITY ERROR: {response.text}")
            return f"Search failed with status {response.status_code}"
        
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"]
            print(f"🔍 PERPLEXITY SUCCESS: {content[:100]}...")
            return content
        else:
            return "No search results found for that query"
            
    except Exception as e:
        print(f"🔍 PERPLEXITY EXCEPTION: {e}")
        return f"Search error: {str(e)}"

# Legacy functions - keep for compatibility but redirect
async def handle_web_question(user_message: str, context: str, openai_client) -> str:
    """Legacy function - redirects to data-only approach"""
    return await get_web_data(user_message)