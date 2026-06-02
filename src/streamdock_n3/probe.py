#!/usr/bin/env python3
"""Probe and lightly control a Stream Dock N3 on Linux."""

from __future__ import annotations

import argparse
import signal
import time

from streamdock_n3 import paths
from streamdock_n3._vendor.StreamDock.DeviceManager import DeviceManager
from streamdock_n3.events import BUTTON_NAMES, KNOB_NAMES, describe_event
from streamdock_n3.icons import FALLBACK_COLORS, make_icon


def set_test_icons(device) -> None:
    icon_dir = paths.generated_key_dir()
    icon_dir.mkdir(parents=True, exist_ok=True)
    for key in range(1, 7):
        icon_path = icon_dir / f"key-{key}.jpg"
        make_icon(str(key), FALLBACK_COLORS[key - 1], icon_path)
        result = device.set_key_image(key, str(icon_path))
        print(f"set key {key}: {result}", flush=True)
    device.refresh()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="streamdock-n3-probe")
    parser.add_argument("--brightness", type=int, default=80)
    parser.add_argument("--no-init", action="store_true")
    parser.add_argument("--no-icons", action="store_true")
    parser.add_argument("--seconds", type=float, default=0)
    parser.add_argument(
        "--map", action="store_true", help="Print the known N3 input mapping before listening."
    )
    args = parser.parse_args(argv)

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

    def handle_signal(_signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    def on_input(_dev, event):
        print(describe_event(event), flush=True)

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
