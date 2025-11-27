import logging
from logging import Logger
from logging.handlers import RotatingFileHandler
from pathlib import Path
from src.config.settings import LOG_DIR

LOG_FILE = LOG_DIR / "app.log"


def setup_logging(level=logging.INFO) -> Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(level)

    # Avoid duplicate handlers if called multiple times
    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        fh = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3)
        fmt = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger
