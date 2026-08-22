"""Config IO: load/save the user's runtime config from XDG_CONFIG_HOME."""

from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path
from typing import Any

from streamdock_n3 import paths

DEFAULT_CONFIG: dict[str, Any] = {
    "brightness": 80,
    "grab_evdev": True,
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


def _shipped_default_text() -> str | None:
    """Return the packaged default config, or None if it cannot be read.

    Reads through the Traversable rather than resources.as_file: as_file may
    extract to a temp file that is unlinked when its context exits, so a path
    returned from inside that context is already gone by the time a caller
    opens it.
    """
    try:
        ref = resources.files("streamdock_n3").joinpath("_data/config.default.json")
        return ref.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return None


def _write_atomic(text: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, target)


def ensure_config(path: Path | None = None) -> Path:
    """Create the config file with sane defaults if missing. Returns the path."""
    target = path or paths.config_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return target
    shipped = _shipped_default_text()
    if shipped is not None:
        _write_atomic(shipped, target)
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
    _write_atomic(json.dumps(data, indent=2, ensure_ascii=False) + "\n", target)


def normalize(config: dict[str, Any]) -> dict[str, Any]:
    """Coerce a loaded config into the shape the daemon and GUI assume.

    A hand-edited file can hold junk — a string where a key object belongs, a
    missing "keys" object. The daemon tolerated this field by field; the GUI
    builds widgets straight from these values, so it has to do the same or the
    window fails to construct. Doing it once, up front, keeps both honest.

    Mutates and returns `config`. Deliberately does not invent entries for
    absent LCD keys: callers that need one use setdefault, so "key present but
    unusable" and "key absent" stay distinguishable here.
    """
    keys = config.get("keys")
    config["keys"] = {
        str(k): (v if isinstance(v, dict) else {})
        for k, v in (keys.items() if isinstance(keys, dict) else ())
    }
    if not isinstance(config.get("actions"), dict):
        config["actions"] = {}
    return config


def action_map(config: dict[str, Any]) -> dict[str, Any]:
    actions = config.get("actions", {})
    return actions if isinstance(actions, dict) else {}
