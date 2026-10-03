#!/usr/bin/env python3
"""Migrate a flat streamdock-n3 config to the pages format.

Takes the existing keys and button.1-6 actions, moves them into pages[0],
and leaves global actions (knob, evdev, button.7-9) at root level.
"""

import json
import sys
from pathlib import Path

GLOBAL_ACTION_PREFIXES = (
    "knob.",
    "evdev.",
    "button.7.",
    "button.8.",
    "button.9.",
)


def is_global_action(key: str) -> bool:
    return any(key.startswith(prefix) for prefix in GLOBAL_ACTION_PREFIXES)


def migrate(config: dict) -> dict:
    if "pages" in config:
        print("Config already uses pages format, nothing to do.")
        sys.exit(0)

    keys = config.pop("keys", {})
    actions = config.pop("actions", {})

    page_actions = {}
    global_actions = {}
    for k, v in actions.items():
        if is_global_action(k):
            global_actions[k] = v
        else:
            page_actions[k] = v

    print(f"  LCD key definitions found:   {len(keys)} keys (1-6)")
    print(f"  Page-specific actions found: {len(page_actions)} (button.1-6)")
    print(f"  Global actions kept at root: {len(global_actions)} (knob, evdev, button.7-9)")

    config["pages"] = [
        {
            "name": "Page 1",
            "keys": keys,
            "actions": page_actions,
        }
    ]
    config["actions"] = global_actions

    return config


def main():
    config_path = Path(
        sys.argv[1] if len(sys.argv) > 1
        else Path.home() / ".config/streamdock-n3/config.json"
    )

    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)

    backup_path = config_path.with_suffix(".json.bak")
    backup_path.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Backup saved to: {backup_path}")
    print()

    with config_path.open(encoding="utf-8") as f:
        config = json.load(f)

    print("Migrating config:")
    migrated = migrate(config)

    tmp = config_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(migrated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(config_path)

    print()
    print(f"Done. Config written to: {config_path}")


if __name__ == "__main__":
    main()
