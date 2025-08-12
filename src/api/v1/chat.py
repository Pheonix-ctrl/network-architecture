# src/api/v1/chat.py - Updated with ML-powered smart routing
from fastapi import APIRouter, Depends, HTTPException
from ...models.schemas.chat import ChatMessage, ChatResponse, PersonalityMode
from ...services.ai.mode_classifier import ModeClassifier
from ...core.dependencies import get_current_user
import time

# Initialize the ML-powered mode classifier
mode_classifier = ModeClassifier()

router = APIRouter()

@router.post("/message", response_model=ChatResponse)
async def chat_message(
    message: ChatMessage,
    current_user = Depends(get_current_user)
):
    """
    Main chat endpoint with ML-powered intelligent routing
    """
    start_time = time.time()
    
    try:
        print(f"💬 User {current_user.id}: {message.content}")
        
        # Step 1: Use ML classifier to determine routing
        personality_mode, routing_info = mode_classifier.classify_mode(
            message.content, 
            PersonalityMode.MJ,  # Default mode
            user_context={"user_id": current_user.id}
        )
        
        print(f"🧠 ML Routing: {routing_info}")
        print(f"🎭 Personality Mode: {personality_mode.value}")
        
        # Step 2: Route to appropriate specialized module
        response_content = ""
        
        # Medical routing
        if routing_info.get('should_use_medical', False):
            try:
                from ...services.ai.medico import should_use_medical_care, handle_medical_query
                is_medical, urgency_level = should_use_medical_care(message.content)
                
                if is_medical:
                    print(f"🏥 Medical module activated (urgency: {urgency_level})")
                    response_content = handle_medical_query(message.content, urgency_level)
                
            except ImportError as e:
                print(f"⚠️ Medical module not available: {e}")
        
        # Educational routing  
        elif routing_info.get('should_use_educational', False):
            try:
                from ...services.ai.prism import should_use_prism, handle_educational_question
                should_educate, intent_data = should_use_prism(message.content)
                
                if should_educate:
                    print(f"📚 Educational module activated")
                    response_content = handle_educational_question(message.content, intent_data)
                
            except ImportError as e:
                print(f"⚠️ Educational module not available: {e}")
        
        # Web search routing
        elif routing_info.get('should_search_web', False):
            try:
                from ...services.external.perplexity import handle_web_question
                print(f"🌐 Web search module activated")
                response_content = handle_web_question(message.content)
                
            except ImportError as e:
                print(f"⚠️ Web search module not available: {e}")
        
        # Step 3: If no specialized module handled it, use regular MJ
        if not response_content:
            print(f"💭 Using regular MJ personality mode: {personality_mode.value}")
            
            # Here you would call your regular OpenAI chat completion
            # with the determined personality mode
            from ...services.ai.openai_client import OpenAIClient
            
            openai_client = OpenAIClient()
            response_content = await openai_client.chat_completion(
                messages=[{"role": "user", "content": message.content}],
                mode=personality_mode,
                tools=routing_info.get('should_search_web', False)
            )
        
        # Step 4: Calculate response time and return
        response_time = int((time.time() - start_time) * 1000)
        
        return ChatResponse(
            content=response_content,
            mode=personality_mode,
            response_time_ms=response_time,
            tokens_used=0,  # You'd track this from your AI calls
            similar_memories=[],  # You'd populate this from memory system
            routing_info=routing_info  # Include ML routing info for debugging
        )
        
    except Exception as e:
        print(f"❌ Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

@router.get("/test-classifier")
async def test_classifier_endpoint():
    """Test endpoint to verify the ML classifier is working"""
    
    test_queries = [
        "My head hurts really bad",
        "Can you explain quantum physics?",
        "What's the latest Bitcoin price?", 
        "I'm feeling really sad"
    ]
    
    results = []
    
    for query in test_queries:
        mode, routing_info = mode_classifier.classify_mode(query, PersonalityMode.MJ)
        
        results.append({
            "query": query,
            "personality_mode": mode.value,
            "ml_prediction": routing_info.get('ml_prediction', 'unknown'),
            "confidence": routing_info.get('confidence', 0.0),
            "should_use_medical": routing_info.get('should_use_medical', False),
            "should_use_educational": routing_info.get('should_use_educational', False),
            "should_search_web": routing_info.get('should_search_web', False)
        })
    
    return {
        "message": "ML Classifier is working!",
        "test_results": results
    }