"""
Base repository pattern for Opora.
"""

from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from db.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations."""
    
    def __init__(self, session: AsyncSession, model: type[ModelType]):
        self.session = session
        self.model = model
    
    async def get_by_id(self, id: int) -> ModelType | None:
        """Get entity by ID."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def create(self, **kwargs) -> ModelType:
        """Create new entity."""
        entity = self.model(**kwargs)
        self.session.add(entity)
        await self.session.flush()
        return entity
    
    async def update(self, entity: ModelType, **kwargs) -> ModelType:
        """Update entity fields."""
        for key, value in kwargs.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        await self.session.flush()
        return entity
    
    async def delete(self, entity: ModelType) -> None:
        """Delete entity."""
        await self.session.delete(entity)
        await self.session.flush()
