#!/usr/bin/env python3
"""Config-driven Linux controller for the Stream Dock N3."""

from __future__ import annotations

import argparse
import contextlib
import os
import select
import signal
import subprocess
import threading
import time
import traceback
from pathlib import Path
from typing import Any

from streamdock_n3 import config as configmod
from streamdock_n3 import paths
from streamdock_n3._vendor.StreamDock.DeviceManager import DeviceManager
from streamdock_n3.events import (
    BUTTON_NAMES,  # noqa: F401
    KNOB_NAMES,  # noqa: F401
    describe_event,
    evdev_event_key,
    event_key,
)
from streamdock_n3.icons import FALLBACK_COLORS, make_icon, parse_color
from streamdock_n3.shutdown import hard_exit

try:
    from evdev import InputDevice, categorize, ecodes, list_devices  # type: ignore
except ImportError:  # pragma: no cover
    InputDevice = None  # type: ignore[assignment]
    categorize = None  # type: ignore[assignment]
    ecodes = None  # type: ignore[assignment]
    list_devices = None  # type: ignore[assignment]


VID = "6603"
PID = "1003"


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


def apply_icons(device, config: dict[str, Any]) -> None:
    keys = configmod.normalize(config)["keys"]

    icon_dir = paths.generated_key_dir()
    icon_dir.mkdir(parents=True, exist_ok=True)

    for key in range(1, 7):
        item = keys.get(str(key), {})
        icon_path = item.get("icon")
        if icon_path:
            source = Path(icon_path).expanduser()
            if source.exists():
                device.set_key_image(key, str(source))
                continue

        label = str(item.get("label", key))
        color = parse_color(item.get("color"), FALLBACK_COLORS[key - 1])
        generated = icon_dir / f"key-{key}.jpg"
        make_icon(label, color, generated)
        device.set_key_image(key, str(generated))

    device.refresh()


def open_device():
    manager = DeviceManager()
    devices = manager.enumerate()
    if not devices:
        raise RuntimeError("no StreamDock device found")
    return devices[0]


def hidraw_paths() -> list[Path]:
    out = []
    token = f"v0000{VID.upper()}p0000{PID.upper()}"
    for hidraw in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        uevent = hidraw / "device" / "uevent"
        try:
            text = uevent.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if token in text:
            out.append(Path("/dev") / hidraw.name)
    return out


def is_streamdock_evdev(path: str) -> bool:
    if InputDevice is None:
        return False
    try:
        dev = InputDevice(path)
    except OSError:
        return False
    # Probing runs over every /dev/input/event* on the system, twice at
    # startup; without the close() each probe leaks an fd for the life of
    # the process.
    try:
        info = dev.info
        name = (dev.name or "").lower()
        return (
            (info.vendor == int(VID, 16) and info.product == int(PID, 16))
            or "hotspotekusb" in name
            or "streamdock" in name
        )
    finally:
        with contextlib.suppress(OSError):
            dev.close()


def streamdock_evdev_paths() -> list[Path]:
    found: set[Path] = set()
    by_id = Path("/dev/input/by-id")
    if by_id.exists():
        for link in by_id.glob("*HOTSPOTEKUSB*event*"):
            with contextlib.suppress(OSError):
                found.add(link.resolve())

    if list_devices is not None:
        for path in list_devices():
            if is_streamdock_evdev(path):
                found.add(Path(path))

    return sorted(found)


def _warn_unreadable(label: str, items: list[Path]) -> None:
    unreadable = [p for p in items if not os.access(p, os.R_OK)]
    if not unreadable:
        return
    joined = ", ".join(str(p) for p in unreadable)
    print(
        f"warning: StreamDock {label} nodes are not readable by this user: {joined}\n"
        "Run `sudo streamdock-n3-install` and unplug/replug the dock.",
        flush=True,
    )


def warn_if_hidraw_unreadable() -> None:
    _warn_unreadable("hidraw", hidraw_paths())


def warn_if_evdev_unreadable() -> None:
    _warn_unreadable("input event", streamdock_evdev_paths())


def _dispatch_evdev(dev, actions: dict[str, Any], dry_run: bool) -> None:
    for event in dev.read():
        if event.type != ecodes.EV_KEY:
            continue
        key = categorize(event)
        keycodes = key.keycode if isinstance(key.keycode, list) else [key.keycode]
        for keycode in keycodes:
            mapped = evdev_event_key(str(keycode), event.value)
            print(f"evdev {keycode} value={event.value} [{mapped}]", flush=True)
            run_actions(actions.get(mapped), dry_run=dry_run)


