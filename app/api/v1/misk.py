import structlog
from fastapi import APIRouter

from core.settings import settings

logger = structlog.get_logger()
router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.info("health_check", status="ok", version=settings.version)
    return {"status": "ok", "version": settings.version}
