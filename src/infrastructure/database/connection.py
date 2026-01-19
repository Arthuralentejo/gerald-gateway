"""Database connection and session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import settings


class DatabaseSessionManager:
    """
    Manages database connections and sessions.

    Uses SQLAlchemy async engine for non-blocking database operations.
    """

    def __init__(self):
        self._engine = None
        self._sessionmaker = None

    def init(self, database_url: str | None = None):
        """
        Initialize the database engine and session factory.

        Args:
            database_url: Optional override for the database URL
        """
        url = database_url or settings.database_url

        # Convert postgres:// to postgresql+asyncpg://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        self._engine = create_async_engine(
            url,
            echo=settings.debug,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
        )

        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    async def close(self):
        """Close the database engine."""
        if self._engine:
            await self._engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Provide a transactional scope around operations.

        Yields:
            An async database session
        """
        if self._sessionmaker is None:
            raise RuntimeError("Database not initialized. Call init() first.")

        session = self._sessionmaker()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


db_manager = DatabaseSessionManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Yields:
        An async database session
    """
    async with db_manager.session() as session:
        yield session
