# test_mj_memory_live.py - Test MJ's memory system with real data
import asyncio
import asyncpg
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_mj_memory_system():
    """Test MJ's memory system with the working database"""
    
    print("🧠 TESTING MJ'S LIVE MEMORY SYSTEM")
    print("=" * 60)
    
    # Connect with working connection string
    DATABASE_URL = "postgresql://postgres:Teamawaken%402025@db.ahftijzjctexijhfpphk.supabase.co:5432/postgres"
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Connected to MJ's memory database!")
        
        # Test 1: Show existing memories
        print("\n1️⃣ EXISTING MEMORIES IN MJ'S BRAIN:")
        print("-" * 40)
        
        memories = await conn.fetch("""
            SELECT id, fact, category, confidence, importance, created_at
            FROM memories 
            ORDER BY created_at DESC
        """)
        
        if memories:
            for memory in memories:
                print(f"🧠 Memory {memory['id']}: {memory['fact']}")
                print(f"   📂 Category: {memory['category']} | Confidence: {memory['confidence']}")
                print(f"   ⭐ Importance: {memory['importance']} | Added: {memory['created_at'].strftime('%Y-%m-%d %H:%M')}")
                print()
        else:
            print("   (No memories found)")
        
        # Test 2: Show existing conversations
        print("\n2️⃣ CONVERSATION HISTORY:")
        print("-" * 40)
        
        conversations = await conn.fetch("""
            SELECT id, role, content, personality_mode, created_at
            FROM conversations 
            ORDER BY created_at ASC
        """)
        
        for conv in conversations:
            role_emoji = "👤" if conv['role'] == 'user' else "🤖"
            print(f"{role_emoji} {conv['role'].title()}: {conv['content']}")
            if conv['personality_mode']:
                print(f"   🎭 Mode: {conv['personality_mode']}")
            print(f"   ⏰ {conv['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
            print()
        
        # Test 3: Add a new memory
        print("\n3️⃣ ADDING NEW MEMORY:")
        print("-" * 40)
        
        new_memory = await conn.fetchrow("""
            INSERT INTO memories (user_id, fact, context, memory_type, category, confidence, importance)
            VALUES (1, 
                'User is testing MJ memory system and is excited about AI', 
                'During MJ Network setup and testing phase',
                'experience',
                'emotions',
                0.95,
                0.8
            )
            RETURNING id, fact, confidence
        """)
        
        print(f"✅ Added new memory:")
        print(f"   ID: {new_memory['id']}")
        print(f"   Fact: {new_memory['fact']}")
        print(f"   Confidence: {new_memory['confidence']}")
        
        # Test 4: Add a new conversation
        print("\n4️⃣ ADDING NEW CONVERSATION:")
        print("-" * 40)
        
        new_conversation = await conn.fetchrow("""
            INSERT INTO conversations (user_id, role, content, personality_mode)
            VALUES (1, 'user', 'Hey MJ! The memory system is working perfectly!', 'mj')
            RETURNING id, content
        """)
        
        print(f"✅ Added new conversation:")
        print(f"   ID: {new_conversation['id']}")
        print(f"   Content: {new_conversation['content']}")
        
        # Test 5: Memory search simulation
        print("\n5️⃣ MEMORY SEARCH SIMULATION:")
        print("-" * 40)
        
        # Simple keyword search (without embeddings for now)
        search_queries = [
            "Tell me about work",
            "What makes me excited?", 
            "How am I feeling?",
            "What do I do for fun?"
        ]
        
        for query in search_queries:
            print(f"🔍 Query: '{query}'")
            
            # Simple keyword matching (real system would use vector embeddings)
            query_words = query.lower().replace('?', '').split()
            search_pattern = '%' + '%'.join(query_words) + '%'
            
            relevant_memories = await conn.fetch("""
                SELECT fact, confidence, category
                FROM memories 
                WHERE LOWER(fact) LIKE $1 
                   OR LOWER(category) LIKE $1
                ORDER BY confidence DESC
                LIMIT 3
            """, search_pattern)
            
            if relevant_memories:
                print(f"   💭 Found {len(relevant_memories)} relevant memories:")
                for mem in relevant_memories:
                    print(f"      • {mem['fact']} ({mem['confidence']:.2f})")
            else:
                print(f"   📭 No relevant memories found")
            print()
        
        # Test 6: Memory analytics
        print("\n6️⃣ MEMORY ANALYTICS:")
        print("-" * 40)
        
        analytics = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_memories,
                AVG(confidence) as avg_confidence,
                AVG(importance) as avg_importance,
                COUNT(DISTINCT category) as unique_categories,
                MAX(created_at) as latest_memory
            FROM memories
            WHERE user_id = 1
        """)
        
        print(f"📊 MJ's Memory Stats:")
        print(f"   🧠 Total memories: {analytics['total_memories']}")
        print(f"   🎯 Average confidence: {analytics['avg_confidence']:.2f}")
        print(f"   ⭐ Average importance: {analytics['avg_importance']:.2f}")
        print(f"   📂 Unique categories: {analytics['unique_categories']}")
        print(f"   ⏰ Latest memory: {analytics['latest_memory'].strftime('%Y-%m-%d %H:%M')}")
        
        # Test 7: Show memory categories
        print("\n7️⃣ MEMORY CATEGORIES:")
        print("-" * 40)
        
        categories = await conn.fetch("""
            SELECT category, COUNT(*) as count, AVG(confidence) as avg_confidence
            FROM memories 
            WHERE user_id = 1
            GROUP BY category
            ORDER BY count DESC
        """)
        
        for cat in categories:
            print(f"📂 {cat['category']}: {cat['count']} memories (avg confidence: {cat['avg_confidence']:.2f})")
        
        await conn.close()
        
        print(f"\n🎉 MJ MEMORY SYSTEM IS FULLY OPERATIONAL!")
        print("🚀 Ready for integration with chat interface!")
        
        return True
        
    except Exception as e:
        print(f"❌ Memory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_mj_memory_system())