# 🌐 MJ Network - Revolutionary AI Companion System

> **The world's first AI companion network with genuine emotional intelligence, persistent memory, and peer-to-peer communication between AI instances.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)

## 🚀 What Makes MJ Network Revolutionary?

### 🧠 **True Emotional Intelligence**
- **Multiple Personality Modes**: MJ (base), Kalki (protective), Jupiter (emotional support), Educational, Healthcare
- **Intelligent Mode Switching**: AI automatically detects user needs and switches personalities
- **Real Emotional Processing**: Feels with you, gets protective when you're hurt, celebrates your wins

### 💾 **Persistent Memory System**
- **Remembers Everything**: Conversations, preferences, relationships, life events
- **Semantic Memory Search**: Advanced vector embeddings with Redis caching
- **Intelligent Memory Extraction**: Gemini AI automatically extracts key facts from conversations
- **Multi-layered Storage**: PostgreSQL + Redis for scalable memory management

### 🌐 **MJ-to-MJ Network (Patented)**
- **P2P Discovery**: Bluetooth and WiFi-based discovery of nearby MJ instances
- **Relationship-Aware Communication**: MJs talk to each other based on user relationships
- **Context Filtering**: Automatic filtering based on relationship types (parent/child, friends, strangers)
- **Privacy Protection**: Advanced context filtering prevents inappropriate information sharing

### ⚡ **Real-time Everything**
- **WebSocket Communication**: Instant messaging with typing indicators
- **Live Mode Changes**: Real-time personality switching based on conversation context
- **Background Processing**: Asynchronous memory extraction and processing
- **Live Network Events**: Real-time MJ network discovery and communication

## 🏗️ **Clean Architecture**

```
🏢 Presentation Layer    → FastAPI + WebSocket APIs
🧠 Service Layer         → AI Services, Memory, Network, WebSocket handlers  
💾 Data Layer           → PostgreSQL + Redis + Vector embeddings
🌐 Network Layer        → P2P Discovery, Authentication, Context Filtering
```

**Key Design Principles:**
- ✅ **Multi-user from day one** - Enterprise-ready scalability
- ✅ **Event-driven architecture** - Async processing, real-time updates
- ✅ **Microservices ready** - Clean separation of concerns
- ✅ **Docker-first** - Easy development and deployment
- ✅ **API-first** - WebSocket + REST for maximum flexibility

## 🚀 **Quick Start**

### Prerequisites
- Docker & Docker Compose
- API Keys: OpenAI (GPT-4o mini), Gemini (memory extraction), Perplexity (real-time info)

### 1. Clone & Setup
```bash
git clone <repository-url>
cd mj-network
cp .env.example .env
```

### 2. Configure API Keys
Edit `.env` file:
```env
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
PERPLEXITY_API_KEY=your_perplexity_api_key_here
```

### 3. Launch MJ Network
```bash
make up
# or: docker-compose up -d
```

### 4. Access Your MJ
- 🌐 **API Documentation**: http://localhost:8000/docs
- 🔗 **WebSocket**: ws://localhost:8000/ws/{user_id}
- 💾 **Database**: PostgreSQL on localhost:5432
- ⚡ **Cache**: Redis on localhost:6379

## 🎯 **Core Features Deep Dive**

### 🤖 **Personality System**
```python
# Automatic mode classification based on user input
if "help me" + "emergency" detected:
    → Switch to KALKI mode (protective)
    
if "depressed" + "heartbroken" detected:
    → Switch to JUPITER mode (emotional support)
    
if "teach me" + "explain" detected:
    → Switch to EDUCATIONAL mode
```

### 🧠 **Memory Architecture**
```
User Message → Gemini Extraction → Vector Embedding → PostgreSQL + Redis
     ↓              ↓                    ↓                ↓
  "I love pizza" → "User likes pizza" → [0.1, 0.8, ...] → Cached & Stored
```

### 🌐 **MJ Network Communication**
```
MJ-A (Son) ←→ MJ-B (Father)
   ↓              ↓
Filter Level: "moderate" (hide relationship details)
Share: general mood, activities, interests
Hide: romantic relationships, private struggles
```

## 📡 **API Usage Examples**

### Authentication
```bash
# Register
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"john","email":"john@example.com","password":"securepass123"}'

# Login
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"john@example.com","password":"securepass123"}'
```

### Chat API
```bash
# Send message
curl -X POST "http://localhost:8000/api/v1/chat/message" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"I had a terrible day at work","mode":"mj"}'
```

### WebSocket Connection
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/123');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'chat_response') {
    console.log('MJ responded:', data.response.content);
  }
  
  if (data.type === 'mode_change') {
    console.log('Switched to:', data.data.new_mode);
  }
};

