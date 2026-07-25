from datetime import timedelta

import structlog
from fastapi import APIRouter, HTTPException

from schemas.coordinates import CalculateResponse
from schemas.tle import CalculateRequest

logger = structlog.get_logger()
router = APIRouter()


@router.post("/calculate/sync", response_model=CalculateResponse)
async def calculate_sync(
    request: CalculateRequest,
    settings: SettingsDep,  # noqa: F821
) -> CalculateResponse:
    """расчёт координат (до ``settings.sync_max_points`` точек)."""
    points_count = estimate_points_count(  # noqa: F821
        request.start, request.end, timedelta(seconds=request.step_seconds)
    )
    if points_count > settings.sync_max_points:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Расчёт требует {points_count} точек, лимит синхронной ручки—"
                f"{settings.sync_max_points}. Используйте /calculate/async."
            ),
        )

    satellite = _build_sat(request)  # noqa: F821
    batch = await run_in_threadpool(  # noqa: F821
        calculate_coordinates,  # noqa: F821
        satellite,
        request.start,
        request.end,
        timedelta(seconds=request.step_seconds),
    )

    points = _batch_to_points(batch)  # noqa: F821
    return CalculateSyncResponse(points=points, total=len(points))  # noqa: F821
