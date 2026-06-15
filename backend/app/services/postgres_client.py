from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.core.config import settings
from app.services.database import Base
import logging

logger = logging.getLogger(__name__)


class PostgresClient:
    def __init__(self):
        self.engine = None
        self.async_session_maker = None
        self.connected = False
    
    async def connect(self):
        """Initialize PostgreSQL connection"""
        try:
            self.engine = create_async_engine(
                settings.POSTGRES_URI.replace("postgresql://", "postgresql+asyncpg://"),
                echo=settings.DEBUG,
                pool_size=20,
                max_overflow=40,
                pool_pre_ping=True
            )
            self.async_session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False
            )
            self.connected = True
            logger.info(f"Connected to PostgreSQL at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    async def close(self):
        """Close PostgreSQL connections"""
        if self.engine:
            await self.engine.dispose()
            self.connected = False
            logger.info("PostgreSQL connections closed")
    
    async def get_db(self) -> AsyncSession:
        """Get database session"""
        if not self.connected:
            raise RuntimeError("PostgreSQL not connected")
        
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def get_pool(self):
        """Get connection pool for health check"""
        if not self.connected or not self.engine:
            raise RuntimeError("PostgreSQL not connected")
        
        # Test connection by executing a simple query
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    
    async def init_db(self):
        """Initialize database tables"""
        if not self.connected:
            raise RuntimeError("PostgreSQL not connected")
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")


# Global PostgreSQL client instance
postgres_client = PostgresClient()