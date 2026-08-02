import io
import json
import logging

from orchestrator.logger import request_id_var, setup_logger, trace_id_var


def test_json_formatter():
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)

    # capture logs
    log_capture_string = io.StringIO()
    ch = logging.StreamHandler(log_capture_string)

    from orchestrator.logger import JSONFormatter
    ch.setFormatter(JSONFormatter())
    logger.addHandler(ch)

    # Set context variables
    trace_id_var.set("trace-123")
    request_id_var.set("req-456")

    logger.info("This is a test message")

    log_contents = log_capture_string.getvalue()
    log_dict = json.loads(log_contents)

    assert log_dict["severity"] == "INFO"
    assert log_dict["message"] == "This is a test message"
    assert log_dict["logging.googleapis.com/trace"] == "trace-123"
    assert log_dict["request_id"] == "req-456"
    assert "timestamp" in log_dict
    assert log_dict["logger"] == "test_logger"

def test_setup_logger():
    from orchestrator.logger import get_logger
    logger = setup_logger()
    assert isinstance(logger, logging.Logger)
    assert logger.name == "orchestrator"
    assert logger.hasHandlers()

    sublogger = get_logger("orchestrator.submodule")
    assert sublogger.name == "orchestrator.submodule"
    assert not sublogger.handlers
