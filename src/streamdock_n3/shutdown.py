"""Process teardown for entry points that hold an open StreamDock handle."""

from __future__ import annotations

import contextlib
import os
import sys
from typing import NoReturn


def hard_exit(code: int) -> NoReturn:
    """Flush the standard streams, then exit without interpreter finalization.

    The vendored SDK's `libtransport.so` has a broken thread-cleanup path:
    joining its reader and heartbeat threads — which is what `device.close()`
    does — trips glibc's tcache integrity check and aborts the process with
    "unaligned tcache chunk detected". Skipping `close()` and bypassing
    finalization lets the kernel reclaim the HID fd while those threads die
    without running their C destructors.

    Flushing first is not optional: `os._exit` does not flush Python's
    buffers, and stdout is block-buffered when the process runs under
    systemd, so a final diagnostic would otherwise be lost.
    """
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(OSError, ValueError):
            stream.flush()
    os._exit(code)
