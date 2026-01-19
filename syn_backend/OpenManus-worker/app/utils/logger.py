import logging
import os

try:
    import structlog
except ModuleNotFoundError:  # pragma: no cover
    structlog = None


ENV_MODE = os.getenv("ENV_MODE", "LOCAL")

if structlog is None:  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("openmanus")
else:
    renderer = [structlog.processors.JSONRenderer()]
    if ENV_MODE.lower() == "local".lower():
        renderer = [structlog.dev.ConsoleRenderer()]

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.dict_tracebacks,
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            ),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.contextvars.merge_contextvars,
            *renderer,
        ],
        cache_logger_on_first_use=True,
    )

    logger: structlog.stdlib.BoundLogger = structlog.get_logger(level=logging.DEBUG)
