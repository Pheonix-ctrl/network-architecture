
# src/utils/crypto.py
import secrets
import hashlib
from cryptography.fernet import Fernet
from typing import str, bytes

def generate_secret_key() -> str:
    """Generate a secure random secret key"""
    return secrets.token_urlsafe(32)

def generate_mj_instance_id(user_id: int, username: str) -> str:
    """Generate unique MJ instance ID"""
    data = f"{user_id}:{username}:{secrets.token_hex(4)}"
    hash_obj = hashlib.md5(data.encode())
    return f"MJ-{hash_obj.hexdigest()[:8]}"

def encrypt_sensitive_data(data: str, key: bytes) -> bytes:
    """Encrypt sensitive data"""
    f = Fernet(key)
    return f.encrypt(data.encode())

def decrypt_sensitive_data(encrypted_data: bytes, key: bytes) -> str:
    """Decrypt sensitive data"""
    f = Fernet(key)
    return f.decrypt(encrypted_data).decode()

def hash_content(content: str) -> str:
    """Create hash of content for deduplication"""
    return hashlib.sha256(content.encode()).hexdigest()

def generate_session_id() -> str:
    """Generate secure session ID"""
    return secrets.token_urlsafe(16)