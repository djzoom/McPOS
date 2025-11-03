"""
Database Service

SQLAlchemy setup and initialization for SQLite (local) → Postgres (future).
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event
from sqlalchemy.engine import Engine
from models.base import Base
import os

# Database URL (SQLite for MVP, Postgres for production)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./data/db.sqlite3"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL logging
    future=True
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# SQLite-specific: Enable foreign keys
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign keys for SQLite"""
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async def init_db():
    """Initialize database: create tables"""
    # Import all models to ensure tables are registered
    from models.channel import Channel
    from models.track import Track
    from models.image import Image
    
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    # Create default channel if it doesn't exist
    async with AsyncSessionLocal() as session:
        from services.channel_service import ChannelService
        channel_service = ChannelService(session)
        await channel_service.ensure_default_channel()
        await session.commit()
    
    print("✅ Database initialized")


async def get_db():
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

