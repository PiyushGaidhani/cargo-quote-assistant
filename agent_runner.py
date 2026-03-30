#!/usr/bin/env python3
"""
Long-running runner for the Email-to-Quote agent.

It calls worker.process_emails() every 60 seconds until stopped.
"""

import time
import logging

from logging_setup import setup_logging
from worker import process_emails


def run_continuously(poll_interval: int = 60) -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Email-to-Quote agent loop (interval=%s seconds)", poll_interval)

    try:
        while True:
            logger.info("Starting processing cycle")
            try:
                process_emails()
                logger.info("Processing cycle completed")
            except Exception as e:
                logger.exception("Error during processing cycle: %s", e)

            logger.info("Sleeping for %s seconds", poll_interval)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")


if __name__ == "__main__":
    run_continuously(poll_interval=60)
