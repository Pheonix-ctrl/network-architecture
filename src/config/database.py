# src/config/database.py

# FORCE LOAD ENVIRONMENT VARIABLES FIRST
from dotenv import load_dotenv
import os
from pathlib import Path

# Try multiple ways to load the .env file
env_loaded = False

# Method 1: Load from current directory
if load_dotenv():
    env_loaded = True
    print("✓ Environment loaded from current directory")

# Method 2: Load with explicit path if first method failed
if not env_loaded:
    env_path = Path(__file__).parent.parent.parent / ".env"
    if load_dotenv(env_path):
        env_loaded = True
        print(f"✓ Environment loaded from: {env_path}")

# Method 3: Load with absolute path if still failed
if not env_loaded:
    abs_env_path = Path("C:/Users/abhir/Desktop/MJ/Complete-Architecture/.env")
    if load_dotenv(abs_env_path):
        env_loaded = True
        print(f"✓ Environment loaded from absolute path: {abs_env_path}")

if not env_loaded:
    print("⚠️ Warning: Could not load .env file")
else:
    print(f"✓ SECRET_KEY loaded: {'Yes' if os.environ.get('SECRET_KEY') else 'No'}")

# NOW CONTINUE WITH NORMAL IMPORTS
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData
from typing import AsyncGenerator
from .settings import Settings

settings = Settings()

# Database Engine Configuration
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=settings.is_development,
)

# Session Factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base Model
class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s"
        }
    )

# Dependency for getting DB session
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()