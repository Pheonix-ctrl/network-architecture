
# src/services/ai/mode_classifier.py
from typing import Dict, List, Tuple
import re
from ...models.schemas.chat import PersonalityMode

class ModeClassifier:
    def __init__(self):
        self.keywords = {
            PersonalityMode.KALKI: [
                # Emergency/Crisis keywords
                "help", "emergency", "danger", "scared", "afraid", "panic",
                "following me", "stalking", "unsafe", "threatened", "attack",
                "hurt me", "violence", "abuse", "trapped", "lost", "alone at night",
                "stranger", "suspicious", "creepy", "harassment", "assault",
                "call police", "911", "emergency room", "hospital", "ambulance",
                # Emotional crisis
                "suicide", "kill myself", "self harm", "cutting", "overdose",
                "end it all", "can't go on", "hopeless", "worthless",
            ],
            
            PersonalityMode.JUPITER: [
                # Deep emotional support keywords
                "depressed", "anxiety", "lonely", "heartbroken", "devastated",
                "grieving", "lost someone", "breakup", "divorce", "death",
                "trauma", "ptsd", "therapy", "counselor", "medication",
                "crying", "tears", "emotional", "feelings", "hurt inside",
                "empty", "numb", "overwhelmed", "breakdown", "mental health",
                "love", "relationship problems", "family issues", "friendship",
                "betrayed", "abandoned", "rejected", "unloved", "insecure",
            ],
            
            PersonalityMode.EDUCATIONAL: [
                # Learning and teaching keywords
                "learn", "teach", "explain", "understand", "study", "homework",
                "assignment", "project", "research", "knowledge", "education",
                "school", "college", "university", "course", "class", "lesson",
                "exam", "test", "grade", "academic", "subject", "topic",
                "how does", "why does", "what is", "how to", "tutorial",
                "guide", "instructions", "steps", "method", "technique",
                "skill", "practice", "training", "certification", "degree",
            ],
            
            PersonalityMode.HEALTHCARE: [
                # Health and medical keywords
                "health", "medical", "doctor", "hospital", "medicine", "symptom",
                "pain", "sick", "illness", "disease", "condition", "treatment",
                "diagnosis", "prescription", "medication", "therapy", "surgery",
                "appointment", "clinic", "nurse", "specialist", "emergency room",
                "headache", "fever", "nausea", "dizzy", "fatigue", "weakness",
                "chest pain", "shortness of breath", "allergic reaction",
                "injury", "accident", "bleeding", "broken", "sprain", "strain",
                "mental health", "depression", "anxiety disorder", "bipolar",
            ]
        }
        
        # Priority order (higher priority modes checked first)
        self.priority_order = [
            PersonalityMode.KALKI,      # Highest priority - emergency
            PersonalityMode.HEALTHCARE, # Medical emergencies
            PersonalityMode.JUPITER,    # Emotional support
            PersonalityMode.EDUCATIONAL, # Learning
        ]
    
    def classify_mode(
        self,
        message: str,
        current_mode: PersonalityMode = PersonalityMode.MJ,
        user_context: Dict = None
    ) -> Tuple[PersonalityMode, float]:
        """
        Classify the appropriate personality mode for a message
        Returns: (mode, confidence_score)
        """
        message_lower = message.lower()
        
        # Calculate scores for each mode
        mode_scores = {}
        
        for mode in self.priority_order:
            score = self._calculate_mode_score(message_lower, mode)
            mode_scores[mode] = score
        
        # Find the highest scoring mode
        best_mode = max(mode_scores.items(), key=lambda x: x[1])
        
        # Apply threshold - only switch if confidence is high enough
        confidence_threshold = self._get_threshold_for_mode(best_mode[0])
        
        if best_mode[1] >= confidence_threshold:
            return best_mode[0], best_mode[1]
        else:
            # Stay in current mode if no strong signal
            return current_mode, 0.5
    
    def _calculate_mode_score(self, message: str, mode: PersonalityMode) -> float:
        """Calculate relevance score for a specific mode"""
        if mode not in self.keywords:
            return 0.0
        
        keywords = self.keywords[mode]
        total_score = 0.0
        
        for keyword in keywords:
            # Exact match gets full score
            if keyword in message:
                weight = self._get_keyword_weight(keyword, mode)
                total_score += weight
                
            # Partial match gets reduced score
            elif any(word in message for word in keyword.split()):
                weight = self._get_keyword_weight(keyword, mode) * 0.5
                total_score += weight
        
        # Normalize score by number of keywords
        normalized_score = min(total_score / len(keywords) * 10, 1.0)
        
        return normalized_score
    
    def _get_keyword_weight(self, keyword: str, mode: PersonalityMode) -> float:
        """Get weight for specific keywords based on urgency/importance"""
        
        # Emergency keywords get highest weight
        emergency_keywords = ["help", "emergency", "danger", "911", "police", "suicide", "kill myself"]
        if keyword in emergency_keywords:
            return 1.0
        
        # Medical urgency keywords
        medical_urgent = ["chest pain", "can't breathe", "overdose", "allergic reaction", "bleeding"]
        if keyword in medical_urgent:
            return 0.9
        
        # High emotional distress
        emotional_urgent = ["heartbroken", "devastated", "breakdown", "trauma", "grief"]
        if keyword in emotional_urgent:
            return 0.8
        
        # Standard keywords
        return 0.3
    
    def _get_threshold_for_mode(self, mode: PersonalityMode) -> float:
        """Get confidence threshold required to switch to a mode"""
        thresholds = {
            PersonalityMode.KALKI: 0.3,      # Low threshold for emergencies
            PersonalityMode.HEALTHCARE: 0.4, # Low threshold for health issues
            PersonalityMode.JUPITER: 0.5,    # Medium threshold for emotional support
            PersonalityMode.EDUCATIONAL: 0.6, # Higher threshold for educational mode
        }
        return thresholds.get(mode, 0.5)
    
    def get_mode_explanation(self, mode: PersonalityMode) -> str:
        """Get explanation for why a mode was selected"""
        explanations = {
            PersonalityMode.KALKI: "Detected potential emergency or crisis situation. Switching to protective mode.",
            PersonalityMode.JUPITER: "Detected emotional distress or need for deeper support. Switching to empathetic mode.",
            PersonalityMode.HEALTHCARE: "Detected health-related concerns. Switching to healthcare support mode.",
            PersonalityMode.EDUCATIONAL: "Detected learning or educational request. Switching to teaching mode.",
            PersonalityMode.MJ: "Continuing in default conversational mode."
        }
        return explanations.get(mode, "Mode selected based on conversation context.")
