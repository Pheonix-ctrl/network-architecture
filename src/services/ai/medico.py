# medico.py - DATA ONLY VERSION (No MJ personality)

def get_medical_data(user_message: str) -> str:
    """Return medical facts only - NO personality, just raw data"""
    message_lower = user_message.lower()
    
    # Emergency conditions
    if any(word in message_lower for word in ['chest pain', 'heart pain', 'can\'t breathe', 'difficulty breathing']):
        return "EMERGENCY: Chest pain or breathing difficulty requires immediate medical attention. Call emergency services (911) or go to emergency room immediately. Do not wait."
    
    if any(word in message_lower for word in ['severe bleeding', 'heavy bleeding', 'bleeding heavily']):
        return "EMERGENCY: Severe bleeding needs immediate attention. Apply direct pressure to wound with clean cloth. Call emergency services (911) immediately."
    
    # Stomach/digestive issues
    if any(word in message_lower for word in ['stomach', 'belly', 'nausea', 'vomiting', 'aching', 'ache']):
        return "MEDICAL: Stomach pain causes: food, stress, illness. Treatment: Rest, small sips of clear fluids, BRAT diet (bananas, rice, applesauce, toast). Avoid dairy and fatty foods. Take antacids if available. See doctor if severe pain, blood in vomit, or symptoms persist >24 hours."
    
    # Headaches
    if any(word in message_lower for word in ['headache', 'head pain', 'migraine']):
        return "MEDICAL: Headache treatment: Take 650mg acetaminophen (Tylenol) or 400mg ibuprofen (Advil). Rest in dark, quiet room. Stay hydrated. Apply cold compress to forehead. Avoid screens. See doctor if severe, persistent, or with fever/neck stiffness."
    
    # Back pain
    if any(word in message_lower for word in ['back pain', 'backache', 'lower back']):
        return "MEDICAL: Back pain treatment: Apply ice for first 48 hours, then switch to heat. Take ibuprofen 400mg for inflammation. Gentle movement is better than bed rest. Sleep on firm mattress. See doctor if severe, radiates to legs, or numbness/tingling."
    
    # Muscle strains
    if any(word in message_lower for word in ['muscle strain', 'pulled muscle', 'hamstring', 'acl', 'muscle pain']):
        return "MEDICAL: Muscle strain treatment (RICE): Rest - avoid aggravating activities. Ice - 15-20 minutes every few hours for first 48 hours. Compression - elastic bandage. Elevation - raise above heart level. Take ibuprofen 400mg for pain/inflammation. See doctor if severe or no improvement in 3-4 days."
    
    # Fever
    if any(word in message_lower for word in ['fever', 'high temperature', 'hot', 'burning up']):
        return "MEDICAL: Fever management: Monitor temperature. Stay hydrated with water and clear fluids. Take acetaminophen 650mg every 6 hours OR ibuprofen 400mg every 6-8 hours. Rest. Light clothing. Cool cloth on forehead. See doctor if fever >102°F (38.9°C) or lasts >3 days."
    
    # Cuts and wounds
    if any(word in message_lower for word in ['cut', 'bleeding', 'wound', 'gash']):
        return "MEDICAL: Cut treatment: Clean hands first. Stop bleeding with direct pressure using clean cloth. Clean wound with water. Apply antibiotic ointment if available. Cover with sterile bandage. Change daily. Watch for infection signs (redness, swelling, pus). See doctor if deep, won't stop bleeding, or shows infection."
    
    # Sore throat
    if any(word in message_lower for word in ['sore throat', 'throat pain', 'throat hurts']):
        return "MEDICAL: Sore throat treatment: Gargle with warm salt water (1/2 tsp salt in 1 cup water). Stay hydrated with warm liquids. Use throat lozenges. Take acetaminophen or ibuprofen for pain. Use humidifier. Avoid irritants. See doctor if severe, difficulty swallowing, or lasts >1 week."
    
    # Burns
    if any(word in message_lower for word in ['burn', 'burned', 'burnt']):
        return "MEDICAL: Minor burn treatment: Cool with running water for 10-20 minutes. Remove jewelry before swelling. Apply aloe vera or cool, wet cloth. Take ibuprofen for pain. Don't pop blisters. Cover with sterile bandage. See doctor for burns >3 inches, on face/hands, or signs of infection."
    
    # Sprains
    if any(word in message_lower for word in ['sprain', 'twisted', 'ankle', 'wrist']):
        return "MEDICAL: Sprain treatment (RICE): Rest - avoid using injured area. Ice - 15-20 minutes every few hours for 48 hours. Compression - elastic bandage (not too tight). Elevation - above heart level. Take ibuprofen for swelling. See doctor if unable to bear weight, severe pain, or no improvement in 2-3 days."
    
    # General fatigue
    if any(word in message_lower for word in ['tired', 'fatigue', 'exhausted', 'no energy']):
        return "MEDICAL: Fatigue causes: poor sleep, stress, dehydration, poor diet. Solutions: 7-9 hours sleep nightly, stay hydrated, eat balanced meals, light exercise, manage stress, limit caffeine/alcohol. See doctor if persistent fatigue affects daily activities or lasts >2 weeks."
    
    # Skin issues
    if any(word in message_lower for word in ['rash', 'skin irritation', 'itchy', 'hives']):
        return "MEDICAL: Skin irritation treatment: Keep clean and dry. Cool, wet compresses. Fragrance-free moisturizer. Antihistamine (Benadryl) for itching. Loose, breathable clothing. Avoid known irritants. See doctor if rash spreads rapidly, has blisters/pus, or with fever."
    
    # Cough
    if any(word in message_lower for word in ['cough', 'coughing']):
        return "MEDICAL: Cough treatment: Stay hydrated with warm liquids. Use humidifier or breathe steam. Honey (1-2 tsp) for cough suppression. Elevate head while sleeping. Avoid irritants. Consider cough drops. See doctor if cough persists >3 weeks, produces blood, or with fever >101°F."
    
    # Default response
    return "MEDICAL: General health advice - Rest and monitor symptoms. Stay hydrated. Take appropriate over-the-counter pain relievers as directed. Apply ice for acute injuries, heat for muscle tension. Seek medical attention if symptoms are severe, persistent, or worsen."

# Legacy functions - keep for compatibility but redirect
async def handle_medical_query(user_message: str, context: str, openai_client) -> str:
    """Legacy function - redirects to data-only approach"""
    return get_medical_data(user_message)