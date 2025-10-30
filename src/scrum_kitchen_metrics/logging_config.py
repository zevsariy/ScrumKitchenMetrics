"""Central logging configuration."""
from __future__ import annotations

import logging
import json as _json
import sys
from logging import Logger
from typing import Optional

from .config import get_settings

_LEVEL_MAP = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}

class ColourFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\x1b[36m",      # Cyan
        logging.INFO: "\x1b[32m",       # Green
        logging.WARNING: "\x1b[33m",    # Yellow
        logging.ERROR: "\x1b[31m",      # Red
        logging.CRITICAL: "\x1b[35m",   # Magenta
    }
    RESET = "\x1b[0m"

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        color = self.COLORS.get(record.levelno, "")
        message = super().format(record)
        if color:
            return f"{color}{message}{self.RESET}"
        return message

def configure_logging(level: Optional[str] = None) -> None:
    settings = get_settings()
    log_level_name = (level or settings.core.log_level or "INFO").upper()
    log_level = _LEVEL_MAP.get(log_level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(log_level)

    # Clear existing handlers to avoid duplicate logs when reconfiguring
    root.handlers.clear()

    if settings.core.log_format.lower() == 'json':
        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:  # noqa: D401
                data = {
                    "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                    "level": record.levelname,
                    "logger": record.name,
                    "msg": record.getMessage(),
                }
                if record.exc_info:
                    data["exc_info"] = self.formatException(record.exc_info)
                return _json.dumps(data, ensure_ascii=False)
        formatter = JsonFormatter()
    else:
        formatter = ColourFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    logging.getLogger(__name__).debug("Logging configured at level %s", log_level_name)

def get_logger(name: str) -> Logger:
    return logging.getLogger(name)

__all__ = ["configure_logging", "get_logger"]