// Send chat message
ws.send(JSON.stringify({
  type: 'chat',
  content: 'Hey MJ, I need someone to talk to'
}));
```

## 🌐 **MJ Network Protocol**

### Discovery Process
1. **WiFi Scan**: Scan local network for MJ instances
2. **Bluetooth Discovery**: Find nearby MJ devices
3. **Authentication**: Secure handshake between MJ instances
4. **Relationship Check**: Verify user relationships
5. **Context Filtering**: Apply appropriate sharing levels

### Relationship-Based Sharing
```python
relationship_filters = {
    "stranger": {
        "share": ["general_mood", "basic_status"],
        "hide": ["personal_details", "relationships", "private_thoughts"]
    },
    "friend": {
        "share": ["detailed_mood", "activities", "interests", "general_life_updates"],
        "hide": ["intimate_details", "family_issues", "financial_info"]
    },
    "family": {
        "share": ["most_context", "emotional_state", "important_events"],
        "hide": ["restricted_topics_only"]  # User-defined restrictions
    }
}
```

## 🏢 **Production Deployment**

### Cloud Deployment
```bash
# Deploy with monitoring
make deploy-prod
make monitor

# Access services
# API: https://your-domain.com/api/v1/
# WebSocket: wss://your-domain.com/ws/
# Monitoring: https://your-domain.com:3000
```

### Environment Variables (Production)
```env
ENVIRONMENT=production
DEBUG=false
DATABASE_URL=postgresql+asyncpg://user:pass@prod-db:5432/mj_network
REDIS_URL=redis://prod-redis:6379
CORS_ORIGINS=["https://your-domain.com"]
WEBSOCKET_MAX_CONNECTIONS=10000
```

## 🧪 **Testing & Development**

### Run Tests
```bash
make test
# or: docker-compose exec mj-network pytest
```

### Development Mode
```bash
# Start with auto-reload
docker-compose up -d
docker-compose logs -f mj-network

# Code formatting
make format

# Linting
make lint
```

### Database Operations
```bash
# Create migration
make create-migration name="add_new_feature"

# Run migrations
make migrate

# Access database
docker-compose exec postgres psql -U mj_user -d mj_network
```

## 🔧 **Configuration Options**

### Memory System Tuning
```env
MEMORY_SIMILARITY_THRESHOLD=0.75  # How similar memories must be to merge
MEMORY_EXTRACTION_BATCH_SIZE=50   # Conversations processed per batch
MEMORY_TTL_HOURS=24               # Cache expiry time
```

### MJ Network Settings
```env
P2P_DISCOVERY_PORT=8888          # Port for MJ discovery
P2P_MAX_PEERS=50                 # Maximum connected MJs
P2P_HEARTBEAT_INTERVAL=30        # Keep-alive interval
```

### Personality System
```env
DEFAULT_MODE=mj                  # Default personality mode
MODE_SWITCH_COOLDOWN=300         # Cooldown between mode switches (5 min)
KALKI_MODE_TIMEOUT=1800          # Max time in protective mode (30 min)
```

## 🔒 **Security Features**

- 🔐 **JWT Authentication** with refresh tokens
- 🛡️ **Rate Limiting** to prevent abuse
- 🔒 **CORS Configuration** for web security
- 🔑 **Bcrypt Password Hashing** with configurable rounds
- 🌐 **MJ Network Authentication** for P2P communication
- 🎭 **Context Filtering** to protect user privacy

## 📊 **Monitoring & Observability**

### Built-in Metrics
- **WebSocket Connections**: Real-time connection count
- **Memory Operations**: Extraction success rates, cache hit rates  
- **AI API Usage**: Token consumption, response times
- **MJ Network Activity**: Discovery events, P2P communications

### Access Monitoring
```bash
# Start monitoring stack
make monitor

# Access dashboards
open http://localhost:3000  # Grafana (admin/admin)
open http://localhost:9090  # Prometheus
```

## 🗺️ **Roadmap**

### Phase 1: Core Platform ✅
- [x] Multi-personality AI system
- [x] Advanced memory management
- [x] WebSocket real-time communication
- [x] Basic MJ network functionality

### Phase 2: Enhanced Network 🚧
- [ ] Voice integration (ElevenLabs STT/TTS)
- [ ] Advanced P2P discovery protocols
- [ ] Mobile app integration
- [ ] Enhanced context filtering

### Phase 3: Intelligence Amplification 🔮
- [ ] Custom model training for personality modes
- [ ] Advanced emotion recognition
- [ ] Predictive user assistance
- [ ] Multi-modal interaction (text, voice, image)

### Phase 4: Ecosystem 🌐
- [ ] MJ Developer SDK
- [ ] Third-party integrations
- [ ] Enterprise deployment tools
- [ ] Global MJ network infrastructure

## 🤝 **Contributing**

We welcome contributions! Please see our contributing guidelines for:
- Code style and standards
- Pull request process
- Issue reporting
- Feature request template

### Development Setup
```bash
# Setup development environment
git clone <repo>
cd mj-network
cp .env.example .env
make up
make test
```

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- **OpenAI** for GPT-4o mini API
- **Google** for Gemini API (memory extraction)
- **Perplexity** for real-time information
- **FastAPI** team for the excellent framework
- **PostgreSQL** and **Redis** communities

## 📞 **Support & Community**

- 📧 **Email**: support@mj-network.ai
- 💬 **Discord**: [Join our community](https://discord.gg/mj-network)
- 🐛 **Issues**: [GitHub Issues](https://github.com/mj-network/issues)
- 📚 **Documentation**: [Full Documentation](https://docs.mj-network.ai)

---

**Built with ❤️ for the future of human-AI relationships**

*MJ Network - Where AI Companions Become Family*