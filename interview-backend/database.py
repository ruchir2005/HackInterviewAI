"""
Database Configuration and Connection Management
PostgreSQL async connection using SQLAlchemy 2.0 with asyncpg
"""

import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()

# Database URL from environment
# Format: postgresql+asyncpg://user:password@host:port/database
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:15432/interviews"
)

# For sync operations (like Alembic migrations)
SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DEBUG", "false").lower() == "true",
    poolclass=NullPool,  # Disable connection pooling for serverless compatibility
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection for database sessions.
    Usage in FastAPI:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        # Import models to register them with Base
        from models import (
            User, InterviewSession, Question, SoftSkillsMetric, TokenUsage,
            AssessmentCategory, AssessmentQuestion, AssessmentQuestionOption,
            AssessmentAttempt, AssessmentAttemptAnswer,
            Institution, InstitutionMembership, InstitutionInterview,
            InstitutionInterviewRound, InstitutionInterviewQuestion,
            InstitutionInterviewAttempt, InstitutionInterviewAnswer,
        )
        
        logger.info("Creating database tables...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")


async def close_db():
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connections closed")
