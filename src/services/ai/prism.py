# prism.py - DATA ONLY VERSION (No MJ personality)

def get_educational_data(user_message: str) -> str:
    """Return educational facts only - NO personality, just raw knowledge"""
    message_lower = user_message.lower()
    
    # Physics/Science topics
    if any(word in message_lower for word in ['thermodynamics', 'heat', 'energy', 'entropy']):
        return "EDUCATION: Thermodynamics studies heat and energy transfer. Key laws: 1) First Law - energy cannot be created or destroyed, only converted (conservation of energy). Example: chemical energy in gas → heat → kinetic energy in car. 2) Second Law - entropy (disorder) always increases. Heat flows from hot to cold naturally. 3) Third Law - absolute zero cannot be reached. Applications: engines, refrigerators, power plants."
    
    elif any(word in message_lower for word in ['circuits', 'electricity', 'electrical', 'current', 'voltage']):
        return "EDUCATION: Electric circuits have three main parts: 1) Power source (battery) provides energy. 2) Load (light bulb, motor) uses energy. 3) Conductors (wires) carry electricity. When switch closes, electrons flow from negative to positive terminal. If circuit breaks (cut wire), no current flows. Ohm's Law: Voltage = Current × Resistance (V=IR)."
    
    elif any(word in message_lower for word in ['calculus', 'derivatives', 'integrals']):
        return "EDUCATION: Calculus studies continuous change. Two main branches: 1) Differential calculus (derivatives) - measures rates of change. If position changes over time, derivative gives velocity. If velocity changes, derivative gives acceleration. 2) Integral calculus - measures accumulation. Adding up all velocity changes gives total distance. Applications: physics, engineering, optimization, economics."
    
    elif any(word in message_lower for word in ['quantum', 'quantum physics', 'quantum mechanics']):
        return "EDUCATION: Quantum physics studies behavior of atoms and subatomic particles. Key concepts: 1) Superposition - particles exist in multiple states until measured. 2) Wave-particle duality - light and matter act as both waves and particles. 3) Uncertainty principle - cannot know both exact position and momentum simultaneously. 4) Quantum entanglement - particles can be mysteriously connected across distances."
    
    elif any(word in message_lower for word in ['mechanics', 'physics', 'motion', 'force', 'newton']):
        return "EDUCATION: Mechanics studies motion and forces. Newton's Laws: 1) First Law (Inertia) - objects at rest stay at rest, objects in motion stay in motion unless acted upon by force. 2) Second Law - Force = mass × acceleration (F=ma). 3) Third Law - for every action, there's equal and opposite reaction. Key concepts: velocity (speed with direction), acceleration (change in velocity)."
    
    # Chemistry topics
    elif any(word in message_lower for word in ['chemistry', 'atoms', 'molecules', 'periodic table']):
        return "EDUCATION: Chemistry studies matter at atomic level. Atoms contain protons (+), neutrons (neutral), electrons (-). Elements are defined by number of protons. Compounds form when atoms bond together (H2O = water). Chemical bonds: ionic (transfer electrons), covalent (share electrons). Periodic table organizes elements by atomic number, showing patterns in properties."
    
    elif any(word in message_lower for word in ['photosynthesis', 'plants', 'chlorophyll']):
        return "EDUCATION: Photosynthesis is how plants make food using sunlight. Process: Chlorophyll in leaves absorbs light energy. Roots absorb water (H2O). Leaves take in carbon dioxide (CO2) from air. Plants combine CO2 + H2O using light energy to create glucose (food) and release oxygen (O2). Equation: 6CO2 + 6H2O + light → C6H12O6 + 6O2."
    
    # Math topics
    elif any(word in message_lower for word in ['algebra', 'equations', 'variables']):
        return "EDUCATION: Algebra uses letters (variables) to represent unknown numbers. Goal is solving equations to find variable values. Example: 2x + 5 = 13. Subtract 5 from both sides: 2x = 8. Divide by 2: x = 4. Key operations: addition/subtraction (inverse operations), multiplication/division (inverse operations). Used in science, engineering, finance."
    
    elif any(word in message_lower for word in ['geometry', 'shapes', 'angles', 'triangles']):
        return "EDUCATION: Geometry studies shapes, sizes, angles, and spatial relationships. Basic shapes: triangle (3 sides), square (4 equal sides), circle (all points equal distance from center). Key concepts: perimeter (distance around), area (space inside), volume (3D space). Pythagorean theorem: a² + b² = c² for right triangles."
    
    # Biology topics
    elif any(word in message_lower for word in ['evolution', 'natural selection', 'darwin']):
        return "EDUCATION: Evolution is change in species over time through natural selection. Darwin's insights: 1) Variation - individuals differ in traits. 2) Inheritance - traits passed to offspring. 3) Selection pressure - environmental challenges. 4) Survival of fittest - advantageous traits help survival/reproduction. Over generations, helpful traits become more common. Evidence: fossils, DNA similarities, observed changes."
    
    elif any(word in message_lower for word in ['dna', 'genes', 'genetics']):
        return "EDUCATION: DNA (deoxyribonucleic acid) contains genetic instructions for all living things. Structure: double helix with four bases (A, T, G, C). Genes are DNA segments coding for specific traits. Inheritance: offspring receive DNA from both parents. Mutations can create new variations. DNA determines physical characteristics, some behaviors, and disease susceptibility."
    
    # Social Studies topics
    elif any(word in message_lower for word in ['democracy', 'government', 'voting', 'politics']):
        return "EDUCATION: Democracy means 'rule by the people.' Key principles: 1) Popular sovereignty - government authority from people's consent. 2) Majority rule with minority rights protection. 3) Individual liberties (speech, religion, assembly). 4) Equality under law. 5) Free, fair elections with secret ballots. Types: direct democracy (citizens vote on issues) vs representative democracy (elect representatives)."
    
    elif any(word in message_lower for word in ['history', 'historical', 'past', 'civilization']):
        return "EDUCATION: History studies past events, their causes, and effects. Key themes: 1) Cause and effect - events don't happen in isolation. 2) Change and continuity - some things transform, others remain constant. 3) Human agency - individuals/groups shape events. 4) Historical context - understanding time period's values/technology. 5) Multiple perspectives - different groups experience same events differently."
    
    # Economics topics
    elif any(word in message_lower for word in ['economics', 'supply', 'demand', 'market', 'money']):
        return "EDUCATION: Economics studies how societies allocate limited resources. Key concepts: 1) Scarcity - unlimited wants, limited resources. 2) Supply and demand - price determined by availability vs desire. 3) Opportunity cost - what you give up to get something. 4) Market economy - prices set by supply/demand. 5) Inflation - general price increases over time. 6) GDP - total value of goods/services produced."
    
    # Literature topics
    elif any(word in message_lower for word in ['literature', 'poetry', 'writing', 'shakespeare', 'stories']):
        return "EDUCATION: Literature is artistic written expression exploring human experience. Elements: 1) Plot - sequence of events (exposition, rising action, climax, resolution). 2) Character - people in story, their development. 3) Setting - time and place. 4) Theme - central message. 5) Style - author's unique writing approach. 6) Literary devices - metaphor, symbolism, irony. Literature develops empathy, communication skills, cultural understanding."
    
    # Default educational response
    return "EDUCATION: This topic involves understanding fundamental principles, how different components interact, their relationships, and real-world applications. Learning requires building from basic concepts to more complex ideas, making connections between new and existing knowledge, and practicing application in various contexts."

# Legacy functions - keep for compatibility but redirect
async def handle_educational_question(user_message: str, context: str, openai_client) -> str:
    """Legacy function - redirects to data-only approach"""
    return get_educational_data(user_message)