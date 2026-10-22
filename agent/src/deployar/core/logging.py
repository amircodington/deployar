"""structlog JSON logs with the redactor as the last processor before rendering."""

import logging
import sys
from typing import TextIO

import structlog

from deployar.core.redact import redact_processor


def configure_logging(stream: TextIO = sys.stdout, level: int = logging.INFO) -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            redact_processor,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=False,
    )
    # httpx logs full URLs at INFO; keep it quiet so request details never reach logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
