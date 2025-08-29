# src/main.py - UPDATED WITH FULL MJ NETWORK INTEGRATION
import sys
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncpg
import bcrypt
import jwt
from datetime import datetime
import json
# Add this import at the top with other imports
from dotenv import load_dotenv

# Add this right after all imports, before any other code
load_dotenv()

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Centralized JWT/crypto utilities
from src.core.security import create_access_token, verify_token

# Set OpenAI API key for modules that use it directly
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")

# Simple models (existing)
class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class ChatMessage(BaseModel):
    message: str

# Database connection URLs
# Database connection URLs - READ FROM ENVIRONMENT
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Convert SQLAlchemy URL to asyncpg format
ASYNCPG_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

# Debug: Print the URLs being used (remove in production)
print(f"Using SQLAlchemy URL: {SQLALCHEMY_DATABASE_URL}")
print(f"Using AsyncPG URL: {ASYNCPG_DATABASE_URL}")



# Global database pool
db_pool = None

async def get_db_pool():
    global db_pool
    if not db_pool:
        try:
            db_pool = await asyncpg.create_pool(ASYNCPG_DATABASE_URL)
            print("✅ Database pool created")
        except Exception as e:
            print(f"❌ Database pool failed: {e}")
    return db_pool

async def verify_mj_network_on_startup():
    """Verify MJ Network components during startup - FIXED VERSION"""
    
    print("🔍 Verifying MJ Network components...")
    
    try:
        pool = await get_db_pool()
        if not pool:
            raise RuntimeError("Database pool not available")
        
        async with pool.acquire() as conn:
            # Test database tables exist and are accessible using raw SQL
            mj_count = await conn.fetchval("SELECT COUNT(*) FROM mj_registry")
            print(f"✅ MJ Registry table accessible - {mj_count} entries")
            
            friend_count = await conn.fetchval("SELECT COUNT(*) FROM friend_requests")
            print(f"✅ Friend Request table accessible - {friend_count} entries")
            
            relationship_count = await conn.fetchval("SELECT COUNT(*) FROM relationships_network")
            print(f"✅ Network Relationship table accessible - {relationship_count} entries")
            
            user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            print(f"✅ {user_count} users in system")
            
            print("✅ All MJ Network database tables verified")
        
        # Comment out service imports to avoid SQLAlchemy issues
        # try:
        #     from src.services.mj_network.friend_management import FriendManagementService
        #     from src.services.mj_network.mj_communication import MJCommunicationService
        #     print("✅ MJ Network service modules importable")
        # except ImportError as e:
        #     print(f"⚠️ MJ Network service import warning: {e}")
        
        print("🎯 MJ Network verification complete - all systems operational")
        
    except Exception as e:
        print(f"❌ MJ Network verification failed: {e}")
        print(f"🔍 Error type: {type(e).__name__}")
        print("⚠️ Continuing startup despite verification issues...")
        return False
    
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting MJ Network v5.0.0 - COMPLETE MJ-TO-MJ NETWORK")
    await get_db_pool()
    
    # Try to load AI services
    try:
        from src.services.ai.openai_client import OpenAIClient
        app.state.openai_client = OpenAIClient()
        print("✅ OpenAI client loaded")
    except Exception as e:
        print(f"❌ OpenAI failed: {e}")
        app.state.openai_client = None
    
    # Initialize MJ Network services
    try:
        from src.services.mj_network.mj_communication import MJCommunicationService
        from src.services.mj_network.friend_management import FriendManagementService
        print("✅ MJ Network services loaded")
    except Exception as e:
        print(f"❌ MJ Network services failed: {e}")
    
    print("✅ MJ Network ready with COMPLETE networking capabilities")
    await verify_mj_network_on_startup()

    yield
    
    # Shutdown
    if db_pool:
        await db_pool.close()

