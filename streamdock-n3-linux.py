#!/usr/bin/env python3
"""Config-driven Linux controller for the Stream Dock N3."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / "vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from PIL import Image, ImageDraw, ImageFont
from StreamDock.DeviceManager import DeviceManager
from StreamDock.InputTypes import EventType

try:
    from evdev import InputDevice, categorize, ecodes, list_devices
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    InputDevice = None
    categorize = None
    ecodes = None
    list_devices = None


DEFAULT_CONFIG = ROOT / "streamdock-n3-linux.config.json"
VID = "6603"
PID = "1003"

BUTTON_NAMES = {
    1: "lcd key 1",
    2: "lcd key 2",
    3: "lcd key 3",
    4: "lcd key 4",
    5: "lcd key 5",
    6: "lcd key 6",
    7: "round button 1",
    8: "round button 2",
    9: "round button 3",
}

KNOB_NAMES = {
    "knob_1": "small knob 1",
    "knob_2": "small knob 2",
    "knob_3": "large knob",
}


def event_key(event) -> str | None:
    if event.event_type == EventType.BUTTON:
        state = "press" if event.state else "release"
        return f"button.{event.key.value}.{state}"
    if event.event_type == EventType.KNOB_PRESS:
        state = "press" if event.state else "release"
        knob = event.knob_id.value.replace("knob_", "")
        return f"knob.{knob}.{state}"
    if event.event_type == EventType.KNOB_ROTATE:
        knob = event.knob_id.value.replace("knob_", "")
        return f"knob.{knob}.{event.direction.value}"
    return None


def evdev_event_key(keycode: str, value: int) -> str:
    state = "press" if value == 1 else "release" if value == 0 else "repeat"
    return f"evdev.{keycode}.{state}"


def describe_event(event) -> str:
    if event.event_type == EventType.BUTTON:
        state = "pressed" if event.state else "released"
        name = BUTTON_NAMES.get(event.key.value, f"button {event.key.value}")
        return f"{name} {state}"
    if event.event_type == EventType.KNOB_PRESS:
        state = "pressed" if event.state else "released"
        name = KNOB_NAMES.get(event.knob_id.value, event.knob_id.value)
        return f"{name} {state}"
    if event.event_type == EventType.KNOB_ROTATE:
        name = KNOB_NAMES.get(event.knob_id.value, event.knob_id.value)
        return f"{name} rotated {event.direction.value}"
    return "unknown event"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("config root must be a JSON object")
    return data


def run_command(command: str, *, dry_run: bool) -> None:
    print(f"run: {command}", flush=True)
    if dry_run:
        return
    env = os.environ.copy()
    subprocess.Popen(
        command,
        shell=True,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def run_actions(actions: Any, *, dry_run: bool) -> None:
    if actions is None:
        return
    if isinstance(actions, str):
        run_command(actions, dry_run=dry_run)
        return
    if isinstance(actions, list):
        for action in actions:
            run_actions(action, dry_run=dry_run)
        return
    if isinstance(actions, dict):
        command = actions.get("command")
        if command:
            run_command(str(command), dry_run=dry_run)
        return
    raise ValueError(f"unsupported action: {actions!r}")


def make_icon(
    label: str,
    color: tuple[int, int, int],
    path: Path,
    text_color: tuple[int, int, int] = (255, 255, 255),
) -> None:
    image = Image.new("RGB", (64, 64), color)
    draw = ImageDraw.Draw(image)
    size = 26 if len(label) <= 3 else 18 if len(label) <= 5 else 14
    font = ImageFont.load_default(size=size)
    lines = label.split("\\n")
    line_boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_height = max(box[3] - box[1] for box in line_boxes)
    total_height = line_height * len(lines) + 2 * (len(lines) - 1)
    y = (image.height - total_height) // 2
    for line, box in zip(lines, line_boxes):
        width = box[2] - box[0]
        x = (image.width - width) // 2
        draw.text((x, y), line, fill=text_color, font=font)
        y += line_height + 2
    image.save(path, "JPEG", quality=95)


def parse_color(value: Any, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if not isinstance(value, str):
        return fallback
    value = value.strip().lstrip("#")
    if len(value) != 6:
        return fallback
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


def apply_icons(device, config: dict[str, Any]) -> None:
    keys = config.get("keys", {})
    if not isinstance(keys, dict):
        return

    icon_dir = ROOT / ".streamdock-icons"
    icon_dir.mkdir(exist_ok=True)
    fallback_colors = [
        (28, 99, 184),
        (24, 132, 82),
        (181, 83, 36),
        (132, 68, 168),
        (50, 122, 138),
        (174, 54, 92),
    ]

    for key in range(1, 7):
        item = keys.get(str(key), {})
        if not isinstance(item, dict):
            item = {}
        icon_path = item.get("icon")
        if icon_path:
            source = Path(icon_path).expanduser()
            if not source.is_absolute():
                source = ROOT / source
            if source.exists():
                device.set_key_image(key, str(source))
                continue

        label = str(item.get("label", key))
        color = parse_color(item.get("color"), fallback_colors[key - 1])
        generated = icon_dir / f"key-{key}.jpg"
        make_icon(label, color, generated)
        device.set_key_image(key, str(generated))

    device.refresh()


def action_map(config: dict[str, Any]) -> dict[str, Any]:
    actions = config.get("actions", {})
    return actions if isinstance(actions, dict) else {}


def open_device():
    manager = DeviceManager()
    devices = manager.enumerate()
    if not devices:
        raise RuntimeError("no StreamDock device found")
    return devices[0]


def hidraw_paths() -> list[Path]:
    paths = []
    token = f"v0000{VID.upper()}p0000{PID.upper()}"
    for hidraw in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        uevent = hidraw / "device" / "uevent"
        try:
            text = uevent.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if token in text:
            paths.append(Path("/dev") / hidraw.name)
    return paths


def is_streamdock_evdev(path: str) -> bool:
    if InputDevice is None:
        return False
    try:
        dev = InputDevice(path)
    except OSError:
        return False
    info = dev.info
    name = (dev.name or "").lower()
    return (
        (info.vendor == int(VID, 16) and info.product == int(PID, 16))
        or "hotspotekusb" in name
        or "streamdock" in name
    )


def streamdock_evdev_paths() -> list[Path]:
    paths = set()
    by_id = Path("/dev/input/by-id")
    if by_id.exists():
        for link in by_id.glob("*HOTSPOTEKUSB*event*"):
            try:
                paths.add(link.resolve())
            except OSError:
                pass

    if list_devices is not None:
        for path in list_devices():
            if is_streamdock_evdev(path):
                paths.add(Path(path))

    return sorted(paths)


def warn_if_hidraw_unreadable() -> None:
    unreadable = [path for path in hidraw_paths() if not os.access(path, os.R_OK)]
    if not unreadable:
        return
    joined = ", ".join(str(path) for path in unreadable)
    print(
        "warning: StreamDock hidraw nodes are not readable by this user: "
        f"{joined}\n"
        "Install the udev rule with ./install_udev.sh, then unplug/replug the dock.",
        flush=True,
    )


def warn_if_evdev_unreadable() -> None:
    unreadable = [path for path in streamdock_evdev_paths() if not os.access(path, os.R_OK)]
    if not unreadable:
        return
    joined = ", ".join(str(path) for path in unreadable)
    print(
        "warning: StreamDock input event nodes are not readable by this user: "
        f"{joined}\n"
        "Run ./install_udev.sh, then unplug/replug the dock.",
        flush=True,
    )


def evdev_worker(stop: threading.Event, actions: dict[str, Any], dry_run: bool) -> None:
    if InputDevice is None:
        return

    devices = []
    for path in streamdock_evdev_paths():
        try:
            dev = InputDevice(str(path))
            dev.set_nonblocking(True)
            devices.append(dev)
            print(f"evdev listening: {path} {dev.name!r}", flush=True)
        except OSError as exc:
            print(f"evdev cannot open {path}: {exc}", flush=True)

    while not stop.is_set():
        for dev in devices:
            try:
                for event in dev.read():
                    if event.type != ecodes.EV_KEY:
                        continue
                    key = categorize(event)
                    keycodes = key.keycode if isinstance(key.keycode, list) else [key.keycode]
                    for keycode in keycodes:
                        mapped = evdev_event_key(str(keycode), event.value)
                        print(f"evdev {keycode} value={event.value} [{mapped}]", flush=True)
                        run_actions(actions.get(mapped), dry_run=dry_run)
            except BlockingIOError:
                pass
            except OSError as exc:
                print(f"evdev read error on {dev.path}: {exc}", flush=True)
        time.sleep(0.02)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--brightness", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-icons", action="store_true")
    parser.add_argument("--no-init", action="store_true")
    parser.add_argument("--seconds", type=float, default=0)
    args = parser.parse_args()

    config = load_config(args.config)
    actions = action_map(config)
    brightness = args.brightness
    if brightness is None:
        brightness = int(config.get("brightness", 80))

    warn_if_hidraw_unreadable()
    warn_if_evdev_unreadable()
    device = open_device()
    print(
        f"using {type(device).__name__} vid={device.vendor_id:04x} "
        f"pid={device.product_id:04x} path={device.getPath()}"
    )

    stop = False
    stop_event = threading.Event()

    def handle_signal(signum, frame):
        nonlocal stop
        stop = True
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    def on_input(dev, event):
        key = event_key(event)
        print(f"{describe_event(event)} [{key}]", flush=True)
        if key:
            run_actions(actions.get(key), dry_run=args.dry_run)

    try:
        device.open()
        if not args.no_init:
            device.init()
        device.set_brightness(max(0, min(100, brightness)))
        if not args.no_icons:
            apply_icons(device, config)
        device.set_key_callback(on_input)
        evdev_thread = threading.Thread(
            target=evdev_worker,
            args=(stop_event, actions, args.dry_run),
            daemon=True,
        )
        evdev_thread.start()

        started = time.monotonic()
        print("controller running; press Ctrl-C to stop", flush=True)
        while not stop:
            if args.seconds and time.monotonic() - started >= args.seconds:
                break
            time.sleep(0.1)
    finally:
        stop_event.set()
        device.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
