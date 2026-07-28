from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from api.v1.calculator import router as calc_router
from api.v1.misk import router as misk_router
from core.clickhouse import ch_container, setup_clickhouse
from core.exceptions import TaskNotFinishedException
from core.logger import StructlogMiddleware
from core.logger_config import configure_logging
from core.settings import settings
from database import db_manager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import URL

configure_logging(is_dev=settings.is_dev)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:

    db_dsl: str | URL

    db_dsl = settings.db_dsl or ""

    if not db_dsl:
        logger.error("db_dsl not initialized")

    db_manager.init(db_dsl=db_dsl)
    setup_clickhouse()

    yield

    await db_manager.close()
    ch_container.close()


app = FastAPI(
    title=settings.app_name, version=settings.version, lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(StructlogMiddleware)


app.include_router(misk_router, prefix="", tags=["misk"])
app.include_router(calc_router, prefix="", tags=["calculations"])


@app.exception_handler(TaskNotFinishedException)
async def task_not_finished_handler(
    _: Request, exc: TaskNotFinishedException
) -> JSONResponse:

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "detail": "task not ready",
            "task_id": exc.task_id,
            "status": exc.current_status,
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
        log_config=None,
        access_log=False,
    )