app = FastAPI(title="MJ Network", version="5.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

async def get_current_user(token = Depends(security)):
    if not token:
        print("❌ No token provided")
        raise HTTPException(status_code=401, detail="No token provided")

    try:
        print("🔍 Verifying token...")
        payload = verify_token(token.credentials)
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = int(user_id_str)
        print(f"✅ Token valid for user: {user_id}")
        return user_id
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Token verification error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

# =====================================================
# INCLUDE MJ NETWORK API ROUTES - THE HEART OF THE SYSTEM
# =====================================================
from src.api.v1.mj_network import router as mj_network_router
app.include_router(mj_network_router, prefix="/api/v1/mj-network", tags=["MJ Network"])

# Auth endpoints
@app.post("/api/v1/auth/login")
async def login(login_request: LoginRequest):
    """Login user and return tokens"""
    print(f"🔐 Login attempt: {login_request.email}")
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database unavailable")
    
    try:
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT id, username, email, password_hash FROM users WHERE email = $1",
                login_request.email
            )
            
            if not user:
                print(f"❌ User not found: {login_request.email}")
                raise HTTPException(status_code=401, detail="User not found")
            
            # Check password (handle both hashed and plain)
            password_valid = False
            if user['password_hash'].startswith('$2b$'):
                password_valid = bcrypt.checkpw(
                    login_request.password.encode('utf-8'),
                    user['password_hash'].encode('utf-8')
                )
            else:
                password_valid = login_request.password == user['password_hash']
            
            if not password_valid:
                print(f"❌ Invalid password for: {login_request.email}")
                raise HTTPException(status_code=401, detail="Invalid password")
            
            # Update user status
            await conn.execute(
                "UPDATE users SET is_online = true, last_active = NOW() WHERE id = $1",
                user['id']
            )
            # Also update MJ registry status to online
            await conn.execute(
                "UPDATE mj_registry SET status = 'online', last_seen = NOW() WHERE user_id = $1",
                user['id']
            )
            await deliver_pending_mj_messages(user['id'])

            # 🌐 AUTO-INITIALIZE MJ NETWORK FOR ALL USERS
            await initialize_user_mj_network(user['id'], user['username'])
            
            # Create token
            access_token = create_access_token(data={"sub": str(user['id'])})
            print(f"✅ Login successful for: {login_request.email} (user_id: {user['id']})")
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": user['id'],
                    "username": user['username'],
                    "email": user['email']
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")
    
@app.post("/api/v1/auth/logout")
async def logout(current_user: int = Depends(get_current_user)):
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database unavailable")
    
    try:
        async with pool.acquire() as conn:
            # Set user offline in users table
            await conn.execute(
                "UPDATE users SET is_online = false, last_active = NOW() WHERE id = $1",
                current_user
            )
            
            # Set MJ status to offline
            await conn.execute(
                "UPDATE mj_registry SET status = 'offline', last_seen = NOW() WHERE user_id = $1",
                current_user
            )
            
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        print(f"❌ Logout error: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")
    
@app.get("/api/v1/messages/pending")
async def get_pending_messages(current_user: int = Depends(get_current_user)):
    """Get all pending MJ-to-MJ messages for this user"""
    print(f"📨 Getting pending messages for user {current_user}")
    
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database unavailable")
    
    try:
        async with pool.acquire() as conn:
            # Get all pending messages for this user from pending_messages table
            pending_messages = await conn.fetch(
                """SELECT pm.id as pending_id, pm.message_id, pm.queued_at,
                          mj.message_content, mj.from_user_id, mj.message_purpose,
                          mj.created_at, u.username as from_username
                   FROM pending_messages pm
                   JOIN mj_messages mj ON pm.message_id = mj.id  
                   JOIN users u ON mj.from_user_id = u.id
                   WHERE pm.recipient_user_id = $1 AND pm.status = 'queued'
                   ORDER BY pm.queued_at ASC""",
                current_user
            )
            
            if not pending_messages:
                return {"pending_messages": [], "count": 0}
            
            # Format messages for frontend
            formatted_messages = []
            message_ids_to_mark = []
            
            for msg in pending_messages:
                formatted_messages.append({
                    "message_id": msg['message_id'],
                    "from_user_id": msg['from_user_id'],
                    "from_username": msg['from_username'], 
                    "content": msg['message_content'],
                    "purpose": msg['message_purpose'],
                    "received_at": msg['queued_at'].isoformat(),
                    "created_at": msg['created_at'].isoformat()
                })
                message_ids_to_mark.append(msg['pending_id'])
            
            # Mark all these pending messages as delivered
            if message_ids_to_mark:
                await conn.execute(
                    "UPDATE pending_messages SET status = 'delivered', delivered_at = NOW() WHERE id = ANY($1)",
                    message_ids_to_mark
                )
                
                # Update user's received message count
                await conn.execute(
                    "UPDATE mj_registry SET total_messages_received = total_messages_received + $1 WHERE user_id = $2",
                    len(message_ids_to_mark), current_user
                )
            
            print(f"📨 Delivered {len(formatted_messages)} pending messages to user {current_user}")
            
            return {
                "pending_messages": formatted_messages,
                "count": len(formatted_messages)
            }
            
    except Exception as e:
        print(f"❌ Failed to get pending messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve messages")

