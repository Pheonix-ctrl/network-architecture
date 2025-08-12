# classifier_test.py - Test how the classifier is working with tough questions

import sys
import os
import asyncio

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

async def test_classifier():
    """Test the classifier with challenging and entangled questions"""
    
    print("🧪 TESTING MJ CLASSIFIER WITH TOUGH QUESTIONS")
    print("=" * 60)
    
    # Import the classifier
    try:
        from src.services.ai.mode_classifier import ModeClassifier
        classifier = ModeClassifier()
        print("✅ Classifier loaded successfully!")
    except Exception as e:
        print(f"❌ Failed to load classifier: {e}")
        return
    
    # Test cases - from easy to EXTREMELY challenging
    test_cases = [
        # === CLEAR CUT CASES ===
        "my head hurts a lot",
        "explain quantum physics to me", 
        "what's the current Bitcoin price?",
        "hey how are you doing?",
        
        # === MEDICAL CASES ===
        "btw I got my acl swollen fuck",
        "my stomach is aching alot",
        "I don't know my back is paining a lot mj, I think this deadlifts",
        "my uncle just got an stroke bro",
        "I'm feeling really tired lately",
        "I cut my finger and it's bleeding",
        "I think I have COVID symptoms",
        "my chest feels tight and I can't breathe properly",
        "I've been having panic attacks",
        "my period is late and I'm worried",
        
        # === EDUCATIONAL CASES ===
        "mj I was wondering like im not understanding what is thermodynamics bro",
        "can you explain me electric circuits",
        "explain me the overall concept of it", 
        "what is calculus exactly?",
        "how does photosynthesis work?",
        "tell me about democracy",
        "I need to understand machine learning algorithms",
        "what's the difference between communism and socialism?",
        "how do vaccines actually work in the body?",
        
        # === WEB SEARCH CASES ===
        "tell me latest today news",
        "search on web for it",
        "can you tell me whats current stock price of apple?",
        "when is the next Real Madrid match?",
        "what's happening in Ukraine right now?",
        "latest news about AI",
        "who won the elections yesterday?",
        "what's the weather like today?",
        "current cryptocurrency prices",
        "breaking news about the stock market crash",
        
        # === EXTREMELY ENTANGLED CASES ===
        "I'm stressed about my medical school exam on pharmacology",  # Personal + Educational + Medical
        "my therapist told me to research anxiety disorders online",  # Medical + Educational + Web + Personal
        "search for the latest research on cancer treatment because my mom has it",  # Web + Medical + Personal
        "I need to understand economics for my job but the stress is giving me headaches",  # Educational + Medical + Personal
        "can you find current news about mental health and then explain the psychology behind depression?",  # Web + Educational + Medical + Personal
        "my girlfriend is studying medicine and I want to learn too but I'm scared of blood",  # Educational + Medical + Personal
        "search for quantum computing news and explain how it works because I'm interviewing at a tech company tomorrow",  # Web + Educational + Personal
        "I'm having nightmares about my chemistry exam, can you teach me organic chemistry?",  # Personal + Educational
        "my doctor said to look up information about my condition online, but I don't understand medical terms",  # Medical + Web + Educational
        "I'm depressed because I failed my physics exam, can you explain relativity to me?",  # Personal + Educational
        
        # === CONTEXT DEPENDENT NIGHTMARES ===
        "can you explain me?",  # Needs context
        "tell me more about it",  # Needs context
        "what should I do?",  # Could be any category
        "help me understand this",  # Vague
        "I don't get it",  # Vague
        "continue from where we left off",  # Needs context
        "that thing you mentioned earlier",  # Needs context
        "yes, tell me more",  # Needs context
        "what about the other one?",  # Needs context
        
        # === EMOTIONAL MEDICAL EDUCATIONAL WEB COMBOS ===
        "I'm scared about my surgery tomorrow, can you search for success rates and explain the procedure?",  # Medical + Web + Educational + Personal
        "my dad died of cancer, I want to understand oncology and find the latest treatment research",  # Medical + Educational + Web + Personal
        "I'm having an anxiety attack, can you teach me breathing techniques and find current research on panic disorders?",  # Medical + Educational + Web + Personal
        "my girlfriend broke up with me and now I can't focus on my biochemistry studies",  # Personal + Educational
        "I'm worried about climate change affecting my health, can you search for recent studies and explain the science?",  # Personal + Medical + Web + Educational
        
        # === DECEPTIVE QUESTIONS ===
        "I need some medicine",  # Sounds medical but could be asking for drugs
        "search for my doctor",  # Sounds like web search but could be medical
        "teach me about drugs",  # Could be educational (pharmacology) or something else
        "I want to learn about bodies",  # Could be educational (anatomy) or inappropriate
        "explain how to make people feel better",  # Could be medical, educational, or personal
        "find information about treatment",  # Medical + Web but very vague
        "I need to understand pain",  # Could be medical, educational, or personal
        "tell me about recovery",  # Medical, personal, or educational?
        
        # === MULTIPLE CONFLICTING REQUESTS ===
        "search for quantum physics news and then explain it to me and also I have a headache",  # Web + Educational + Medical
        "my head hurts, find me a doctor nearby, and also teach me about migraines",  # Medical + Web + Educational
        "explain economics and tell me the latest market news but I'm too stressed to focus",  # Educational + Web + Personal
        "I want to learn programming but my wrist hurts from typing, search for ergonomic solutions",  # Educational + Medical + Web
        "find news about the new COVID variant and explain how viruses mutate",  # Web + Educational + Medical
        
        # === IMPOSSIBLE EDGE CASES ===
        "uh",  # Single syllable
        "hmm",  # Thinking sound
        "...",  # Just dots
        "idk",  # Very short
        "sure",  # Agreement without context
        "nah",  # Disagreement without context
        "maybe",  # Uncertainty without context
        "whatever",  # Dismissive without context
        "k",  # Single letter
        "",  # Empty string
        "🤔",  # Just emoji
        "lol",  # Just laughter
        
        # === METAPHORICAL/INDIRECT ===
        "my heart is broken",  # Could be medical (cardiac) or personal (emotional)
        "I'm dying to know",  # Not actually medical despite "dying"
        "this is killing me",  # Not actually medical despite "killing"
        "I'm sick of this",  # Not actually medical despite "sick"
        "my brain is fried",  # Not actually medical despite brain reference
        "I'm burning up",  # Could be fever or just stressed
        "I feel like I'm drowning",  # Could be panic attack or just overwhelmed
        "I'm bleeding money",  # Not actually medical bleeding
        
        # === TECHNICAL JARGON MIXING ===
        "the derivatives in my calculus class are giving me migraines",  # Educational + Medical
        "I need to search for the latest AI models to help with my depression research",  # Web + Educational + Medical
        "my quantum mechanics professor is making me sick with stress",  # Educational + Medical + Personal
        "can you find current stock prices for pharmaceutical companies and explain how drug development works?",  # Web + Educational + Medical
        "the thermodynamics equations are heating up my brain",  # Educational (metaphorical medical)
        
        # === TEMPORAL CONFUSION ===
        "what was that thing you told me yesterday about cancer?",  # Medical + needs context + temporal
        "remember when we talked about quantum physics last week?",  # Educational + temporal + context
        "you mentioned some news earlier, what was it?",  # Web + temporal + context
        "continue explaining what you were teaching me before",  # Educational + temporal + context
        
        # === CULTURAL/SLANG MIXING ===
        "yo bro my head is totally fucked up right now",  # Medical with slang
        "can you break down this complicated shit about economics for me?",  # Educational with profanity
        "find me the latest tea about celebrity drama",  # Web search with slang
        "I'm lowkey dying from this exam stress",  # Personal/Medical metaphor with slang
        "this math problem is absolutely destroying my soul",  # Educational with dramatic language
        
        # === NESTED CONDITIONALS ===
        "if my headache gets worse, search for symptoms, but if it's just stress, teach me relaxation techniques",  # Medical + Web + Educational with conditions
        "depending on what the news says about the market, either explain economics to me or help me find a therapist",  # Web + Educational + Medical with conditions
        "if you can't find current information, just explain it from your knowledge, but I prefer recent data",  # Web + Educational with fallback
        
        # === PARADOXICAL REQUESTS ===
        "I don't want to know but I need to understand",  # Contradictory
        "search for something but don't tell me what you find",  # Web but contradictory
        "explain this simply but give me all the complex details",  # Educational but contradictory
        "I trust you but I want to verify everything online",  # Personal + Web contradiction
        
        # === EMERGENCY VS NON-EMERGENCY CONFUSION ===
        "I think I'm having a heart attack but it might just be anxiety",  # Medical emergency vs non-emergency
        "my house is on fire but first can you explain combustion chemistry?",  # Emergency + Educational (inappropriate priority)
        "I'm bleeding badly but can you search for the best hospitals first?",  # Medical emergency + Web (wrong priority)
        "someone call 911 but also teach me first aid",  # Emergency + Educational
    ]
    
    print(f"\n🧪 Testing {len(test_cases)} cases...\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"TEST {i:2d}: {test_case}")
        print(f"{'='*60}")
        
        try:
            # Test the classifier
            result = classifier.classify_mode(test_case, 'mj', {})
            
            # Handle tuple result
            if isinstance(result, tuple) and len(result) == 2:
                personality_mode, routing_info = result
                
                # Extract info
                mode_str = str(personality_mode).replace('PersonalityMode.', '').lower()
                confidence = routing_info.get('confidence', 0.0)
                
                # Check if it should be web_search
                if routing_info.get('should_search_web', False):
                    mode_str = 'web_search'
                
                print(f"🎯 RESULT: {mode_str.upper()}")
                print(f"📊 CONFIDENCE: {confidence:.3f}")
                print(f"📋 ROUTING INFO: {routing_info}")
                
                # Determine if this is a good classification
                expected = determine_expected_category(test_case)
                if expected:
                    if mode_str in expected:
                        print(f"✅ CORRECT (expected: {expected})")
                    else:
                        print(f"❌ WRONG (expected: {expected}, got: {mode_str})")
                else:
                    print(f"🤔 UNCLEAR (subjective case)")
                
            else:
                print(f"❌ UNEXPECTED RESULT FORMAT: {result}")
                
        except Exception as e:
            print(f"💥 ERROR: {e}")
        
        print(f"{'='*60}")
    
    print(f"\n🏁 CLASSIFIER TESTING COMPLETE")

def determine_expected_category(test_case):
    """Determine what category we'd expect for each test case"""
    test_lower = test_case.lower()
    
    # Clear medical cases
    if any(word in test_lower for word in ['hurt', 'pain', 'aching', 'sick', 'bleeding', 'stroke', 'surgery', 'doctor', 'tired', 'acl', 'stomach', 'back', 'head', 'finger']):
        return ['healthcare', 'medical']
    
    # Clear educational cases  
    if any(word in test_lower for word in ['explain', 'thermodynamics', 'quantum', 'calculus', 'circuits', 'photosynthesis', 'democracy', 'understand', 'physics', 'teach']):
        return ['educational']
    
    # Clear web search cases
    if any(word in test_lower for word in ['news', 'current', 'latest', 'search', 'price', 'bitcoin', 'apple', 'stock', 'real madrid', 'ukraine', 'happening']):
        return ['web_search']
    
    # Personal/unclear cases
    if any(word in test_lower for word in ['hey', 'how are you', 'stressed', 'depressed', 'scared', 'worried', 'girlfriend']):
        return ['personal']
    
    # Entangled cases (multiple valid answers)
    if 'stressed about my exam' in test_lower:
        return ['personal', 'educational']
    if 'search for' in test_lower and 'explain' in test_lower:
        return ['web_search', 'educational']
    if 'doctor told me to learn' in test_lower:
        return ['medical', 'educational']
    
    # Context dependent - could be anything
    if test_case in ['can you explain me?', 'tell me more about it', 'what should I do?', 'help me understand this', "I don't get it"]:
        return None  # Subjective
    
    return None  # Unknown/subjective

if __name__ == "__main__":
    asyncio.run(test_classifier())