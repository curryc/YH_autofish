import logging
import os
from datetime import datetime


class ConsoleActionFilter(logging.Filter):
    def filter(self, record):
        return record.levelno >= logging.INFO


def setup_logger(name="NTE_AutoFish"):
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_date = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(f"{log_dir}/{log_date}.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.addFilter(ConsoleActionFilter())

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

logger = setup_logger()


def log_kv(level: int, event: str, **fields):
    payload = " ".join(f"{k}={repr(v)}" for k, v in fields.items())
    logger.log(level, f"{event} {payload}".rstrip())