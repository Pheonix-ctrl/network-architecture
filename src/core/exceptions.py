
# src/core/exceptions.py
from typing import Optional, Dict, Any
from fastapi import HTTPException, status

class MJNetworkException(Exception):
    """Base exception for MJ Network"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class AuthenticationError(MJNetworkException):
    """Authentication related errors"""
    pass

class AuthorizationError(MJNetworkException):
    """Authorization related errors"""
    pass

class ValidationError(MJNetworkException):
    """Input validation errors"""
    pass

class MemoryError(MJNetworkException):
    """Memory system errors"""
    pass

class AIServiceError(MJNetworkException):
    """AI service related errors"""
    pass

class NetworkError(MJNetworkException):
    """MJ network communication errors"""
    pass

class DatabaseError(MJNetworkException):
    """Database operation errors"""
    pass

# HTTP Exception wrappers
def raise_authentication_error(message: str = "Authentication required"):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"}
    )

def raise_authorization_error(message: str = "Insufficient permissions"):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=message
    )

def raise_validation_error(message: str, field: str = None):
    detail = {"message": message}
    if field:
        detail["field"] = field
    
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=detail
    )

def raise_not_found_error(resource: str = "Resource"):
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource} not found"
    )

def raise_rate_limit_error(message: str = "Rate limit exceeded"):
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=message
    )

def raise_server_error(message: str = "Internal server error"):
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=message
    )

