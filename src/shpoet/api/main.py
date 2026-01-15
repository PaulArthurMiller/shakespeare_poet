"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI

from shpoet.config.settings import get_settings


logger = logging.getLogger(__name__)


def configure_logging(config_path: Path) -> None:
    """Configure logging using a YAML configuration file."""

    if not config_path.exists():
        logging.basicConfig(level=logging.INFO)
        logger.warning("Logging config not found at %s; using basicConfig", config_path)
        return

    with config_path.open("r", encoding="utf-8") as file_handle:
        config_data: dict[str, Any] = yaml.safe_load(file_handle)

    logging.config.dictConfig(config_data)


settings = get_settings()
configure_logging(settings.log_config_path)

app = FastAPI(title=settings.app_name)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return a simple health check payload."""

    return {"status": "ok"}
