"""Logging helpers: a dependency-free JSON formatter (one JSON object per line, ready for log collectors)."""

import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # django.request records carry the request and the status code.
        request = getattr(record, "request", None)
        if request is not None:
            payload["method"] = getattr(request, "method", None)
            payload["path"] = getattr(request, "path", None)
        status_code = getattr(record, "status_code", None)
        if status_code:
            payload["status"] = status_code
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)
