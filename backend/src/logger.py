import logging
from pathlib import Path

LOG_PATH = Path(__file__).parent.parent.parent / "logs" / "lobster.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(module)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ]
)

logger = logging.getLogger("lobster")
