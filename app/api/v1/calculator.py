import structlog
from api.dependencies.tasks import validate_task_finished
from core.exceptions import InfrastructureeOperationalException
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from schemas.calcreq import CalculationRequest
from schemas.coordinates import CalculateResponsePagination
from services.calculation import (
    OrbitCalculationService,
    get_orbit_calculations_service,
)
from services.coordinates import CoordinateService

logger = structlog.get_logger()
router = APIRouter()


@router.post("/coordinates_calculate")
async def calculate(
    request: CalculationRequest,
    service: OrbitCalculationService = Depends(get_orbit_calculations_service),
) -> JSONResponse:
    """Calculation of satellite trajectory coordinates using TLE"""

    res = await service.calculate_satellite_position(request)

    if res:
        return JSONResponse(content=res)

    return JSONResponse(
        content={
            "mes": "the task has been placed in the queue.",
            "task_id": "1",
        },
        status_code=status.HTTP_202_ACCEPTED,
    )


@router.get(
    "/tasks/{task_id}/coordinates",
)
async def get_coordinates_page(
    page: int = Query(default=1, ge=1, description="page number"),
    size: int = Query(default=100, ge=1, le=1000, description="page size"),
    task_id: int = Depends(validate_task_finished),
    coordinate_service: CoordinateService = Depends(),
) -> CalculateResponsePagination:
    """Get coordinate by task_id"""
    try:
        res, total = await coordinate_service.get_coordinates_paginated(
            task_id, page, size
        )

        return CalculateResponsePagination(
            points=res, page=page, size=size, total=total
        )
    except InfrastructureeOperationalException as error:
        logger.exception(
            "ClickHouse infrastructure failure for task %s wit error %s",
            task_id,
            error,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database not aviable",
        ) from None


@router.get(
    "/tasks/{task_id}/coordinates/download",
)
async def download_coordinates_file(
    offset_row: int = Query(default=0, ge=0, description="offset from start"),
    limit_row: int = Query(
        default=1000000, ge=1, le=1000000, description="max row count"
    ),
    task_id: int = Depends(validate_task_finished),
    coordinate_service: CoordinateService = Depends(),
) -> StreamingResponse:
    """Get csv-stream with coordinate by task_id"""
    try:
        file_stream = await coordinate_service.get_coordinates_file_stream(
            task_id=task_id, offset_row=offset_row, limit_row=limit_row
        )
    except InfrastructureeOperationalException as error:
        logger.exception(
            "ClickHouse infrastructure failure for task %s wit error %s",
            task_id,
            error,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database not aviable",
        ) from None

    filename = (
        f"task_{task_id}_rows_{offset_row}_to_{offset_row + limit_row}.csv"
    )
    headers = {"Content-Disposition": f"attachment; filename={filename}"}

    return StreamingResponse(
        file_stream, media_type="text/csv", headers=headers
    )
