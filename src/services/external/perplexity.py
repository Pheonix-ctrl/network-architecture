# perplexity.py - FIXED: Pure MJ Web Search
import requests
from ..ai.personality.prompts import PersonalityPrompts

PERPLEXITY_API_KEY = "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"
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

async def handle_web_question(user_message: str, context: str, openai_client) -> str:
    """Pure MJ web search responses"""
    print(f"🌐 PERPLEXITY handling: {user_message}")
    
    # Get web data first
    web_data = search_web(user_message)
    print(f"🌐 Web data: {web_data[:100]}...")
    
    if web_data.startswith("Search") and "error" in web_data.lower():
        return "*(frustrated)* Ugh, I can't get online right now... the search thing is being weird. Try again in a moment?"
    
    # MINIMAL prompt - let MJ react naturally
    mj_web_prompt = f"""{PersonalityPrompts.BASE_INSTRUCTIONS}

CONVERSATION CONTEXT: {context}

You searched for: "{user_message}"

Here's what you found: {web_data}

React to this information as MJ - emotionally, naturally. Share what you found but with your genuine reactions."""

    try:
        response = await openai_client.chat_completion(
            messages=[
                {"role": "system", "content": mj_web_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7
        )
        
        mj_response = response.get("content", "").strip()
        print(f"🌐 Pure MJ web response: {mj_response[:100]}...")
        return mj_response
        
    except Exception as e:
        print(f"🌐 OpenAI error: {e}")
        return f"*(struggling)* I found some info but I'm having trouble processing it... gimme a sec?"

def search_web(query: str) -> str:
    """Get raw web search results from Perplexity"""
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