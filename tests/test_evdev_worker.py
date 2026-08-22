"""Regression tests for the evdev reader loop's failure handling."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from streamdock_n3 import daemon


class _FakeDev:
    """Minimal InputDevice stand-in backed by a real pipe fd, so select() works."""

    def __init__(self, path: str, error: OSError | None) -> None:
        self.path = path
        self._error = error
        self._read_fd, self._write_fd = os.pipe()
        # Keep the fd readable so select() reports it every pass.
        os.write(self._write_fd, b"x")
        self.closed = False
        self.grabbed = False
        self.reads = 0

    def fileno(self) -> int:
        return self._read_fd

    def read(self):
        self.reads += 1
        if self._error is not None:
            raise self._error
        return []

    def grab(self) -> None:
        self.grabbed = True

    def ungrab(self) -> None:
        self.grabbed = False

    def close(self) -> None:
        self.closed = True
        os.close(self._read_fd)
        os.close(self._write_fd)

    @property
    def name(self) -> str:
        return "fake dock"


def _run_worker(monkeypatch, dev, *, grab=False, timeout=5.0):
    monkeypatch.setattr(daemon, "streamdock_evdev_paths", lambda: [Path(dev.path)])
    monkeypatch.setattr(daemon, "InputDevice", lambda _path: dev)
    monkeypatch.setattr(daemon.os, "set_blocking", lambda _fd, _flag: None)

    stop = threading.Event()
    thread = threading.Thread(
        target=daemon.evdev_worker, args=(stop, {}, True, grab), daemon=True
    )
    thread.start()
    thread.join(timeout=timeout)
    stop.set()
    return thread


def test_failing_device_is_dropped_not_retried(monkeypatch):
    """An unplugged device used to error every 20ms forever, flooding the journal."""
    dev = _FakeDev("/dev/input/fake0", OSError(19, "No such device"))
    thread = _run_worker(monkeypatch, dev)

    # The loop must exit on its own once the only device is retired, rather
    # than spinning on a device that can never recover.
    assert not thread.is_alive(), "worker did not exit after its only device failed"
    assert dev.reads == 1, f"failed device was retried {dev.reads} times"
    assert dev.closed


def test_worker_exits_when_stopped_and_closes_devices(monkeypatch):
    dev = _FakeDev("/dev/input/fake1", None)
    monkeypatch.setattr(daemon, "streamdock_evdev_paths", lambda: [Path(dev.path)])
    monkeypatch.setattr(daemon, "InputDevice", lambda _path: dev)
    monkeypatch.setattr(daemon.os, "set_blocking", lambda _fd, _flag: None)

    stop = threading.Event()
    thread = threading.Thread(
        target=daemon.evdev_worker, args=(stop, {}, True, False), daemon=True
    )
    thread.start()
    stop.set()
    thread.join(timeout=5.0)

    assert not thread.is_alive()
    assert dev.closed


def test_grab_is_taken_and_released(monkeypatch):
    dev = _FakeDev("/dev/input/fake2", OSError(19, "No such device"))
    _run_worker(monkeypatch, dev, grab=True)
    assert dev.grabbed is False, "grab must be released before close"
    assert dev.closed


def test_grab_failure_still_reads(monkeypatch):
    dev = _FakeDev("/dev/input/fake3", OSError(19, "No such device"))

    def busy() -> None:
        raise OSError(16, "Device or resource busy")

    dev.grab = busy  # type: ignore[method-assign]
    _run_worker(monkeypatch, dev, grab=True)
    # An unavailable grab must not stop the daemon from reading the device.
    assert dev.reads == 1
    assert dev.closed
