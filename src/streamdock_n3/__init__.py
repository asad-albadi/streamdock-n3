"""streamdock-n3-linux: Linux controller and GTK4 GUI for the Stream Dock N3."""

from __future__ import annotations

import os
import sys

# When invoked as root (typically `sudo streamdock-n3-install`), suppress
# bytecode writes so we don't drop root-owned .pyc files into the user-owned
# pipx / uv-tool venv. Those files block the next reinstall with "Permission
# denied" and force a manual sudo rm.
#
# This covers every submodule, and must live here rather than in one of them:
# by the time a submodule's body runs, its sibling __init__.pyc has already
# been emitted. It cannot cover everything, though — a module's .pyc is
# written before its body executes, so this file's own __init__.pyc is already
# on disk as root, and the venv's _virtualenv.py shim is compiled at
# interpreter startup, earlier still. An env var cannot help either: pipx's
# console scripts run `python -E`, which discards PYTHON*. Whatever slips
# through is cleaned up by system_install._purge_root_owned_bytecode.
if hasattr(os, "geteuid") and os.geteuid() == 0:
    sys.dont_write_bytecode = True

from importlib.metadata import PackageNotFoundError, version  # noqa: E402

try:
    __version__ = version("streamdock-n3-linux")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
