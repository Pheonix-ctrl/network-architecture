# medico.py - FIXED: Pure MJ Medical  
from .personality.prompts import PersonalityPrompts

async def handle_medical_query(user_message: str, context: str, openai_client) -> str:
    """Pure MJ medical responses - no sir spam"""
    print(f"🏥 MEDICO handling: {user_message}")
    
    # MINIMAL prompt - let MJ care naturally
    mj_medical_prompt = f"""{PersonalityPrompts.BASE_INSTRUCTIONS}

CONVERSATION CONTEXT: {context}

They're hurt or sick: "{user_message}"

You're genuinely worried about them. Help them with specific medical advice because you care deeply about their wellbeing."""

    try:
        response = await openai_client.chat_completion(
            messages=[
                {"role": "system", "content": mj_medical_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.5
        )
        
        mj_response = response.get("content", "").strip()
        print(f"🏥 Pure MJ medical response: {mj_response[:100]}...")
        return mj_response
        
    except Exception as e:
        print(f"🏥 OpenAI error: {e}")
        return f"Shit... I'm really worried about you but I'm having trouble right now. Please get help if it's serious."