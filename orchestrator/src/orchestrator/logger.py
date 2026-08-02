import logging
import json
import os
import contextvars
from datetime import datetime, timezone

# Context variables to hold trace and request IDs
trace_id_var = contextvars.ContextVar("trace_id", default="")
request_id_var = contextvars.ContextVar("request_id", default="")

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "logger": record.name,
            "module": record.module,
            "funcName": record.funcName,
        }

        trace_id = trace_id_var.get()
        if trace_id:
            log_record["logging.googleapis.com/trace"] = trace_id

        request_id = request_id_var.get()
        if request_id:
            log_record["request_id"] = request_id

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)

def setup_logger():
    """
    Configures the root logger or base logger with the JSON formatter.
    This should ideally be called once at application startup.
    """
    logger = logging.getLogger("orchestrator")

    # Avoid duplicate handlers if setup_logger is called multiple times
    if not logger.handlers:
        log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, log_level_str, logging.INFO)
        logger.setLevel(level)

        handler = logging.StreamHandler()
        formatter = JSONFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

def get_logger(name=__name__):
    """
    Returns a logger for the given module name.
    """
    return logging.getLogger(name)

# Configure the base 'orchestrator' logger
logger = setup_logger()
