import logging

import structlog
from structlog.processors import CallsiteParameterAdder

LOG_NAME = "ChatApp"


def initialize(log_level=logging.INFO, log_name=LOG_NAME):
    """Initialize the logging configuration for the application.

    Args:
        log_level (int): The logging level (e.g., logging.INFO, logging.DEBUG)
    """
    processors = [
        structlog.stdlib.add_log_level,
        CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    console_handler = logging.StreamHandler()
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.RichTracebackFormatter(),
        ),
        foreign_pre_chain=processors,
    )
    console_handler.setFormatter(formatter)
    root_logger = logging.getLogger(log_name)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(log_level)


def getLogger(log_name=LOG_NAME) -> structlog.stdlib.BoundLogger:
    """Retrieve the structured logger for the application."""
    return structlog.get_logger(log_name)
