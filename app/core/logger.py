import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

logger = structlog.get_logger()


class StructlogMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        clear_contextvars()
        start_time = time.perf_counter()

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time

            logger.info(
                "http_request_processed",
                status_code=response.status_code,
                duration_ms=round(process_time * 1000, 2),
            )
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            process_time = time.perf_counter() - start_time
            logger.exception(
                "http_request_failed",
                error=str(e),
                duration_ms=round(process_time * 1000, 2),
            )
            raise e
