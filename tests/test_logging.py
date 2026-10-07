import io
import json
import logging

from careerops.core.logging import JsonLogFormatter


def test_json_log_formatter_emits_valid_allowlisted_fields() -> None:
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger("careerops.test.structured")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    logger.info(
        'analysis_event_with_"quotes"',
        extra={
            "request_id": "request-1",
            "run_id": "run-1",
            "attempt": 2,
            "database_ready": False,
            "redis_ready": True,
            "raw_output": "must-not-be-logged",
        },
    )

    payload = json.loads(output.getvalue())
    assert payload["event"] == 'analysis_event_with_"quotes"'
    assert payload["request_id"] == "request-1"
    assert payload["run_id"] == "run-1"
    assert payload["attempt"] == 2
    assert payload["database_ready"] is False
    assert payload["redis_ready"] is True
    assert "raw_output" not in payload
    assert "timestamp" in payload
