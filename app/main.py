from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.misk import router as misk_router
from api.v1.tleanalyser import router as calc_router
from core.logger import StructlogMiddleware
from core.logger_config import configure_logging
from core.settings import settings
from database import db_manager

configure_logging(is_dev=settings.is_dev)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db_manager.init(db_dsl=settings.db_dsl)
    yield
    await db_manager.close()


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
