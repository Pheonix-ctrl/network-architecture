from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Text, ForeignKey, Boolean, ARRAY, Numeric, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector  # from `pgvector`
from ...config.database import Base

class Memory(Base):
    __tablename__ = "memories"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    # Keep column for data tracking but remove ForeignKey constraint reference
    source_conversation_id = Column(BigInteger, nullable=True)

    # Content
    fact = Column(Text, nullable=False)
    context = Column(Text, nullable=True)
    memory_type = Column(String, nullable=True)
    category = Column(String, nullable=True)

    # Metadata
    confidence = Column(Numeric, nullable=True)
    importance = Column(Numeric, nullable=True)
    tags = Column(ARRAY(Text), nullable=True)

    # Embedding (pgvector); set your real dimension (e.g., 1536)
    embedding = Column(Vector(1536), nullable=True)

    # Usage / extra metadata (avoid attribute name 'metadata')
    access_count = Column(Integer, nullable=True)
    memory_metadata = Column('metadata', JSONB, nullable=True)

    # Validation
    is_validated = Column(Boolean, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Only keep the user relationship - remove conversation relationship entirely
    user = relationship("User", back_populates="memories")