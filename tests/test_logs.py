import io
import json
import logging
from types import SimpleNamespace

from tracker.logs import JsonFormatter


def make_logger(name):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(name)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger, stream


def test_each_record_is_one_json_line_with_the_basic_fields():
    logger, stream = make_logger("tests.logs.basic")
    logger.warning("Ticket %s modifié", 12)

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["level"] == "WARNING"
    assert payload["logger"] == "tests.logs.basic"
    assert payload["message"] == "Ticket 12 modifié"  # accents are kept, not escaped
    assert "é" in lines[0]
    assert payload["time"].endswith("+00:00")


def test_exception_is_included_on_the_same_line():
    logger, stream = make_logger("tests.logs.exception")
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("Échec")

    payload = json.loads(stream.getvalue().splitlines()[0])
    assert "ValueError: boom" in payload["exception"]


def test_request_and_status_code_are_included_when_present():
    logger, stream = make_logger("tests.logs.request")
    request = SimpleNamespace(method="POST", path="/feedbacks/1/triage/")
    logger.warning("Forbidden", extra={"request": request, "status_code": 403})

    payload = json.loads(stream.getvalue().splitlines()[0])
    assert (payload["method"], payload["path"], payload["status"]) == ("POST", "/feedbacks/1/triage/", 403)


def test_no_request_fields_without_a_request():
    logger, stream = make_logger("tests.logs.norequest")
    logger.info("Plain")
    payload = json.loads(stream.getvalue().splitlines()[0])
    assert not {"method", "path", "status", "exception"} & payload.keys()
