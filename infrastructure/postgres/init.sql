--infrastructure/postgres/init.sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Create custom types
CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system');
CREATE TYPE personality_mode AS ENUM ('mj', 'kalki', 'jupiter', 'educational', 'healthcare');
CREATE TYPE share_level AS ENUM ('basic', 'moderate', 'full');

-- Indexes for performance
-- (Tables are created by SQLAlchemy, but we can add extra indexes here)

-- Full text search indexes
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_memories_fact_fts 
--     ON memories USING gin(to_tsvector('english', fact));

-- GIN indexes for arrays
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_memories_tags 
--     ON memories USING gin(relevance_tags);

-- Embedding similarity indexes (when using pgvector)
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_memories_embedding_cosine 
--     ON memories USING ivfflat (embedding vector_cosine_ops);
