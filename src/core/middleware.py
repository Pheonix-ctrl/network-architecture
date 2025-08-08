# src/core/middleware.py
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from typing import Callable
import time
import uuid
from ..utils.logging import MJLogger

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses"""
    
    def __init__(self, app, logger_name: str = "mj_network"):
        super().__init__(app)
        self.logger = MJLogger(logger_name)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start time
        start_time = time.time()
        
        # Log request
        self.logger.logger.info(
            "http_request_start",
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response
            self.logger.logger.info(
                "http_request_complete",
                request_id=request_id,
                status_code=response.status_code,
                process_time_ms=round(process_time * 1000, 2)
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
        
        except Exception as e:
            # Log error
            process_time = time.time() - start_time
            self.logger.logger.error(
                "http_request_error",
                request_id=request_id,
                error_type=type(e).__name__,
                error_message=str(e),
                process_time_ms=round(process_time * 1000, 2)
            )
            raise

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = {}  # In production, use Redis
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/docs", "/redoc"]:
            return await call_next(request)
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean old requests (simple cleanup)
        if client_ip in self.requests:
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if current_time - req_time < 60  # Last minute
            ]
        else:
            self.requests[client_ip] = []
        
        # Check rate limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            from .exceptions import raise_rate_limit_error
            raise_rate_limit_error(f"Rate limit exceeded: {self.requests_per_minute} requests per minute")
        
        # Add current request
        self.requests[client_ip].append(current_time)
        
        return await call_next(request)
