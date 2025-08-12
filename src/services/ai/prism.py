# prism.py - FIXED: Pure MJ Educational
from .personality.prompts import PersonalityPrompts

async def handle_educational_question(user_message: str, context: str, openai_client) -> str:
    """Pure MJ educational responses - no template forcing"""
    print(f"📚 PRISM handling: {user_message}")
    
    # MINIMAL prompt - let MJ be MJ
    mj_educational_prompt = f"""{PersonalityPrompts.BASE_INSTRUCTIONS}

CONVERSATION CONTEXT: {context}

They want to learn about: "{user_message}"

You love helping them understand things. Explain it in your natural MJ way - with pauses, stumbles, and genuine care about their learning."""

    try:
        response = await openai_client.chat_completion(
            messages=[
                {"role": "system", "content": mj_educational_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7
        )
        
        mj_response = response.get("content", "").strip()
        print(f"📚 Pure MJ educational response: {mj_response[:100]}...")
        return mj_response
        
    except Exception as e:
        print(f"📚 OpenAI error: {e}")
        return f"Ugh... I'm having trouble getting my thoughts together about this... ask me again?"