# src/utils/logging.py
import logging
import sys
import json
from datetime import datetime
from typing import Dict, Any
import structlog

def setup_logging(level: str = "INFO", format_type: str = "json"):
    """Setup structured logging for the application"""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if format_type == "json" else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper())
    )
    
    # Get structlog logger
    logger = structlog.get_logger()
    
    return logger

class MJLogger:
    """Custom logger for MJ Network with contextual information"""
    
    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)
    
    def log_chat_interaction(
        self,
        user_id: int,
        message_length: int,
        mode: str,
        response_time_ms: int,
        tokens_used: int
    ):
        """Log chat interaction with metrics"""
        self.logger.info(
            "chat_interaction",
            user_id=user_id,
            message_length=message_length,
            personality_mode=mode,
            response_time_ms=response_time_ms,
            tokens_used=tokens_used
        )
    
    def log_memory_extraction(
        self,
        user_id: int,
        conversation_id: int,
        memories_extracted: int,
        success: bool
    ):
        """Log memory extraction results"""
        self.logger.info(
            "memory_extraction",
            user_id=user_id,
            conversation_id=conversation_id,
            memories_extracted=memories_extracted,
            success=success
        )
    
    def log_mj_network_event(
        self,
        event_type: str,
        user_id: int,
        details: Dict[str, Any]
    ):
        """Log MJ network events"""
        self.logger.info(
            "mj_network_event",
            event_type=event_type,
            user_id=user_id,
            **details
        )
    
    def log_error(
        self,
        error_type: str,
        error_message: str,
        user_id: int = None,
        context: Dict[str, Any] = None
    ):
        """Log errors with context"""
        self.logger.error(
            "error_occurred",
            error_type=error_type,
            error_message=error_message,
            user_id=user_id,
            context=context or {}
        )
    
    def log_performance_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "ms",
        context: Dict[str, Any] = None
    ):
        """Log performance metrics"""
        self.logger.info(
            "performance_metric",
            metric_name=metric_name,
            value=value,
            unit=unit,
            context=context or {}
        )