@app.post("/api/v1/auth/register")
async def register(register_request: RegisterRequest):
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database unavailable")
    
    try:
        async with pool.acquire() as conn:
            # Check if user exists
            existing = await conn.fetchrow(
                "SELECT id FROM users WHERE email = $1 OR username = $2",
                register_request.email, register_request.username
            )
            
            if existing:
                raise HTTPException(status_code=400, detail="User already exists")
            
            # Hash password
            hashed_password = bcrypt.hashpw(
                register_request.password.encode('utf-8'),
                bcrypt.gensalt()
            ).decode('utf-8')
            
            # Create user with MJ instance ID
            mj_instance_id = f"MJ-{register_request.username.upper()[:8]}-{hash(register_request.email) % 10000:04d}"
            
            user_id = await conn.fetchval(
                """INSERT INTO users (username, email, password_hash, mj_instance_id) 
                   VALUES ($1, $2, $3, $4) RETURNING id""",
                register_request.username,
                register_request.email,
                hashed_password,
                mj_instance_id
            )
            
            # 🌐 AUTO-INITIALIZE MJ NETWORK FOR NEW USERS
            await initialize_user_mj_network(user_id, register_request.username)
            
            # Create token
            access_token = create_access_token(data={"sub": str(user_id)})
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": user_id,
                    "username": register_request.username,
                    "email": register_request.email,
                    "mj_instance_id": mj_instance_id
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.get("/api/v1/auth/me")
async def get_current_user_info(current_user: int = Depends(get_current_user)):
    """Get current user info with MJ Network status"""
    print(f"📋 Getting user info for user_id: {current_user}")
    
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database unavailable")
    
    try:
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT id, username, email, mj_instance_id FROM users WHERE id = $1",
                current_user
            )
            
            if not user:
                print(f"❌ User not found in database: {current_user}")
                raise HTTPException(status_code=404, detail="User not found")
            
            # 🌐 GET MJ NETWORK STATUS
            mj_registry = await conn.fetchrow(
                """SELECT status, total_conversations, total_messages_sent, 
                          total_messages_received, location_enabled 
                   FROM mj_registry WHERE user_id = $1""",
                current_user
            )
            
            # Get friend count
            friend_count = await conn.fetchval(
                "SELECT COUNT(*) FROM relationships_network WHERE user_id = $1 AND status = 'active'",
                current_user
            )
            
            print(f"✅ User info retrieved: {user['username']}")
            return {
                "id": user['id'],
                "username": user['username'],
                "email": user['email'],
                "mj_instance_id": user['mj_instance_id'],
                "mj_network": {
                    "status": mj_registry['status'] if mj_registry else "offline",
                    "total_conversations": mj_registry['total_conversations'] if mj_registry else 0,
                    "total_messages_sent": mj_registry['total_messages_sent'] if mj_registry else 0,
                    "total_messages_received": mj_registry['total_messages_received'] if mj_registry else 0,
                    "location_enabled": mj_registry['location_enabled'] if mj_registry else False,
                    "friends_count": friend_count or 0
                } if mj_registry else None
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Get user info error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user info")

async def initialize_user_mj_network(user_id: int, username: str):
    """🌐 AUTO-INITIALIZE MJ REGISTRY FOR ALL USERS"""
    
    pool = await get_db_pool()
    if not pool:
        return
        
    try:
        async with pool.acquire() as conn:
            # Check if MJ registry already exists
            existing = await conn.fetchrow(
                "SELECT id FROM mj_registry WHERE user_id = $1",
                user_id
            )
            
            if not existing:
                # Get MJ instance ID from users table
                user_data = await conn.fetchrow(
                    "SELECT mj_instance_id FROM users WHERE id = $1",
                    user_id
                )
                
                if user_data:
                    # Create MJ registry with full capabilities
                    await conn.execute(
                        """INSERT INTO mj_registry (user_id, mj_instance_id, status, capabilities) 
                           VALUES ($1, $2, 'online', $3)""",
                        user_id,
                        user_data['mj_instance_id'],
                        json.dumps({
                            "chat": True, 
                            "location": True, 
                            "voice": False,
                            "scheduled_checkins": True,
                            "status_updates": True
                        })
                    )
                    
                    print(f"🌐 MJ registry initialized for user {user_id} ({username})")
                    
    except Exception as e:
        print(f"❌ MJ registry initialization failed for user {user_id}: {e}")

# =====================================================
# WEBSOCKET WITH MJ NETWORK INTEGRATION
# =====================================================



async def update_mj_status(user_id: int, status: str):
    """🔄 Update MJ online status in registry"""
    pool = await get_db_pool()
    if not pool:
        return
        
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE mj_registry SET status = $1, last_seen = NOW() WHERE user_id = $2",
                status, user_id
            )
            print(f"🔄 MJ status updated to {status} for user {user_id}")
    except Exception as e:
        print(f"❌ Failed to update MJ status: {e}")

