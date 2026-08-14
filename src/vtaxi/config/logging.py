"""Logging configuration.

Loads the structured `logging.config.dictConfig` definition from
`configs/logging.yaml`. Falls back to `logging.basicConfig` if that file is
missing, so the application never fails to start over a logging config
problem -- observability is important, but it must not be a hard dependency
for boot.
"""

import logging
import logging.config
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOGGING_CONFIG_PATH = _REPO_ROOT / "configs" / "logging.yaml"


def configure_logging(level: str = "INFO") -> None:
    """Apply the logging configuration, overriding the root/vtaxi level."""
    if _LOGGING_CONFIG_PATH.exists():
        config = yaml.safe_load(_LOGGING_CONFIG_PATH.read_text(encoding="utf-8"))
        config.setdefault("loggers", {}).setdefault("vtaxi", {})["level"] = level.upper()
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(
            level=level.upper(),
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        )
