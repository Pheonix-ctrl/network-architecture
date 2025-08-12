# src/services/ai/classifier/smart_router.py
import joblib
import time
import os
from pathlib import Path

class MJSmartRouter:
    def __init__(self):
        """Load the trained MJ classifier components"""
        try:
            # Get the directory where this file is located
            current_dir = Path(__file__).parent
            
            # Load the trained models
            self.classifier = joblib.load(current_dir / 'mj_classifier_model.pkl')
            self.vectorizer = joblib.load(current_dir / 'mj_tfidf_vectorizer.pkl') 
            self.label_encoder = joblib.load(current_dir / 'mj_label_encoder.pkl')
            
            print("✅ MJ Smart Router loaded successfully!")
            print(f"📊 Model accuracy: 91.4% | Categories: {list(self.label_encoder.classes_)}")
            
        except Exception as e:
            print(f"❌ Error loading MJ router: {e}")
            raise
    
    def route_query(self, user_query: str) -> str:
        """
        Route user query to appropriate MJ module
        
        Args:
            user_query (str): User's input query
            
        Returns:
            str: Module name ('medical', 'educational', 'web_search', 'personal')
        """
        start_time = time.time()
        
        # Transform query using trained vectorizer
        query_features = self.vectorizer.transform([user_query])
        
        # Get prediction from trained classifier
        prediction = self.classifier.predict(query_features)[0]
        
        # Convert to module name
        module_name = self.label_encoder.classes_[prediction]
        
        routing_time = (time.time() - start_time) * 1000
        
        # Log routing for monitoring
        print(f"🎯 Routed '{user_query[:50]}...' → {module_name.upper()} ({routing_time:.2f}ms)")
        
        return str(module_name)
    
    def route_with_confidence(self, user_query: str) -> dict:
        """
        Route with confidence scores for advanced decision making
        
        Returns:
            dict: {
                'module': str,
                'confidence': float,
                'all_probabilities': dict,
                'routing_time_ms': float
            }
        """
        start_time = time.time()
        
        query_features = self.vectorizer.transform([user_query])
        prediction = self.classifier.predict(query_features)[0]
        probabilities = self.classifier.predict_proba(query_features)[0]
        
        module_name = self.label_encoder.classes_[prediction]
        confidence = probabilities[prediction]
        
        # All module probabilities
        all_probs = {}
        for i, prob in enumerate(probabilities):
            module = self.label_encoder.classes_[i]
            all_probs[module] = float(prob)
        
        routing_time = (time.time() - start_time) * 1000
        
        return {
            'module': str(module_name),
            'confidence': float(confidence),
            'all_probabilities': all_probs,
            'routing_time_ms': routing_time
        }

# Example usage:
# router = MJSmartRouter()
# result = router.route_with_confidence("My head hurts")
# print(result)  # {'module': 'medical', 'confidence': 0.95, ...}