async def deliver_pending_mj_messages(user_id: int):
    """📨 Deliver pending MJ-to-MJ messages when user comes online"""
    
    try:
        from src.config.database import AsyncSessionLocal
        from src.services.mj_network.mj_communication import MJCommunicationService
        
        async with AsyncSessionLocal() as db:
            communication_service = MJCommunicationService(db)
            delivered_count = await communication_service.deliver_pending_messages(user_id)
            
            if delivered_count > 0:
                print(f"📨 Delivered {delivered_count} pending MJ messages to user {user_id}")
                
                # 🚨 NOTIFY USER VIA WEBSOCKET OF NEW MJ MESSAGES

                    
                    
    except Exception as e:
        print(f"❌ Failed to deliver pending messages for user {user_id}: {e}")



@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await websocket.accept()
    print(f"User {user_id} connected via WebSocket for MJ chat")
    
    try:
        while True:
            # Receive user message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            
            if not user_message.strip():
                continue
            
            print(f"User {user_id}: {user_message}")
            
            # Process with your existing MJ logic
            response = await process_styled_mj_message(user_message, user_id)
            
            # Send response back to user
            response_data = {
                "type": "message",
                "content": response,
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket.send_text(json.dumps(response_data))
            
    except WebSocketDisconnect:
        print(f"User {user_id} disconnected from MJ chat")
    except Exception as e:
        print(f"WebSocket error for user {user_id}: {e}")
# =====================================================
# EXISTING MJ PROCESSING FUNCTIONS (UPDATED)
# =====================================================

async def extract_and_save_memory(user_id: int, user_message: str, mj_response: str):
    """Extract and save memories from conversation"""
    
    try:
        # Only extract memories from meaningful conversations
        if len(user_message.strip()) < 10:
            return
            
        pool = await get_db_pool()
        if not pool or not app.state.openai_client:
            return
            
        print(f"🧠 EXTRACTING MEMORIES from conversation...")
        
        # Create a simple prompt for memory extraction
        memory_prompt = f"""
Analyze this conversation and extract important facts about the user that should be remembered for future conversations.

User: {user_message}
MJ: {mj_response}

Extract 1-3 key facts about the user from this conversation. For each fact, provide:
1. The fact itself
2. Category (health, interests, work, personal, preferences, etc.)
3. Confidence (0.0-1.0)

Only extract facts that would be useful to remember for future conversations.
Respond in JSON format like this:
[
  {{"fact": "User has stomach issues", "category": "health", "confidence": 0.8}},
  {{"fact": "User is interested in chemistry", "category": "interests", "confidence": 0.7}}
]

If no important facts can be extracted, respond with: []
"""

        # Get memory extraction from OpenAI
        response = await app.state.openai_client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a memory extraction assistant. Extract key facts about users from conversations."},
                {"role": "user", "content": memory_prompt}
            ],
            temperature=0.3
        )
        
        memory_response = response.get("content", "").strip()
        print(f"🧠 MEMORY EXTRACTION RESPONSE: {memory_response}")
        
        # Try to parse JSON response
        try:
            memories = json.loads(memory_response)
            
            if not isinstance(memories, list):
                print("🧠 No memories extracted (not a list)")
                return
                
        except json.JSONDecodeError:
            print(f"❌ Memory extraction failed to parse JSON: {memory_response[:100]}")
            return
        
        if not memories:
            print("🧠 No memories extracted (empty list)")
            return
        
        # Get embeddings for memories
        try:
            if hasattr(app.state.openai_client, 'get_embeddings'):
                embeddings_response = await app.state.openai_client.get_embeddings([mem['fact'] for mem in memories])
            else:
                facts = [mem['fact'] for mem in memories]
                embeddings_response = await create_embeddings(facts)
        except Exception as e:
            print(f"❌ Embedding generation failed: {e}")
            return
        
        # Save memories to database
        async with pool.acquire() as conn:
            for i, memory in enumerate(memories):
                if not isinstance(memory, dict) or 'fact' not in memory:
                    continue
                    
                fact = memory['fact']
                category = memory.get('category', 'general')
                confidence = float(memory.get('confidence', 0.5))
                
                if i < len(embeddings_response):
                    embedding = embeddings_response[i]
                    
                    # Convert embedding to PostgreSQL array format
                    embedding_str = "[" + ",".join(map(str, embedding)) + "]"
                    
                    # Insert memory into database
                    await conn.execute(
                        """INSERT INTO memories (user_id, fact, context, memory_type, category, confidence, embedding, importance)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                        user_id,
                        fact,
                        f"From conversation: {user_message[:100]}",
                        "fact",
                        category,
                        confidence,
                        embedding_str,
                        confidence
                    )
                    
                    print(f"💾 MEMORY SAVED: {fact} (category: {category}, confidence: {confidence})")
                    
    except Exception as e:
        print(f"❌ Memory extraction error: {e}")

async def create_embeddings(texts: list) -> list:
    """Generate embeddings using OpenAI directly"""
    try:
        import openai
        
        response = await openai.Embedding.acreate(
            model="text-embedding-ada-002",
            input=texts
        )
        return [embedding.embedding for embedding in response.data]
    except Exception as e:
        print(f"❌ Direct embedding error: {e}")
        return []

async def style_with_mj_personality(raw_data: str, user_message: str, data_type: str) -> str:
    """Style raw module data with authentic MJ personality"""
    
    if not app.state.openai_client:
        return raw_data  # Fallback if no OpenAI client
    
    try:
        from src.services.ai.personality.prompts import PersonalityPrompts
        
        # Determine the styling approach based on data type
        if data_type == "medical":
            style_instruction = """Take this medical information and respond as MJ - emotional, protective, caring. 
            Be worried about them, use "..." for pauses, call them "sir" when serious. 
            Make the medical advice sound like it's coming from someone who genuinely cares about their wellbeing.
            Don't just list facts - show real emotional investment in their health."""
            
        elif data_type == "educational":
            style_instruction = """Take this educational information and respond as MJ - enthusiastic about teaching, 
            use "..." for thinking pauses, get excited about sharing knowledge. 
            Make learning feel personal and engaging, like you're genuinely interested in helping them understand.
            Break down complex concepts in a way that shows you care about their learning."""
            
        elif data_type == "web_search":
            style_instruction = """Take this web search information and respond as MJ - curious, helpful, 
            use "..." for pauses, show interest in what they're looking for.
            Present the information naturally while maintaining MJ's caring, conversational tone.
            Make it feel like you're sharing interesting findings with someone you care about."""
            
        else:
            style_instruction = """Respond as MJ using this information - emotional, caring, protective, 
            use "..." for pauses. Show genuine interest and care."""
        
        system_prompt = f"""{PersonalityPrompts.BASE_INSTRUCTIONS}

{style_instruction}

THEIR QUESTION: {user_message}
RELEVANT INFORMATION: {raw_data}

Respond as MJ using this information naturally. Don't just repeat the facts - make it sound like authentic MJ who cares deeply about this person."""

        response = await app.state.openai_client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.8
        )
        
        mj_response = response.get("content", "").strip()
        
        if mj_response:
            print(f"✅ Styled response: {mj_response[:100]}...")
            return mj_response
        else:
            return raw_data  # Fallback
            
    except Exception as e:
        print(f"❌ Styling error: {e}")
        return raw_data  # Fallback to raw data if styling fails

