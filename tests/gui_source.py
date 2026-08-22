"""Load pure helpers out of gui.py without importing gi.

gui.py imports PyGObject at module scope, which is a distro package and not
installed in the test venv. The functions exercised here are pure string and
value handling, so the source is extracted and exec'd in an isolated namespace
instead. Each target must be a top-level def followed by another top-level def.
"""

from __future__ import annotations

import typing
from pathlib import Path

GUI_PATH = Path(__file__).resolve().parents[1] / "src/streamdock_n3/gui.py"


def load_gui_function(name: str):
    text = GUI_PATH.read_text(encoding="utf-8")
    marker = f"def {name}("
    start = text.index(marker)
    end = text.index("\ndef ", start + len(marker))
    # gui.py has `from __future__ import annotations`, the extracted snippet
    # does not, so annotations are evaluated on 3.11/3.12 and their names have
    # to be present.
    ns: dict = {"Any": typing.Any}
    exec(text[start:end], ns)
    return ns[name]
