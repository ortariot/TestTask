import structlog
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from schemas.coordinates import CalculateResponse
from schemas.tle import CalculateRequest
from services.calculation import (
    OrbitCalculationService,
    get_orbit_calculations_service,
)

logger = structlog.get_logger()
router = APIRouter()


@router.post("/calculate/sync")
async def calculate_sync(
    request: CalculateRequest,
    service: OrbitCalculationService = Depends(get_orbit_calculations_service),
) -> CalculateResponse:
    """расчёт координат (до ``settings.sync_max_points`` точек)."""

    print(request.model_dump_json())
    res = await service.calculate_satellite_position(request)

    if res:
        return JSONResponse(content=res)

    status_code = status.HTTP_202_ACCEPTED
    return JSONResponse(
        content={
            "mes": "the task has been placed in the queue.",
            "task_id": "1",
        },
        status_code=status_code,
    )
