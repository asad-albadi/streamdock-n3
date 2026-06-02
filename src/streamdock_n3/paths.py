"""XDG base-directory paths for streamdock-n3."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "streamdock-n3"


def _xdg(env_var: str, fallback: str) -> Path:
    value = os.environ.get(env_var)
    return Path(value) if value else Path.home() / fallback


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / APP_NAME


def cache_dir() -> Path:
    return _xdg("XDG_CACHE_HOME", ".cache") / APP_NAME


def state_dir() -> Path:
    return _xdg("XDG_STATE_HOME", ".local/state") / APP_NAME


def config_file() -> Path:
    return config_dir() / "config.json"


def icon_cache_dir() -> Path:
    return cache_dir() / "icons"


def generated_key_dir() -> Path:
    return cache_dir() / "keys"


def gui_log_file() -> Path:
    return state_dir() / "gui.log"


def ensure_runtime_dirs() -> None:
    for d in (config_dir(), cache_dir(), state_dir(), icon_cache_dir(), generated_key_dir()):
        d.mkdir(parents=True, exist_ok=True)
