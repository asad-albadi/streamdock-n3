"""streamdock-n3-linux: Linux controller and GTK4 GUI for the Stream Dock N3."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("streamdock-n3-linux")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
