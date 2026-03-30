# logging_setup.py
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    log_path = os.path.abspath("logs/agent.log")
    for existing in logger.handlers:
        if isinstance(existing, RotatingFileHandler) and getattr(existing, "baseFilename", None) == log_path:
            return

    handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=5
    )
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
