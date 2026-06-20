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


ENV_PREFIX = "STASHAI_"

FLAT_ENV_MAP: dict[str, tuple[str, str]] = {
    "STASHAI_STASH_URL": ("stash", "url"),
    "STASHAI_STASH_API_KEY": ("stash", "api_key"),
    "STASHAI_STASH_PAGE_SIZE": ("stash", "page_size"),
    "STASHAI_DATABASE_URL": ("database", "url"),
    "STASHAI_MODELS_DIRECTORY": ("models", "directory"),
    "STASHAI_MODELS_POSITIVE_RATING_THRESHOLD": ("models", "positive_rating_threshold"),
    "STASHAI_MODELS_NEGATIVE_RATING_THRESHOLD": ("models", "negative_rating_threshold"),
    "STASHAI_MODELS_RECOMMENDATION_THRESHOLD": ("models", "recommendation_threshold"),
    "STASHAI_MODELS_REVIEW_CONFIDENCE_THRESHOLD": ("models", "review_confidence_threshold"),
    "STASHAI_MODELS_REMOVAL_THRESHOLD": ("models", "removal_threshold"),
    "STASHAI_APP_HOST": ("app", "host"),
    "STASHAI_APP_PORT": ("app", "port"),
}


def _merge_settings(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_settings(merged[key], value)
        else:
            merged[key] = value
    return merged


def _set_nested(data: dict[str, Any], section: str, field: str, value: str) -> None:
    data.setdefault(section, {})[field] = value


def _env_settings() -> dict[str, Any]:
    data: dict[str, Any] = {}

    for env_name, path in FLAT_ENV_MAP.items():
        if env_name in os.environ:
            _set_nested(data, *path, os.environ[env_name])

    for env_name, value in os.environ.items():
        if not env_name.startswith(ENV_PREFIX) or "__" not in env_name:
            continue
        parts = env_name.removeprefix(ENV_PREFIX).lower().split("__")
        if len(parts) != 2:
            continue
        section, field = parts
        if section in Settings.model_fields:
            _set_nested(data, section, field, value)

    return data


def load_settings(path: str | Path | None = None) -> Settings:
    config_path = Path(path or os.getenv("STASHAI_CONFIG") or "config.yaml")
    data: dict[str, Any] = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    data = _merge_settings(data, _env_settings())
    return Settings.model_validate(data)


def ensure_runtime_dirs(settings: Settings) -> None:
    if settings.database.url.startswith("sqlite:///"):
        db_path = Path(settings.database.url.removeprefix("sqlite:///"))
        if db_path.parent != Path("."):
            db_path.parent.mkdir(parents=True, exist_ok=True)
    Path(settings.models.directory).mkdir(parents=True, exist_ok=True)
