from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Generic, TypeVar, cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from models.basemodel import Base

ModelType = TypeVar("ModelType", bound=Base)


class AbstractRepository(ABC, Generic[ModelType]):  # noqa: UP046
    @abstractmethod
    async def get_by_id(self, id_: Any) -> ModelType | None:
        raise NotImplementedError

    @abstractmethod
    async def get_all(
        self, limit: int = 100, offset: int = 0
    ) -> Sequence[ModelType]:
        raise NotImplementedError

    @abstractmethod
    async def add(self, entity: ModelType) -> ModelType:
        raise NotImplementedError

    @abstractmethod
    async def update(self, id_: Any, **kwargs: Any) -> ModelType | None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, id_: Any) -> bool:
        """Удалить сущность по ID."""
        raise NotImplementedError


class CRUDRepository(AbstractRepository[ModelType]):
    """
    Универсальный репозиторий, инкапсулирующий базовые CRUD операции.
    """

    def __init__(self, session: AsyncSession, model: type[ModelType]) -> None:
        self._session = session
        self._model = model

    async def get_by_id(self, id_: Any) -> ModelType | None:
        return await self._session.get(self._model, id_)

    async def get_all(
        self, limit: int = 100, offset: int = 0
    ) -> Sequence[ModelType]:
        stmt = select(self._model).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add(self, entity: ModelType) -> ModelType:
        self._session.add(entity)
        return entity

    async def update(self, id_: Any, **kwargs: Any) -> ModelType | None:
        filter_condition = self._get_pk_filter(id_)

        stmt = (
            update(self._model)
            .where(*filter_condition)
            .values(**kwargs)
            .returning(self._model)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, id_: Any) -> bool:
        filter_condition = self._get_pk_filter(id_)

        stmt = delete(self._model).where(*filter_condition)
        result = cast("CursorResult", await self._session.execute(stmt))
        return (result.rowcount or 0) > 0

    def _get_pk_filter(self, id_: Any) -> list[Any]:
        """хелпер сборки WHERE по одиночным и составным PK."""
        mapper = self._model.__mapper__
        pk_columns = mapper.primary_key

        if len(pk_columns) > 1 and isinstance(id_, tuple):
            return [
                col == val for col, val in zip(pk_columns, id_, strict=False)
            ]
        return [pk_columns[0] == id_]
