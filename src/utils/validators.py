
# src/utils/validators.py
import re
from typing import List, Optional
from email_validator import validate_email, EmailNotValidError

def validate_password_strength(password: str) -> bool:
    """Validate password meets security requirements"""
    
    if len(password) < 8:
        return False
    
    # Check for uppercase letter
    if not re.search(r'[A-Z]', password):
        return False
    
    # Check for lowercase letter  
    if not re.search(r'[a-z]', password):
        return False
    
    # Check for digit
    if not re.search(r'\d', password):
        return False
    
    # Check for special character
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    
    return True

def validate_email_address(email: str) -> bool:
    """Validate email address format"""
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False

def validate_username(username: str) -> bool:
    """Validate username format"""
    
    # Length check
    if len(username) < 3 or len(username) > 50:
        return False
    
    # Alphanumeric and underscore only
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False
    
    # Must start with letter
    if not username[0].isalpha():
        return False
    
    return True

def validate_personality_mode(mode: str) -> bool:
    """Validate personality mode"""
    valid_modes = ['mj', 'kalki', 'jupiter', 'educational', 'healthcare']
    return mode.lower() in valid_modes

def validate_memory_type(memory_type: str) -> bool:
    """Validate memory type"""
    valid_types = ['personal', 'preference', 'skill', 'goal', 'relationship', 'fact']
    return memory_type.lower() in valid_types

def validate_share_level(share_level: str) -> bool:
    """Validate relationship share level"""
    valid_levels = ['basic', 'moderate', 'full']
    return share_level.lower() in valid_levels

def sanitize_input(text: str, max_length: int = None) -> str:
    """Sanitize user input"""
    
    # Strip whitespace
    text = text.strip()
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Limit length if specified
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text

def validate_mj_id(mj_id: str) -> bool:
    """Validate MJ instance ID format"""
    # Format: MJ-xxxxxxxx (8 hex characters)
    pattern = r'^MJ-[a-fA-F0-9]{8}$'
    return bool(re.match(pattern, mj_id))