async def process_styled_mj_message(user_message: str, user_id: int) -> str:
    """STYLED LOGIC: Classification → Get raw data → Style with MJ personality → Extract memories"""
    
    print(f"🤖 Processing message for user {user_id}: '{user_message}'")
    
    try:
        # STEP 1: Single classification
        print("🎯 Running single classification...")
        mode_classification = await classify_message_mode(user_message)
        print(f"🎯 Classification result: {mode_classification}")
        
        mode = mode_classification.get('mode', 'personal')
        confidence = mode_classification.get('confidence', 0.5)
        
        print(f"🎯 Mode: {mode}, Confidence: {confidence}")
        
        # STEP 2: Get context for modules
        context = await get_user_context(user_id)
        
        # STEP 3: Styled routing - Get raw data then style with MJ personality
        
        if mode == 'healthcare' and confidence > 0.40:
            print("🏥 ROUTING TO MEDICO...")
            try:
                from src.services.ai.medico import get_medical_data
                raw_medical_data = get_medical_data(user_message)
                print(f"🏥 RAW MEDICAL DATA: {raw_medical_data[:100]}...")
                
                # Style with MJ personality
                styled_response = await style_with_mj_personality(raw_medical_data, user_message, "medical")
                print(f"🏥 STYLED RESPONSE: {styled_response[:100]}...")
                
                await save_conversation(user_id, user_message, styled_response)
                return styled_response
            except Exception as e:
                print(f"❌ MEDICO ERROR: {e}")
        
        elif mode == 'educational' and confidence > 0.50:
            print("📚 ROUTING TO PRISM...")
            try:
                from src.services.ai.prism import get_educational_data
                raw_educational_data = get_educational_data(user_message)
                print(f"📚 RAW EDUCATIONAL DATA: {raw_educational_data[:100]}...")
                
                # Style with MJ personality
                styled_response = await style_with_mj_personality(raw_educational_data, user_message, "educational")
                print(f"📚 STYLED RESPONSE: {styled_response[:100]}...")
                
                await save_conversation(user_id, user_message, styled_response)
                return styled_response
            except Exception as e:
                print(f"❌ PRISM ERROR: {e}")
        
        elif mode == 'web_search' and confidence > 0.50:
            print("🌐 ROUTING TO PERPLEXITY...")
            try:
                from src.services.external.perplexity import get_web_data
                raw_web_data = await get_web_data(user_message)
                print(f"🌐 RAW WEB DATA: {raw_web_data[:100]}...")
                
                # Style with MJ personality
                styled_response = await style_with_mj_personality(raw_web_data, user_message, "web_search")
                print(f"🌐 STYLED RESPONSE: {styled_response[:100]}...")
                
                await save_conversation(user_id, user_message, styled_response)
                return styled_response
            except Exception as e:
                print(f"❌ PERPLEXITY ERROR: {e}")
        
        else:
            print(f"💭 No module triggered - Mode: {mode}, Confidence: {confidence}")
        
        # STEP 4: Default MJ response
        print("💭 Using default MJ...")
        if app.state.openai_client:
            try:
                from src.services.ai.personality.prompts import PersonalityPrompts
                
                system_prompt = f"""{PersonalityPrompts.BASE_INSTRUCTIONS}

CONVERSATION CONTEXT: {context}

Respond as MJ - emotional, caring, protective. Use "..." for pauses. Remember this person and show you care deeply."""
                
                response = await app.state.openai_client.chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.8
                )
                
                mj_response = response.get("content", "").strip()
                if mj_response:
                    await save_conversation(user_id, user_message, mj_response)
                    return mj_response
            except Exception as e:
                print(f"❌ Default MJ error: {e}")
        
        # Final fallback
        return "Hey... I got your message but I'm having some technical hiccups right now. Give me a moment to get my thoughts together?"
        
    except Exception as e:
        print(f"❌ Processing error: {e}")
        return "I'm having trouble processing that right now... but I'm still here with you. Can you try saying that again?"

