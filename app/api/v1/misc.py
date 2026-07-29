import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.settings import settings

logger = structlog.get_logger()
router = APIRouter()


@router.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint."""
    logger.info("health_check", status="ok", version=settings.version)
    return JSONResponse(content={"status": "ok", "version": settings.version})
