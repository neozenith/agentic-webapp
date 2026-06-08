"""Logging configuration. JSON-ish single-line in prod (Cloud Logging friendly),
terse in dev. Call configure_logging() once at startup."""

import logging
import sys

_DETAILED = "%(asctime)s %(levelname)s %(name)s:%(lineno)d %(message)s"


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_DETAILED))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # Quiet the noisy GCP/urllib3 transport loggers unless we're debugging.
    for noisy in ("google.auth", "urllib3", "google.cloud"):
        logging.getLogger(noisy).setLevel(max(logging.INFO, root.level))
