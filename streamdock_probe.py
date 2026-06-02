#!/usr/bin/env python3
"""Probe and lightly control a Stream Dock N3 on Linux."""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / "vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from PIL import Image, ImageDraw, ImageFont
from StreamDock.DeviceManager import DeviceManager
from StreamDock.InputTypes import EventType


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


def event_text(event) -> str:
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
    if event.event_type == EventType.SWIPE:
        return f"swipe {event.direction.value}"
    return "unknown event"


def make_icon(label: str, color: tuple[int, int, int], path: Path) -> None:
    image = Image.new("RGB", (64, 64), color)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=28)
    bbox = draw.textbbox((0, 0), label, font=font)
    x = (image.width - (bbox[2] - bbox[0])) // 2
    y = (image.height - (bbox[3] - bbox[1])) // 2
    draw.text((x, y), label, fill=(255, 255, 255), font=font)
    image.save(path, "JPEG", quality=95)


def set_test_icons(device) -> None:
    colors = [
        (28, 99, 184),
        (24, 132, 82),
        (181, 83, 36),
        (132, 68, 168),
        (50, 122, 138),
        (174, 54, 92),
    ]
    icon_dir = ROOT / ".streamdock-icons"
    icon_dir.mkdir(exist_ok=True)
    for key in range(1, 7):
        icon_path = icon_dir / f"key-{key}.jpg"
        make_icon(str(key), colors[key - 1], icon_path)
        result = device.set_key_image(key, str(icon_path))
        print(f"set key {key}: {result}", flush=True)
    device.refresh()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brightness", type=int, default=80)
    parser.add_argument("--no-init", action="store_true")
    parser.add_argument("--no-icons", action="store_true")
    parser.add_argument("--seconds", type=float, default=0)
    parser.add_argument(
        "--map",
        action="store_true",
        help="Print the known N3 input mapping before listening.",
    )
    args = parser.parse_args()

    manager = DeviceManager()
    devices = manager.enumerate()
    print(f"found {len(devices)} StreamDock device(s)")

    if not devices:
        return 2

    device = devices[0]
    print(
        f"using {type(device).__name__} vid={device.vendor_id:04x} "
        f"pid={device.product_id:04x} path={device.getPath()}"
    )
    if args.map:
        print("input map:")
        for key, name in BUTTON_NAMES.items():
            print(f"  button {key}: {name}")
        for key, name in KNOB_NAMES.items():
            print(f"  {key}: {name} press + left/right rotation")

    stop = False

    def handle_signal(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    def on_input(dev, event):
        print(event_text(event), flush=True)

    try:
        device.open()
        if not args.no_init:
            device.init()
        device.set_brightness(max(0, min(100, args.brightness)))
        device.set_key_callback(on_input)
        if not args.no_icons:
            set_test_icons(device)

        started = time.monotonic()
        print("listening; press Ctrl-C to stop", flush=True)
        while not stop:
            if args.seconds and time.monotonic() - started >= args.seconds:
                break
            time.sleep(0.1)
    finally:
        device.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
