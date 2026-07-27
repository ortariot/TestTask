from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DatabaseSessionManager:
    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def init(self, db_dsl: str, pool_pre_ping: bool = True) -> None:

        if self._engine is not None:
            raise RuntimeError(
                "DatabaseSessionManager is allready initialized."
            )

        self._engine = create_async_engine(db_dsl, pool_pre_ping=pool_pre_ping)
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False,
        )

    async def close(self) -> None:

        if self._engine is None:
            raise RuntimeError("DatabaseSessionManager is not initialized.")

        await self._engine.dispose()
        self._engine = None
        self._session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError("DatabaseSessionManager is not initialized.")
        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise


db_manager = DatabaseSessionManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with db_manager.session() as session:
        yield session
