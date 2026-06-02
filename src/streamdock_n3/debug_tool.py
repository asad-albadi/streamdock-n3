#!/usr/bin/env python3
"""Find which Linux interface emits Stream Dock N3 input events."""

from __future__ import annotations

import argparse
import contextlib
import os
import select
import threading
import time
from pathlib import Path

from evdev import InputDevice, categorize, ecodes, list_devices  # type: ignore

from streamdock_n3._vendor.StreamDock.DeviceManager import DeviceManager

VID = "6603"
PID = "1003"


def hexdump(data: bytes, limit: int = 64) -> str:
    return " ".join(f"{byte:02x}" for byte in data[:limit])


def is_streamdock_evdev(path: str) -> bool:
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
    found: set[Path] = set()
    for link in Path("/dev/input/by-id").glob("*HOTSPOTEKUSB*event*"):
        with contextlib.suppress(OSError):
            found.add(link.resolve())
    for path in list_devices():
        if is_streamdock_evdev(path):
            found.add(Path(path))
    return sorted(found)


def evdev_worker(stop: threading.Event) -> None:
    devices = []
    for path in streamdock_evdev_paths():
        try:
            dev = InputDevice(str(path))
            os.set_blocking(dev.fileno(), False)
            devices.append(dev)
            print(
                f"evdev: {path} name={dev.name!r} "
                f"vid={dev.info.vendor:04x} pid={dev.info.product:04x}",
                flush=True,
            )
        except OSError as exc:
            print(f"evdev: cannot open {path}: {exc}", flush=True)

    if not devices:
        print("evdev: no matching StreamDock input devices found", flush=True)
        return

    while not stop.is_set():
        ready, _, _ = select.select(devices, [], [], 0.2)
        for dev in ready:
            try:
                for event in dev.read():
                    if event.type == ecodes.EV_KEY:
                        key = categorize(event)
                        print(f"evdev {dev.path}: {key.keycode} value={event.value}", flush=True)
                    elif event.type != ecodes.EV_SYN:
                        print(
                            f"evdev {dev.path}: type={event.type} "
                            f"code={event.code} value={event.value}",
                            flush=True,
                        )
            except BlockingIOError:
                pass
            except OSError as exc:
                print(f"evdev {dev.path}: read error: {exc}", flush=True)


def hidraw_paths() -> list[Path]:
    out = []
    for hidraw in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        uevent = hidraw / "device" / "uevent"
        try:
            text = uevent.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if f"v0000{VID.upper()}p0000{PID.upper()}" in text:
            out.append(Path("/dev") / hidraw.name)
    return out


def hidraw_worker(stop: threading.Event) -> None:
    fds: list[tuple[int, Path]] = []
    for path in hidraw_paths():
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            fds.append((fd, path))
            print(f"hidraw: {path}", flush=True)
        except OSError as exc:
            print(f"hidraw: cannot open {path}: {exc}", flush=True)

    if not fds:
        print("hidraw: no matching /dev/hidraw nodes found", flush=True)
        return

    fd_list = [fd for fd, _ in fds]
    by_fd = dict(fds)
    try:
        while not stop.is_set():
            ready, _, _ = select.select(fd_list, [], [], 0.2)
            for fd in ready:
                try:
                    data = os.read(fd, 1024)
                except BlockingIOError:
                    continue
                except OSError as exc:
                    print(f"hidraw {by_fd[fd]}: read error: {exc}", flush=True)
                    continue
                if data:
                    print(f"hidraw {by_fd[fd]}: {hexdump(data)}", flush=True)
    finally:
        for fd, _ in fds:
            os.close(fd)


def sdk_worker(stop: threading.Event, init: bool) -> None:
    manager = DeviceManager()
    devices = manager.enumerate()
    if not devices:
        print("sdk: no device found", flush=True)
        return

    device = devices[0]
    print(
        f"sdk: {type(device).__name__} path={device.getPath()} "
        f"vid={device.vendor_id:04x} pid={device.product_id:04x}",
        flush=True,
    )

    try:
        device.open()
        if init:
            device.init()
        while not stop.is_set():
            data = device.read()
            if data:
                decoded = ""
                if len(data) > 10:
                    decoded = f" code=0x{data[9]:02x} state=0x{data[10]:02x}"
                print(f"sdk raw:{decoded} {hexdump(data)}", flush=True)
            time.sleep(0.01)
    finally:
        device.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="streamdock-n3-debug")
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--sdk", action="store_true")
    parser.add_argument("--init", action="store_true")
    args = parser.parse_args(argv)

    stop = threading.Event()
    workers = [
        threading.Thread(target=evdev_worker, args=(stop,), daemon=True),
        threading.Thread(target=hidraw_worker, args=(stop,), daemon=True),
    ]
    if args.sdk:
        workers.append(threading.Thread(target=sdk_worker, args=(stop, args.init), daemon=True))

    for worker in workers:
        worker.start()

    print("press/turn Stream Dock controls now", flush=True)
    started = time.monotonic()
    try:
        while time.monotonic() - started < args.seconds:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        for worker in workers:
            worker.join(timeout=1)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
