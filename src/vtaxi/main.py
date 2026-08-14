"""Application entrypoint.

At this stage (Step 2 -- Project Structure & Foundation) there is no bot,
database, or handler wiring yet -- only enough to prove the project
installs and boots cleanly. Aiogram polling/webhook startup is added in
Step 7 (Bot).
"""

import logging

from vtaxi.config.logging import configure_logging
from vtaxi.config.settings import get_settings

logger = logging.getLogger("vtaxi")


def run() -> None:
    """Configure logging/settings and confirm the application boots."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("VTaxi initialized successfully (environment=%s)", settings.environment)


if __name__ == "__main__":
    run()
