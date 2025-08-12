# src/services/ai/mode_classifier.py
from ...models.schemas.chat import PersonalityMode
from .classifier.smart_router import MJSmartRouter

class ModeClassifier:
    def __init__(self):
        """Initialize the smart router for ML-powered mode classification"""
        try:
            self.smart_router = MJSmartRouter()
            self.router_available = True
            print("🧠 ML-powered mode classification ready!")
        except Exception as e:
            print(f"⚠️ Smart router failed to load: {e}")
            print("🔄 Falling back to keyword-based classification")
            self.router_available = False
    
    def classify_mode(self, message: str, current_mode: PersonalityMode, user_context: dict = None) -> tuple:
        """
        Classify the appropriate personality mode for the message
        
        Args:
            message: User's message
            current_mode: Current personality mode
            user_context: Additional user context
            
        Returns:
            tuple: (PersonalityMode, routing_info: dict)
        """
        
        if self.router_available:
            return self._ml_classify(message, current_mode, user_context)
        else:
            return self._fallback_classify(message, current_mode, user_context)
    
    def _ml_classify(self, message: str, current_mode: PersonalityMode, user_context: dict) -> tuple:
        """ML-powered classification using the trained model"""
        
        # Get routing result from ML model
        routing_result = self.smart_router.route_with_confidence(message)
        
        module = routing_result['module']
        confidence = routing_result['confidence']
        all_probs = routing_result['all_probabilities']
        
        # Map ML modules to personality modes with LOWERED confidence thresholds
        if module == 'medical' and confidence > 0.40:  # LOWERED from 0.7 to 0.4
            new_mode = PersonalityMode.HEALTHCARE
            print(f"🏥 HEALTHCARE mode activated (confidence: {confidence:.2f})")
            
        elif module == 'educational' and confidence > 0.50:  # LOWERED from 0.8 to 0.5
            new_mode = PersonalityMode.EDUCATIONAL  
            print(f"📚 EDUCATIONAL mode activated (confidence: {confidence:.2f})")
            
        elif module == 'web_search' and confidence > 0.50:  # LOWERED from 0.85 to 0.5
            # Keep current personality but flag for web search
            new_mode = current_mode
            print(f"🌐 Web search needed (confidence: {confidence:.2f})")
            
        else:
            # Check for emergency keywords that override ML prediction
            emergency_keywords = ['suicide', 'kill myself', 'end it all', 'want to die', 'hurt myself']
            if any(keyword in message.lower() for keyword in emergency_keywords):
                new_mode = PersonalityMode.KALKI
                print("🚨 KALKI mode activated - EMERGENCY DETECTED")
            else:
                new_mode = PersonalityMode.MJ
                print(f"💭 MJ mode (personal conversation - confidence: {confidence:.2f})")
        
        # Enhanced routing info for the chat handler with LOWERED thresholds
        routing_info = {
            'ml_prediction': module,
            'confidence': confidence,
            'all_probabilities': all_probs,
            'should_search_web': module == 'web_search' and confidence > 0.50,  # LOWERED from 0.85
            'should_use_medical': module == 'medical' and confidence > 0.40,    # LOWERED from 0.7
            'should_use_educational': module == 'educational' and confidence > 0.50,  # LOWERED from 0.8
            'routing_time_ms': routing_result['routing_time_ms']
        }
        
        return new_mode, routing_info
    
    def _fallback_classify(self, message: str, current_mode: PersonalityMode, user_context: dict) -> tuple:
        """Fallback keyword-based classification if ML router fails"""
        
        message_lower = message.lower()
        
        # Emergency keywords - highest priority
        emergency_keywords = ['suicide', 'kill myself', 'end it all', 'want to die', 'hurt myself', 'help me', 'danger']
        if any(keyword in message_lower for keyword in emergency_keywords):
            return PersonalityMode.KALKI, {'fallback': True, 'reason': 'emergency_keywords'}
        
        # Medical keywords - be more aggressive
        medical_keywords = ['pain', 'hurt', 'sick', 'fever', 'bleeding', 'injury', 'doctor', 'hospital', 'symptoms', 'ache', 'aching', 'stomach', 'headache', 'back', 'muscle', 'heart', 'chest']
        if any(keyword in message_lower for keyword in medical_keywords):
            return PersonalityMode.HEALTHCARE, {'fallback': True, 'reason': 'medical_keywords', 'confidence': 0.75}
        
        # Educational keywords - be more aggressive
        educational_keywords = ['explain', 'how does', 'what is', 'teach me', 'learn', 'understand', 'homework', 'thermodynamics', 'physics', 'chemistry', 'calculus', 'quantum', 'concept', 'theory']
        if any(keyword in message_lower for keyword in educational_keywords):
            return PersonalityMode.EDUCATIONAL, {'fallback': True, 'reason': 'educational_keywords', 'confidence': 0.85}
        
        # Web search keywords - be more aggressive
        web_keywords = ['current', 'latest', 'news', 'today', 'now', 'what\'s happening', 'search', 'find', 'look up', 'web', 'google', 'stock', 'price', 'match', 'game', 'recent']
        if any(keyword in message_lower for keyword in web_keywords):
            return current_mode, {'fallback': True, 'reason': 'web_search_keywords', 'should_search_web': True, 'confidence': 0.80}
        
        # Default to MJ mode
        return PersonalityMode.MJ, {'fallback': True, 'reason': 'default', 'confidence': 0.6}