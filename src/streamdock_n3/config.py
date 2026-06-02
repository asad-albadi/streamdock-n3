"""Config IO: load/save the user's runtime config from XDG_CONFIG_HOME."""

from __future__ import annotations

import json
import os
import shutil
from importlib import resources
from pathlib import Path
from typing import Any

from streamdock_n3 import paths

DEFAULT_CONFIG: dict[str, Any] = {
    "brightness": 80,
    "keys": {
        "1": {"label": "Term", "color": "#1c63b8"},
        "2": {"label": "Web", "color": "#188452"},
        "3": {"label": "Files", "color": "#b55324"},
        "4": {"label": "OBS", "color": "#8444a8"},
        "5": {"label": "Mute", "color": "#327a8a"},
        "6": {"label": "Play", "color": "#ae365c"},
    },
    "actions": {
        "button.1.press": "alacritty",
        "button.2.press": "xdg-open https://",
        "button.3.press": "xdg-open \"$HOME\"",
        "button.4.press": "obs",
        "button.5.press": "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle",
        "button.6.press": "playerctl play-pause",
        "button.7.press": "hyprctl dispatch workspace 1",
        "button.8.press": "hyprctl dispatch workspace 2",
        "button.9.press": "hyprctl dispatch workspace 3",
        "knob.1.left": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-",
        "knob.1.right": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+",
        "knob.1.press": "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle",
        "knob.2.left": "playerctl previous",
        "knob.2.right": "playerctl next",
        "knob.2.press": "playerctl play-pause",
        "knob.3.left": "wpctl set-volume @DEFAULT_AUDIO_SOURCE@ 5%-",
        "knob.3.right": "wpctl set-volume @DEFAULT_AUDIO_SOURCE@ 5%+",
        "knob.3.press": "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle",
        "evdev.KEY_VOLUMEDOWN.press": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-",
        "evdev.KEY_VOLUMEUP.press": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+",
        "evdev.KEY_MUTE.press": "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle",
        "evdev.KEY_PREVIOUSSONG.press": "playerctl previous",
        "evdev.KEY_NEXTSONG.press": "playerctl next",
        "evdev.KEY_PLAYPAUSE.press": "playerctl play-pause",
    },
}


def _shipped_default_path() -> Path | None:
    try:
        ref = resources.files("streamdock_n3").joinpath("_data/config.default.json")
        with resources.as_file(ref) as p:
            if p.is_file():
                return Path(p)
    except (FileNotFoundError, ModuleNotFoundError):
        pass
    return None


def ensure_config(path: Path | None = None) -> Path:
    """Create the config file with sane defaults if missing. Returns the path."""
    target = path or paths.config_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return target
    shipped = _shipped_default_path()
    if shipped is not None:
        shutil.copyfile(shipped, target)
        return target
    save(DEFAULT_CONFIG, target)
    return target


def load(path: Path | None = None) -> dict[str, Any]:
    target = path or paths.config_file()
    if not target.exists():
        ensure_config(target)
    with target.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("config root must be a JSON object")
    return data


def save(data: dict[str, Any], path: Path | None = None) -> None:
    target = path or paths.config_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, target)


def action_map(config: dict[str, Any]) -> dict[str, Any]:
    actions = config.get("actions", {})
    return actions if isinstance(actions, dict) else {}
