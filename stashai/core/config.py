from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class StashConfig(BaseModel):
    url: str = "http://localhost:9999/graphql"
    api_key: str | None = None
    page_size: int = 100


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///./data/stashai.sqlite3"


class ModelConfig(BaseModel):
    directory: str = "./models"
    positive_rating_threshold: int = 4
    negative_rating_threshold: int = 2
    recommendation_threshold: float = 0.70
    review_confidence_threshold: float = 0.35
    removal_threshold: float = 0.65


class AppConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8088


class Settings(BaseModel):
    stash: StashConfig = Field(default_factory=StashConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    models: ModelConfig = Field(default_factory=ModelConfig)
    app: AppConfig = Field(default_factory=AppConfig)


def load_settings(path: str | Path | None = None) -> Settings:
    config_path = Path(path or os.getenv("STASHAI_CONFIG", "config.yaml"))
    if not config_path.exists():
        return Settings()
    with config_path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh) or {}
    return Settings.model_validate(data)


def ensure_runtime_dirs(settings: Settings) -> None:
    if settings.database.url.startswith("sqlite:///"):
        db_path = Path(settings.database.url.removeprefix("sqlite:///"))
        if db_path.parent != Path("."):
            db_path.parent.mkdir(parents=True, exist_ok=True)
    Path(settings.models.directory).mkdir(parents=True, exist_ok=True)

