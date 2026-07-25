import logging
import sys

import structlog


def configure_logging(is_dev: bool = False):

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    formatter = (
        structlog.dev.ConsoleRenderer(colors=True)
        if is_dev
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, formatter],
        logger_factory=structlog.BytesLoggerFactory()
        if not is_dev
        else structlog.WriteLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )

    stdlib_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            lambda _, __, event_dict: {
                **event_dict,
                "event": event_dict.get("message", event_dict.get("event")),
            },
            *shared_processors,
            formatter,
        ]
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(stdlib_formatter)

    for logger_name in ("", "uvicorn", "uvicorn.error", "sqlalchemy.engine"):
        log = logging.getLogger(logger_name)
        log.handlers = [handler]
        log.setLevel(logging.INFO)
        log.propagate = False

    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers = [handler]
    uvicorn_access.setLevel(logging.WARNING)
    uvicorn_access.propagate = False
