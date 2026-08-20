import logging

logger = logging.getLogger("hospital")
logger.setLevel(logging.INFO)

if not logger.handlers:
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = logging.FileHandler("hospital.log")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