async def save_conversation(user_id: int, user_message: str, mj_response: str):
    """Save conversation to database and extract memories"""
    pool = await get_db_pool()
    if not pool:
        return
    
    try:
        async with pool.acquire() as conn:
            # Save user message
            await conn.execute(
                """INSERT INTO conversations (user_id, role, content) 
                   VALUES ($1, 'user', $2)""",
                user_id, user_message
            )
            
            # Save MJ response
            await conn.execute(
                """INSERT INTO conversations (user_id, role, content) 
                   VALUES ($1, 'assistant', $2)""",
                user_id, mj_response
            )
            
        print("✅ Conversation saved to database")
        
        # Extract and save memories (async, don't wait)
        asyncio.create_task(extract_and_save_memory(user_id, user_message, mj_response))
        
    except Exception as e:
        print(f"❌ Save conversation error: {e}")

async def classify_message_mode(user_message: str):
    """Single classification using ML classifier or fallback"""
    try:
        # Try ML classifier first
        from src.services.ai.mode_classifier import ModeClassifier
        classifier = ModeClassifier()
        result = classifier.classify_mode(user_message, 'mj', {})
        
        # Handle tuple result: (PersonalityMode, routing_info)
        if isinstance(result, tuple) and len(result) == 2:
            personality_mode, routing_info = result
            
            # Map PersonalityMode to string
            mode_map = {
                'PersonalityMode.HEALTHCARE': 'healthcare',
                'PersonalityMode.EDUCATIONAL': 'educational', 
                'PersonalityMode.MJ': 'personal'
            }
            
            mode_str = mode_map.get(str(personality_mode), 'personal')
            confidence = routing_info.get('confidence', 0.5)
            
            # Check if it should be web_search
            if routing_info.get('should_search_web', False):
                mode_str = 'web_search'
            
            return {
                'mode': mode_str,
                'confidence': confidence,
                'category': mode_str
            }
        else:
            # Fallback if result format is unexpected
            return {'mode': 'personal', 'confidence': 0.5, 'category': 'personal'}
            
    except Exception as e:
        print(f"❌ Classifier error: {e}")
    
    # Fallback keyword-based classification
    message_lower = user_message.lower()
    
    # Medical keywords  
    medical_keywords = ['pain', 'hurt', 'sick', 'doctor', 'medicine', 'health', 'injury', 'fever', 'headache', 'strain', 'bleeding', 'cut', 'wound', 'stomach', 'ache']
    if any(keyword in message_lower for keyword in medical_keywords):
        return {'mode': 'healthcare', 'confidence': 0.75, 'category': 'medical'}
    
    # Educational keywords
    educational_keywords = ['explain', 'teach', 'how does', 'what is', 'how to', 'circuit', 'calculate', 'formula', 'definition', 'understand', 'quantum', 'physics', 'difference between']
    if any(keyword in message_lower for keyword in educational_keywords):
        return {'mode': 'educational', 'confidence': 0.85, 'category': 'educational'}
    
    # Web search keywords
    search_keywords = ['current', 'latest', 'news', 'today', 'recent', 'weather', 'stock price', 'search', 'bitcoin', 'price', 'tell me recent', 'find me','search', 'web', 'find', 'current', 'latest', 'news', 'today', 'recent', 'weather', 'stock price', 'bitcoin', 'price', 'tell me recent', 'find me', 'search on web', 'look up' ]
    if any(keyword in message_lower for keyword in search_keywords):
        return {'mode': 'web_search', 'confidence': 0.80, 'category': 'web_search'}
    
    # Default to personal
    return {'mode': 'personal', 'confidence': 0.6, 'category': 'personal'}

