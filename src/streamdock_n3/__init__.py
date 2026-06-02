"""streamdock-n3-linux: Linux controller and GTK4 GUI for the Stream Dock N3."""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

try:
    __version__ = version("streamdock-n3-linux")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"

_VENDOR = Path(__file__).resolve().parent / "_vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

__all__ = ["__version__"]
