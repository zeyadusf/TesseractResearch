""" app.core.logging"""
from functools import lru_cache
import logging
import sys
from app.core.config import get_setting
config = get_setting()

@lru_cache
def get_logger(name:str)->logging.Logger:

    logger = logging.getLogger(name=name)

    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent log messages bubbling up to root logger
    logger.propagate = False

    return logger