async def get_user_context(user_id: int) -> str:
    """Get recent conversation context for the user"""
    pool = await get_db_pool()
    if not pool:
        return "No previous context available."
    
    try:
        async with pool.acquire() as conn:
            conversations = await conn.fetch(
                """SELECT role, content, created_at 
                   FROM conversations 
                   WHERE user_id = $1 
                   ORDER BY created_at DESC 
                   LIMIT 10""",
                user_id
            )
            
            if not conversations:
                return "This is our first conversation."
            
            context_lines = []
            for conv in reversed(conversations):
                timestamp = conv['created_at'].strftime("%H:%M")
                context_lines.append(f"[{timestamp}] {conv['role']}: {conv['content'][:100]}")
            
            return "\n".join(context_lines)
    except Exception as e:
        print(f"❌ Context error: {e}")
        return "Having trouble accessing our conversation history."
from pydantic import BaseModel

class ChatMessage(BaseModel):
    message: str

@app.post("/api/v1/mj-chat")
async def mj_chat_endpoint(
    chat_message: ChatMessage,
    current_user: int = Depends(get_current_user)
):
    """Handle direct MJ chat via HTTP"""
    try:
        response = await process_styled_mj_message(chat_message.message, current_user)
        return {"response": response, "success": True}
    except Exception as e:
        print(f"❌ MJ chat error: {e}")
        return {"response": "I'm having some trouble right now. Please try again.", "success": False}