def wants_evdev_grab(actions: dict[str, Any], config: dict[str, Any]) -> bool:
    """Whether to take the dock's input nodes exclusively (EVIOCGRAB).

    Without a grab, a dock keypress reaches both the compositor — which
    applies its own volume/media binding — and this daemon, so a mapped
    `evdev.*` action fires on top of it and the change lands twice. Grabbing
    makes the daemon the only consumer.

    Only grab when the config actually maps an `evdev.*` event: otherwise the
    daemon has no use for those keycodes and swallowing them would break
    bindings the compositor was handling perfectly well. `"grab_evdev": false`
    opts out entirely.
    """
    if not config.get("grab_evdev", True):
        return False
    return any(str(name).startswith("evdev.") for name in actions)


def evdev_worker(
    stop: threading.Event,
    actions: dict[str, Any],
    dry_run: bool,
    grab: bool = False,
) -> None:
    if InputDevice is None:
        return

    devices = []
    for path in streamdock_evdev_paths():
        try:
            dev = InputDevice(str(path))
            os.set_blocking(dev.fileno(), False)
            devices.append(dev)
            grabbed = ""
            if grab:
                try:
                    dev.grab()
                    grabbed = " (grabbed)"
                except OSError as exc:
                    # EBUSY means something else holds it; reading unexclusively
                    # is still better than not reading at all.
                    print(f"evdev cannot grab {path}: {exc}", flush=True)
            print(f"evdev listening: {path} {dev.name!r}{grabbed}", flush=True)
        except OSError as exc:
            print(f"evdev cannot open {path}: {exc}", flush=True)

    def release(dev) -> None:
        if grab:
            with contextlib.suppress(OSError):
                dev.ungrab()
        with contextlib.suppress(OSError):
            dev.close()

    def drop(dev, reason: str) -> None:
        print(f"evdev dropping {dev.path}: {reason}", flush=True)
        if dev in devices:
            devices.remove(dev)
        release(dev)

    try:
        # select() rather than a sleep-poll: it wakes on the actual event and
        # bounds the shutdown latency without burning 50 wakeups a second.
        while not stop.is_set() and devices:
            try:
                ready, _, _ = select.select(devices, [], [], 0.2)
            except OSError as exc:
                print(f"evdev select error: {exc}", flush=True)
                break
            for dev in ready:
                try:
                    _dispatch_evdev(dev, actions, dry_run)
                except BlockingIOError:
                    pass
                except OSError as exc:
                    # A device that errors once (unplug -> ENODEV) errors on
                    # every later pass. Retrying it would flood the journal
                    # for as long as the daemon runs, so retire it instead.
                    drop(dev, str(exc))
        if not devices:
            print("evdev: no devices left to read", flush=True)
    finally:
        for dev in list(devices):
            release(dev)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="streamdock-n3")
    parser.add_argument("--config", type=Path, help="Override config path.")
    parser.add_argument("--brightness", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-icons", action="store_true")
    parser.add_argument("--no-init", action="store_true")
    parser.add_argument("--seconds", type=float, default=0)
    parser.add_argument(
        "--no-grab",
        action="store_true",
        help="Do not take the dock's input nodes exclusively, even when "
        "evdev.* actions are configured. Media keys may then apply twice.",
    )
    args = parser.parse_args(argv)

    paths.ensure_runtime_dirs()
    config_path = args.config or configmod.ensure_config()
    config = configmod.normalize(configmod.load(config_path))
    actions = configmod.action_map(config)

    brightness = args.brightness
    if brightness is None:
        brightness = int(config.get("brightness", 80))

    warn_if_hidraw_unreadable()
    warn_if_evdev_unreadable()

    stop = False
    stop_event = threading.Event()

    def handle_signal(_signum, _frame):
        nonlocal stop
        stop = True
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    def on_input(_dev, event):
        key = event_key(event)
        print(f"{describe_event(event)} [{key}]", flush=True)
        if key:
            run_actions(actions.get(key), dry_run=args.dry_run)

    exit_code = 0
    try:
        device = open_device()
        print(
            f"using {type(device).__name__} vid={device.vendor_id:04x} "
            f"pid={device.product_id:04x} path={device.getPath()}",
            flush=True,
        )
        device.open()
        if not args.no_init:
            device.init()
        device.set_brightness(max(0, min(100, brightness)))
        if not args.no_icons:
            apply_icons(device, config)
        device.set_key_callback(on_input)
        grab = wants_evdev_grab(actions, config) and not args.no_grab
        evdev_thread = threading.Thread(
            target=evdev_worker,
            args=(stop_event, actions, args.dry_run, grab),
            daemon=True,
        )
        evdev_thread.start()

        started = time.monotonic()
        print("controller running; press Ctrl-C to stop", flush=True)
        while not stop:
            if args.seconds and time.monotonic() - started >= args.seconds:
                break
            time.sleep(0.1)
    except Exception:
        # hard_exit() skips interpreter finalization, so nothing else would
        # ever report this. Print it here or the journal shows a bare
        # "status=1/FAILURE" with no cause.
        traceback.print_exc()
        exit_code = 1
    finally:
        stop_event.set()
        # Reaching here without an exception is a success, whether the loop
        # ended on a signal or on --seconds elapsing.
        hard_exit(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
