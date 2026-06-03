"""streamdock-n3-linux: Linux controller and GTK4 GUI for the Stream Dock N3."""

from __future__ import annotations

import os
import sys

# When invoked as root (typically `sudo streamdock-n3-install`), suppress
# bytecode writes so we don't drop root-owned .pyc files into the user-owned
# pipx / uv-tool venv. Those files block the next user-mode reinstall with
# "Permission denied" and force a manual sudo rm. Setting this in the
# package __init__ — not in any submodule — is essential, because by the
# time a submodule's body runs, its sibling __init__.pyc has already been
# emitted.
if hasattr(os, "geteuid") and os.geteuid() == 0:
    sys.dont_write_bytecode = True

from importlib.metadata import PackageNotFoundError, version  # noqa: E402

try:
    __version__ = version("streamdock-n3-linux")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
