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

# Simple models
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
SECRET_KEY = "mj_network_secret_key_2025"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Database connection
DATABASE_URL = "postgresql://postgres:Teamawaken%402025@db.ahftijzjctexijhfpphk.supabase.co:5432/postgres"

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
    print("🚀 Starting MJ Network v3.0.0 - CLEAN LOGIC")
    await get_db_pool()
    
    # Try to load AI services
    try:
        from src.services.ai.openai_client import OpenAIClient
        app.state.openai_client = OpenAIClient()
        print("✅ OpenAI client loaded")
    except Exception as e:
        print(f"❌ OpenAI failed: {e}")
        app.state.openai_client = None
    
    print("✅ MJ Network ready for clean routing")
    yield
    
    # Shutdown
    if db_pool:
        await db_pool.close()

app = FastAPI(title="MJ Network", version="3.0.0", lifespan=lifespan)

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

# Auth endpoints
@app.post("/api/v1/auth/login")
async def login(login_request: LoginRequest):
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
            
            # Create user
            user_id = await conn.fetchval(
                """INSERT INTO users (username, email, password_hash, mj_instance_id) 
                   VALUES ($1, $2, $3, $4) RETURNING id""",
                register_request.username,
                register_request.email,
                hashed_password,
                f"MJ-{register_request.username.upper()[:8]}"
            )
            
            # Create token (convert user_id to string for JWT)
            access_token = create_access_token(data={"sub": str(user_id)})
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": user_id,
                    "username": register_request.username,
                    "email": register_request.email
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
                "SELECT id, username, email FROM users WHERE id = $1",
                current_user
            )
            
            if not user:
                print(f"❌ User not found in database: {current_user}")
                raise HTTPException(status_code=404, detail="User not found")
            
            print(f"✅ User info retrieved: {user['username']}")
            return {
                "id": user['id'],
                "username": user['username'],
                "email": user['email']
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Get user info error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user info")

# WebSocket for real-time chat
connected_clients = {}

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await websocket.accept()
    connected_clients[user_id] = websocket
    print(f"✅ User {user_id} connected via WebSocket")
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            
            if not user_message.strip():
                continue
            
            print(f"💬 User {user_id}: {user_message}")
            
            # Process with CLEAN MJ routing
            print("🔄 Processing message with clean logic...")
            response = await process_clean_mj_message(user_message, user_id)
            print(f"✅ MJ response ready: '{response[:100]}...'")
            
            # Send response
            response_data = {
                "type": "message",
                "content": response,
                "timestamp": datetime.now().isoformat()
            }
            print(f"📤 Sending WebSocket response: {response_data}")
            
            await websocket.send_text(json.dumps(response_data))
            print("✅ WebSocket response sent successfully")
            
    except WebSocketDisconnect:
        if user_id in connected_clients:
            del connected_clients[user_id]
        print(f"❌ User {user_id} disconnected")
    except Exception as e:
        print(f"❌ WebSocket error for user {user_id}: {e}")
        if user_id in connected_clients:
            del connected_clients[user_id]

async def process_clean_mj_message(user_message: str, user_id: int) -> str:
    """CLEAN LOGIC: Single classification → Clean routing → Modules handle everything"""
    
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
        
        # STEP 3: Clean routing - LOWERED thresholds, modules handle everything
        
        if mode == 'healthcare' and confidence > 0.50:  # LOWERED from 0.70
            print("🏥 ROUTING TO MEDICO...")
            try:
                from src.services.ai.medico import handle_medical_query
                response = await handle_medical_query(user_message, context, app.state.openai_client)
                print(f"🏥 MEDICO RESPONSE: {response[:100]}...")
                await save_conversation(user_id, user_message, response)
                return response
            except Exception as e:
                print(f"❌ MEDICO ERROR: {e}")
        
        elif mode == 'educational' and confidence > 0.60:  # LOWERED from 0.75
            print("📚 ROUTING TO PRISM...")
            try:
                from src.services.ai.prism import handle_educational_question
                response = await handle_educational_question(user_message, context, app.state.openai_client)
                print(f"📚 PRISM RESPONSE: {response[:100]}...")
                await save_conversation(user_id, user_message, response)
                return response
            except Exception as e:
                print(f"❌ PRISM ERROR: {e}")
        
        elif mode == 'web_search' and confidence > 0.60:  # LOWERED from 0.70
            print("🌐 ROUTING TO PERPLEXITY...")
            try:
                from src.services.external.perplexity import handle_web_question
                response = await handle_web_question(user_message, context, app.state.openai_client)
                print(f"🌐 PERPLEXITY RESPONSE: {response[:100]}...")
                await save_conversation(user_id, user_message, response)
                return response
            except Exception as e:
                print(f"❌ PERPLEXITY ERROR: {e}")
        
        else:
            print(f"💭 No module triggered - Mode: {mode}, Confidence: {confidence}")
            print(f"💭 Thresholds: healthcare>0.50, educational>0.60, web_search>0.60")
        
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
    medical_keywords = ['pain', 'hurt', 'sick', 'doctor', 'medicine', 'health', 'injury', 'fever', 'headache', 'strain', 'bleeding']
    if any(keyword in message_lower for keyword in medical_keywords):
        return {'mode': 'healthcare', 'confidence': 0.75, 'category': 'medical'}
    
    # Educational keywords
    educational_keywords = ['explain', 'teach', 'how does', 'what is', 'how to', 'circuit', 'calculate', 'formula', 'definition', 'understand']
    if any(keyword in message_lower for keyword in educational_keywords):
        return {'mode': 'educational', 'confidence': 0.85, 'category': 'educational'}
    
    # Web search keywords
    search_keywords = ['current', 'latest', 'news', 'today', 'recent', 'weather', 'stock price', 'search']
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

async def save_conversation(user_id: int, user_message: str, mj_response: str):
    """Save conversation to database"""
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
            
    except Exception as e:
        print(f"❌ Save conversation error: {e}")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "MJ Network v3.0.0 - CLEAN"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)