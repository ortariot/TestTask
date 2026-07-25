from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.misk import router as misk_router
from core.logger import StructlogMiddleware
from core.logger_config import configure_logging
from core.settings import settings

configure_logging(is_dev=settings.is_dev)

app = FastAPI(title=settings.app_name, version=settings.version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(StructlogMiddleware)


app.include_router(misk_router, prefix="", tags=["misk"])


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