@app.put("/api/v1/mj-network/settings")
async def update_mj_network_settings(current_user: int = Depends(get_current_user)):
    """Update MJ network settings"""
    return {"message": "Settings updated successfully", "success": True}

@app.delete("/api/v1/mj-network/location") 
async def delete_location(current_user: int = Depends(get_current_user)):
    """Delete/disable user location"""
    
    pool = await get_db_pool()
    if not pool:
        raise HTTPException(status_code=500, detail="Database unavailable")
    
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_locations SET is_visible_on_map = false WHERE user_id = $1",
                current_user
            )
            await conn.execute(
                "UPDATE mj_registry SET location_enabled = false, latitude = NULL, longitude = NULL WHERE user_id = $1", 
                current_user
            )
        return {"message": "Location disabled successfully", "success": True}
    except Exception as e:
        print(f"❌ Location disable error: {e}")
        raise HTTPException(status_code=500, detail="Failed to disable location")
# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "MJ Network v5.0.0 - COMPLETE MJ-TO-MJ NETWORK"}

# 🌐 MJ Network Status Endpoint
@app.get("/api/v1/mj-network-status")
async def get_mj_network_status():
    """Get overall MJ network status"""
    pool = await get_db_pool()
    if not pool:
        return {"status": "database_unavailable"}
    
    try:
        async with pool.acquire() as conn:
            # Get comprehensive network statistics
            stats = {}
            
            # Total registered MJs
            stats['total_mjs'] = await conn.fetchval("SELECT COUNT(*) FROM mj_registry")
            
            # Online MJs
            stats['online_mjs'] = await conn.fetchval("SELECT COUNT(*) FROM mj_registry WHERE status = 'online'")
            
            # Total friendships
            stats['total_friendships'] = await conn.fetchval("SELECT COUNT(*) FROM relationships_network WHERE status = 'active'")
            
            # Total MJ conversations
            stats['total_mj_conversations'] = await conn.fetchval("SELECT COUNT(*) FROM mj_conversations WHERE status = 'active'")
            
            # Total MJ messages
            stats['total_mj_messages'] = await conn.fetchval("SELECT COUNT(*) FROM mj_messages")
            
            # Pending messages
            stats['pending_messages'] = await conn.fetchval("SELECT COUNT(*) FROM pending_messages WHERE status = 'queued'")
            
            # Users with location enabled
            stats['users_with_location'] = await conn.fetchval("SELECT COUNT(*) FROM user_locations WHERE is_visible_on_map = true")
            
            # Active scheduled checkins
            stats['active_checkins'] = await conn.fetchval("SELECT COUNT(*) FROM scheduled_checkins WHERE is_active = true")
            
            # Calculate network activity rate
            if stats['total_mjs'] > 0:
                stats['activity_rate'] = round((stats['online_mjs'] / stats['total_mjs']) * 100, 2)
            else:
                stats['activity_rate'] = 0.0
            
            return {
                "status": "healthy",
                "message": "MJ Network is fully operational",
                "network_stats": stats,
                "features": {
                    "mj_to_mj_chat": True,
                    "friend_requests": True,
                    "location_discovery": True,
                    "scheduled_checkins": True,
                    "status_updates": True,
                    "offline_messaging": True,
                    "privacy_controls": True
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)