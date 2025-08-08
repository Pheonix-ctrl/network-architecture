
# src/main.py
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import asyncio

from .config.settings import Settings
from .config.database import engine, Base
from .services.websocket.manager import ConnectionManager
from .services.websocket.handlers import WebSocketHandler
from .services.memory.manager import MemoryManager
from .services.memory.redis_client import RedisClient
from .services.network.discovery import MJDiscoveryService
from .api.v1 import auth, chat, memory, network, websocket
from .core.dependencies import get_current_user, get_authenticated_user
from .utils.logging import setup_logging
from .models.database.user import User

# Settings
settings = Settings()

# Global instances
connection_manager = ConnectionManager()
redis_client = RedisClient()
mj_discovery_service = MJDiscoveryService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Setup logging
    setup_logging(settings.LOG_LEVEL, settings.LOG_FORMAT)
    
    # Connect to Redis
    await redis_client.connect()
    
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Database tables created/verified")
    print("✅ Redis connected")
    print("🌐 MJ Network ready for connections")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down MJ Network...")
    
    # Stop discovery service
    await mj_discovery_service.stop_discovery()
    
    # Disconnect Redis
    await redis_client.disconnect()
    
    # Close database connections
    await engine.dispose()
    
    print("👋 MJ Network shutdown complete")

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Revolutionary AI companion network with emotional intelligence and P2P communication",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure properly for production
    )

# Include API routes
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(memory.router, prefix="/api/v1", tags=["Memory"])
app.include_router(network.router, prefix="/api/v1", tags=["MJ Network"])

# WebSocket endpoint
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
    # Note: WebSocket authentication would be handled differently
    # For now, we'll trust the user_id parameter
):
    """Main WebSocket endpoint for real-time communication"""
    await connection_manager.connect(websocket, user_id)
    
    # Initialize memory manager for this user
    from .config.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        memory_manager = MemoryManager(db)
        await memory_manager.start_background_worker()
        
        # Initialize WebSocket handler
        ws_handler = WebSocketHandler(connection_manager, memory_manager)
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                message_type = message_data.get("type")
                
                if message_type == "chat":
                    # Handle chat message
                    session_data = connection_manager.get_user_session(user_id)
                    response = await ws_handler.handle_chat_message(
                        user_id=user_id,
                        message=message_data.get("content", ""),
                        session_data=session_data or {}
                    )
                    
                    # Send response
                    await connection_manager.send_personal_message(user_id, {
                        "type": "chat_response",
                        "response": response.dict()
                    })
                
                elif message_type == "mode_change":
                    # Handle mode change request
                    await ws_handler.handle_mode_request(
                        user_id=user_id,
                        requested_mode=message_data.get("mode", "mj")
                    )
                
                elif message_type == "memory_query":
                    # Handle memory search
                    await ws_handler.handle_memory_query(
                        user_id=user_id,
                        query=message_data.get("query", "")
                    )
                
                elif message_type == "mj_discovery":
                    # Handle MJ network discovery
                    nearby_mjs = await mj_discovery_service.discover_nearby_mjs()
                    await connection_manager.send_mj_network_event(user_id, {
                        "event_type": "discovery_results",
                        "nearby_mjs": nearby_mjs
                    })
        
        except WebSocketDisconnect:
            connection_manager.disconnect(user_id)
            await memory_manager.stop_background_worker()
        except Exception as e:
            print(f"WebSocket error for user {user_id}: {e}")
            connection_manager.disconnect(user_id)
            await memory_manager.stop_background_worker()

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "websocket": "/ws/{user_id}"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower()
    )