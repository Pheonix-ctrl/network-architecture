# src/main.py - UPDATED with MJ Network Integration
import sys
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncpg
import bcrypt
import jwt
from datetime import datetime, timedelta
import json

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

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

# JWT settings
SECRET_KEY = "mj_network_secret_key_change_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mj_user:mj_password@localhost:5432/mj_network")

# Global database pool
db_pool = None

async def get_db_pool():
    global db_pool
    if not db_pool:
        try:
            db_pool = await asyncpg.create_pool(DATABASE_URL)
            print("✅ Database pool created")
        except Exception as e:
            print(f"❌ Database pool failed: {e}")
    return db_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting MJ Network v4.0.0 - WITH MJ-TO-MJ NETWORK")
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
    
    print("✅ MJ Network ready with full networking capabilities")
    yield
    
    # Shutdown
    if db_pool:
        await db_pool.close()

app = FastAPI(title="MJ Network", version="4.0.0", lifespan=lifespan)

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

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    print(f"🔑 Created token for user {data.get('sub')}")
    return token

async def get_current_user(token = Depends(security)):
    if not token:
        print("❌ No token provided")
        raise HTTPException(status_code=401, detail="No token provided")
    
    try:
        print(f"🔍 Verifying token...")
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        print(f"✅ Token valid for user: {user_id_str}")
        if user_id_str is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        # Convert back to integer
        user_id = int(user_id_str)
        return user_id
    except jwt.ExpiredSignatureError:
        print("❌ Token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        print(f"❌ Invalid token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print(f"❌ Token verification error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

# Include MJ Network API routes
from src.api.v1.mj_network import router as mj_network_router
app.include_router(mj_network_router, prefix="/api/v1/mj-network", tags=["MJ Network"])

# Auth endpoints (existing)
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
                # bcrypt hashed
                password_valid = bcrypt.checkpw(
                    login_request.password.encode('utf-8'),
                    user['password_hash'].encode('utf-8')
                )
            else:
                # Plain text (for development)
                password_valid = login_request.password == user['password_hash']
            
            if not password_valid:
                print(f"❌ Invalid password for: {login_request.email}")
                raise HTTPException(status_code=401, detail="Invalid password")
            
            # Update user status
            await conn.execute(
                "UPDATE users SET is_online = true, last_active = NOW() WHERE id = $1",
                user['id']
            )
            
            # Auto-initialize MJ registry if not exists
            await initialize_user_mj_network(user['id'], user['username'])
            
            # Create token (convert user_id to string for JWT)
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
            
            # Auto-initialize MJ registry
            await initialize_user_mj_network(user_id, register_request.username)
            
            # Create token (convert user_id to string for JWT)
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
    """Get current user info"""
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
            
            # Get MJ network status
            mj_registry = await conn.fetchrow(
                "SELECT status, total_conversations, total_messages_sent, location_enabled FROM mj_registry WHERE user_id = $1",
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
                    "location_enabled": mj_registry['location_enabled'] if mj_registry else False
                } if mj_registry else None
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Get user info error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user info")

async def initialize_user_mj_network(user_id: int, username: str):
    """Auto-initialize MJ registry for new users"""
    
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
                    # Create MJ registry
                    await conn.execute(
                        """INSERT INTO mj_registry (user_id, mj_instance_id, status, capabilities) 
                           VALUES ($1, $2, 'online', $3)""",
                        user_id,
                        user_data['mj_instance_id'],
                        json.dumps({"chat": True, "location": False, "voice": False})
                    )
                    
                    print(f"🌐 MJ registry initialized for user {user_id}")
                    
    except Exception as e:
        print(f"❌ MJ registry initialization failed for user {user_id}: {e}")

# WebSocket for real-time chat (existing functionality)
connected_clients = {}

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await websocket.accept()
    connected_clients[user_id] = websocket
    print(f"✅ User {user_id} connected via WebSocket")
    
    # Update MJ status to online
    await update_mj_status(user_id, "online")
    
    # Deliver any pending MJ messages
    await deliver_pending_mj_messages(user_id)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            
            if not user_message.strip():
                continue
            
            print(f"💬 User {user_id}: {user_message}")
            
            # Process with existing MJ logic (user-to-MJ conversation)
            print("🔄 Processing message with existing MJ logic...")
            response = await process_styled_mj_message(user_message, user_id)
            print(f"✅ MJ response ready: '{response[:100]}...'")
            
            # Send response
            response_data = {
                "type": "message",
                "content": response,
                "timestamp": datetime.now().isoformat()
            }
            print(f"📤 Sending WebSocket response")
            
            await websocket.send_text(json.dumps(response_data))
            print("✅ WebSocket response sent successfully")
            
    except WebSocketDisconnect:
        if user_id in connected_clients:
            del connected_clients[user_id]
        
        # Update MJ status to offline
        await update_mj_status(user_id, "offline")
        print(f"❌ User {user_id} disconnected")
    except Exception as e:
        print(f"❌ WebSocket error for user {user_id}: {e}")
        if user_id in connected_clients:
            del connected_clients[user_id]
        await update_mj_status(user_id, "offline")

async def update_mj_status(user_id: int, status: str):
    """Update MJ online status"""
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
    """Deliver pending MJ-to-MJ messages when user comes online"""
    
    try:
        from src.config.database import AsyncSessionLocal
        from src.services.mj_network.mj_communication import MJCommunicationService
        
        async with AsyncSessionLocal() as db:
            communication_service = MJCommunicationService(db)
            delivered_count = await communication_service.deliver_pending_messages(user_id)
            
            if delivered_count > 0:
                print(f"📨 Delivered {delivered_count} pending MJ messages to user {user_id}")
                
                # Notify user via WebSocket if connected
                if user_id in connected_clients:
                    notification = {
                        "type": "mj_messages_delivered",
                        "count": delivered_count,
                        "message": f"You have {delivered_count} new MJ messages"
                    }
                    
                    await connected_clients[user_id].send_text(json.dumps(notification))
                    
    except Exception as e:
        print(f"❌ Failed to deliver pending messages for user {user_id}: {e}")

# Existing MJ processing functions
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
            # Check if the OpenAI client has get_embeddings method
            if hasattr(app.state.openai_client, 'get_embeddings'):
                embeddings_response = await app.state.openai_client.get_embeddings([mem['fact'] for mem in memories])
            else:
                # Create embeddings using the client directly
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
        
        if mode == 'healthcare' and confidence > 0.40:  # LOWERED from 0.50
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
        
        elif mode == 'educational' and confidence > 0.50:  # LOWERED from 0.60
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
        
        elif mode == 'web_search' and confidence > 0.50:  # LOWERED from 0.60
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
            print(f"💭 Thresholds: healthcare>0.40, educational>0.50, web_search>0.50")
        
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

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "MJ Network v4.0.0 - WITH MJ-TO-MJ NETWORK"}

# NEW: MJ Network Status Endpoint
@app.get("/api/v1/mj-network-status")
async def get_mj_network_status():
    """Get overall MJ network status"""
    pool = await get_db_pool()
    if not pool:
        return {"status": "database_unavailable"}
    
    try:
        async with pool.acquire() as conn:
            # Get network statistics
            stats = {}
            
            # Total registered MJs
            stats['total_mjs'] = await conn.fetchval("SELECT COUNT(*) FROM mj_registry")
            
            # Online MJs
            stats['online_mjs'] = await conn.fetchval("SELECT COUNT(*) FROM mj_registry WHERE status = 'online'")
            
            # Total relationships
            stats['total_relationships'] = await conn.fetchval("SELECT COUNT(*) FROM relationships WHERE status = 'active'")
            
            # Total MJ conversations
            stats['total_mj_conversations'] = await conn.fetchval("SELECT COUNT(*) FROM mj_conversations WHERE status = 'active'")
            
            # Total MJ messages
            stats['total_mj_messages'] = await conn.fetchval("SELECT COUNT(*) FROM mj_messages")
            
            # Users with location enabled
            stats['users_with_location'] = await conn.fetchval("SELECT COUNT(*) FROM user_locations WHERE is_visible_on_map = true")
            
            return {
                "status": "healthy",
                "network_stats": stats,
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)