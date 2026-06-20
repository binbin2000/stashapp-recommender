from __future__ import annotations

import os

from stashai.core.config import load_settings


def clear_stashai_env(monkeypatch):
    for env_name in list(os.environ):
        if env_name.startswith("STASHAI_"):
            monkeypatch.delenv(env_name, raising=False)


def test_load_settings_uses_env_without_config_file(monkeypatch, tmp_path):
    clear_stashai_env(monkeypatch)
    monkeypatch.setenv("STASHAI_STASH_URL", "http://stash:9999/graphql")
    monkeypatch.setenv("STASHAI_STASH_PAGE_SIZE", "250")
    monkeypatch.setenv("STASHAI_DATABASE_URL", "sqlite:////app/data/test.sqlite3")
    monkeypatch.setenv("STASHAI_APP_PORT", "8090")

    settings = load_settings(tmp_path / "missing.yaml")

    assert settings.stash.url == "http://stash:9999/graphql"
    assert settings.stash.page_size == 250
    assert settings.database.url == "sqlite:////app/data/test.sqlite3"
    assert settings.app.port == 8090


def test_load_settings_env_overrides_yaml(monkeypatch, tmp_path):
    clear_stashai_env(monkeypatch)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
stash:
  url: "http://yaml:9999/graphql"
models:
  recommendation_threshold: 0.50
app:
  port: 8088
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("STASHAI_STASH_URL", "http://env:9999/graphql")
    monkeypatch.setenv("STASHAI_MODELS_RECOMMENDATION_THRESHOLD", "0.85")

    settings = load_settings(config_path)

    assert settings.stash.url == "http://env:9999/graphql"
    assert settings.models.recommendation_threshold == 0.85
    assert settings.app.port == 8088


def test_load_settings_supports_nested_env_names(monkeypatch, tmp_path):
    clear_stashai_env(monkeypatch)
    monkeypatch.setenv("STASHAI_STASH__URL", "http://nested:9999/graphql")
    monkeypatch.setenv("STASHAI_MODELS__REMOVAL_THRESHOLD", "0.9")

    settings = load_settings(tmp_path / "missing.yaml")

    assert settings.stash.url == "http://nested:9999/graphql"
    assert settings.models.removal_threshold == 0.9
