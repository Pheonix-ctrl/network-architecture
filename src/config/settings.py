# src/config/settings.py
from pydantic import BaseSettings, Field
from typing import Optional, List
import os

class Settings(BaseSettings):
    # App Configuration
    APP_NAME: str = "MJ Network"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=False, env="DEBUG")
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    
    # Database Configuration
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = Field(default=10, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")
    
    # Redis Configuration
    REDIS_URL: str = Field(..., env="REDIS_URL")
    REDIS_PASSWORD: Optional[str] = Field(None, env="REDIS_PASSWORD")
    
    # AI Services Configuration
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL")
    
    GEMINI_API_KEY: str = Field(..., env="GEMINI_API_KEY")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash", env="GEMINI_MODEL")
    
    PERPLEXITY_API_KEY: str = Field(..., env="PERPLEXITY_API_KEY")
    PERPLEXITY_MODEL: str = Field(default="llama-3.1-sonar-small-128k-online", env="PERPLEXITY_MODEL")
    
    # JWT Configuration
    JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    
    # WebSocket Configuration
    WEBSOCKET_MAX_CONNECTIONS: int = Field(default=1000, env="WEBSOCKET_MAX_CONNECTIONS")
    WEBSOCKET_PING_INTERVAL: int = Field(default=20, env="WEBSOCKET_PING_INTERVAL")
    WEBSOCKET_PING_TIMEOUT: int = Field(default=20, env="WEBSOCKET_PING_TIMEOUT")
    
    # Memory System Configuration
    MEMORY_EXTRACTION_BATCH_SIZE: int = Field(default=50, env="MEMORY_EXTRACTION_BATCH_SIZE")
    MEMORY_SIMILARITY_THRESHOLD: float = Field(default=0.75, env="MEMORY_SIMILARITY_THRESHOLD")
    MEMORY_TTL_HOURS: int = Field(default=24, env="MEMORY_TTL_HOURS")
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small", env="EMBEDDING_MODEL")
    
    # MJ Network Configuration
    P2P_DISCOVERY_PORT: int = Field(default=8888, env="P2P_DISCOVERY_PORT")
    P2P_MAX_PEERS: int = Field(default=50, env="P2P_MAX_PEERS")
    P2P_HEARTBEAT_INTERVAL: int = Field(default=30, env="P2P_HEARTBEAT_INTERVAL")
    
    # Mode System Configuration
    DEFAULT_MODE: str = Field(default="mj", env="DEFAULT_MODE")
    MODE_SWITCH_COOLDOWN: int = Field(default=300, env="MODE_SWITCH_COOLDOWN")  # 5 minutes
    KALKI_MODE_TIMEOUT: int = Field(default=1800, env="KALKI_MODE_TIMEOUT")    # 30 minutes
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    RATE_LIMIT_WINDOW: int = Field(default=60, env="RATE_LIMIT_WINDOW")
    
    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")
    
    # Security
    CORS_ORIGINS: List[str] = Field(default=["*"], env="CORS_ORIGINS")
    BCRYPT_ROUNDS: int = Field(default=12, env="BCRYPT_ROUNDS")
    
    # External Services
    ELEVENLABS_API_KEY: Optional[str] = Field(None, env="ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID: Optional[str] = Field(None, env="ELEVENLABS_VOICE_ID")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

