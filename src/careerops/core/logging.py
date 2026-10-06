import json
import logging
from datetime import UTC, datetime

_STRUCTURED_FIELDS = (
    "request_id",
    "user_id",
    "run_type",
    "run_id",
    "attempt",
    "dispatch_source",
    "pipeline_version",
    "model_name",
    "status",
    "outcome",
    "error_code",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "failure_reason",
    "diagnostic",
    "response_sha256",
    "response_size_bytes",
    "error_type",
    "requeued",
    "dispatched",
    "dispatch_failed",
)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for field in _STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(log_level: str) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    if not root_logger.handlers:
        root_logger.addHandler(logging.StreamHandler())
    formatter = JsonLogFormatter()
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
